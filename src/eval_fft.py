#!/usr/bin/env python3
"""Place masked shells by joint periodic-FFT position and orientation search."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import resource
import sys
import time

sys.dont_write_bytecode = True


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Resume a completed run: %(prog)s --resume-from RUN --num-cones TOTAL --output-dir NEW_DIRECTORY",
    )
    parser.add_argument("x", type=float, metavar="X", help="First observer x in Mpc/h; also the translation-grid anchor.")
    parser.add_argument("y", type=float, metavar="Y", help="First observer y in Mpc/h.")
    parser.add_argument("z", type=float, metavar="Z", help="First observer z in Mpc/h.")
    parser.add_argument("box_size", type=float, metavar="BOXSIZE", help="Periodic box side in Mpc/h.")
    parser.add_argument("--mask", type=Path, required=True, help="Full HEALPix FITS mask; first table field.")
    parser.add_argument("--mask-values", type=int, nargs="+", default=[4], help="Accepted mask labels; BGS: 4.")
    parser.add_argument("--nmesh", type=int, required=True, help="Grid cells per axis, at least 2.")
    radial = parser.add_mutually_exclusive_group(required=True)
    radial.add_argument("--z-range", type=float, nargs=2, metavar=("ZMIN", "ZMAX"), help="Observed-redshift shell, HR4 Omega_m=0.26.")
    radial.add_argument("--r-range", type=float, nargs=2, metavar=("RMIN", "RMAX"), help="Radial shell in Mpc/h.")
    parser.add_argument("--strategy", choices=["base", "axes", "random", "mask-diverse"], required=True,
                        help="base: one fixed orientation; axes: prescribed rotations about box axes.")
    parser.add_argument("--angles-deg", type=float, nargs="+", default=[30, 60, 90, 120], help="axes angles; base is always included (default: 13 candidates).")
    parser.add_argument("--base-euler", type=float, nargs=3, default=[0, 0, 0], metavar=("X", "Y", "Z"), help="Extrinsic xyz Euler angles in degrees; sky-to-box matrix.")
    parser.add_argument("--candidate-count", type=int, default=13, help="Retained random/mask-diverse candidates, including base.")
    parser.add_argument("--pool-size", type=int, default=64, help="Shared initial random pool size, including base.")
    parser.add_argument("--angular-nside", type=int, default=32, help="Angular sampling for candidate libraries; input mask resolution is retained.")
    parser.add_argument("--seed", type=int, default=20261115, help="Common pool seed for random and mask-diverse.")
    parser.add_argument("--num-cones", type=int, required=True, help="Target window count, including the first fixed window.")
    parser.add_argument("--min-observer-distance", type=float, required=True, metavar="DMIN", help="Minimum periodic observer separation in Mpc/h.")
    parser.add_argument("--max-mean-prior", type=float, help="Optional stopping threshold on mean prior coverage; disabled by default.")
    parser.add_argument("--workers", type=int, default=8, help="Positive SciPy FFT worker count.")
    parser.add_argument("--chunk-size", type=int, default=262144, help="Grid centers per geometry chunk.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New run directory; existing paths are rejected.")
    parser.add_argument("--resume-from", type=Path, help="Resume form inherits geometry; see --resume-from RUN --help.")
    return parser


def build_resume_parser():
    parser = argparse.ArgumentParser(
        description="Continue a completed FFT run, preserving its existing windows and candidate library.",
    )
    parser.add_argument("--resume-from", type=Path, required=True, help="Completed run directory with result, library, coverage and search history.")
    parser.add_argument("--num-cones", type=int, required=True, help="New total count, including the existing windows.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory; the parent run is read only.")
    parser.add_argument("--workers", type=int, help="Override inherited FFT worker count.")
    parser.add_argument("--chunk-size", type=int, help="Override inherited geometry chunk size.")
    parser.add_argument("--max-mean-prior", type=float, help="Override inherited stopping threshold; omitted means inherit.")
    return parser


def resume_arguments(options):
    """Inherit geometry and search rules from a completed parent run."""
    source = options.resume_from.absolute()
    for name in ["result.json", "library.npz", "coverage.npz", "search_candidates.csv", "manifest.json"]:
        if not (source / name).is_file():
            raise ValueError(f"Missing resume input: {source / name}")
    previous = json.loads((source / "result.json").read_text())
    manifest = json.loads((source / "manifest.json").read_text())
    if previous.get("method") != "periodic_fft" or manifest.get("status") != "completed":
        raise ValueError("--resume-from must name a completed periodic_fft run.")
    if options.num_cones <= len(previous["selections"]):
        raise ValueError("New --num-cones must exceed the saved window count.")
    config = previous["arguments"].copy()
    config.update(resume_from=source, num_cones=options.num_cones, output_dir=options.output_dir)
    config["mask"] = Path(config["mask"])
    for name in ["workers", "chunk_size", "max_mean_prior"]:
        value = getattr(options, name)
        if value is not None:
            config[name] = value
    return argparse.Namespace(**config)


def restore_resume_state(args, template_indices):
    """Restore coverage, distance constraints and history without optimizing old windows."""
    import numpy as np

    source = args.resume_from
    previous = json.loads((source / "result.json").read_text())
    records = previous["selections"]
    shape = (args.nmesh,) * 3
    with np.load(source / "coverage.npz", allow_pickle=False) as archive:
        coverage = archive["coverage"]
    if coverage.shape != shape or coverage.dtype != np.uint32:
        raise ValueError("Saved coverage shape or dtype is incompatible with this run.")
    rebuilt = np.zeros(shape, dtype=np.uint32)
    nearest = np.full(shape, np.iinfo(np.int64).max, dtype=np.int64)
    shifts = []
    for row in records:
        shift = tuple(row[f"shift_{axis}"] for axis in "xyz")
        indices = shifted_indices(template_indices[row["candidate_id"]], shift, args.nmesh)
        if len(indices) != row["occupied_voxels"] or int(rebuilt.ravel()[indices].sum(dtype=np.uint64)) != row["prior_coverage_sum"]:
            raise ValueError("Saved windows no longer match rebuilt templates and history.")
        rebuilt.ravel()[indices] += 1
        update_nearest_squared(nearest, shift)
        shifts.append(shift)
    if not np.array_equal(rebuilt, coverage):
        raise ValueError("Saved coverage does not match the saved windows with the current mask.")
    del rebuilt
    integer_fields = {"observer_id", "candidate_id", "legal_positions", "shift_x", "shift_y", "shift_z",
                      "prior_coverage_sum", "occupied_voxels", "selected"}
    with (source / "search_candidates.csv").open() as stream:
        candidates = [
            {key: int(value) if key in integer_fields else value if key == "label" else float(value)
             for key, value in row.items()}
            for row in csv.DictReader(stream)
        ]
    return {
        "coverage": coverage, "nearest": nearest, "records": records, "shifts": shifts,
        "rows": [{key: value for key, value in row.items() if key not in ["matrix_sky_to_box", "quaternion_xyzw"]}
                 for row in records],
        "candidates": candidates, "covered_voxels": int(np.count_nonzero(coverage)),
        "coverage_sum": sum(row["occupied_voxels"] for row in records),
        "coverage_square_sum": sum(row["coverage_square_increment"] for row in records),
        "max_coverage": int(coverage.max()),
        "previous_elapsed_sec": previous["final_metrics"].get("cumulative_elapsed_sec", previous["final_metrics"]["total_elapsed_sec"]),
    }


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows, empty_fields):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else empty_fields)
        writer.writeheader()
        writer.writerows(rows)


def make_fft_library(args, base, mask, directions):
    """Leave legacy libraries unchanged; new random strategies share one pool."""
    import numpy as np
    from orientation_geometry import make_library

    rng = np.random.default_rng(args.seed)
    strategy = "axes" if args.strategy == "base" else args.strategy
    angles = [] if args.strategy == "base" else args.angles_deg
    count = args.pool_size if strategy == "random" else args.candidate_count
    library, signatures = make_library(
        strategy, base, angles, count, args.pool_size, rng, mask, directions,
    )
    if strategy == "random":
        library = library[:args.candidate_count]
        signatures = signatures[:args.candidate_count]
    return library, signatures


def shifted_indices(indices, shift, nmesh):
    """Translate occupied C-order xyz indices by an integer periodic shift."""
    x = (indices // (nmesh * nmesh) + shift[0]) % nmesh
    y = ((indices // nmesh) % nmesh + shift[1]) % nmesh
    z = (indices % nmesh + shift[2]) % nmesh
    return (x * nmesh + y) * nmesh + z


def update_nearest_squared(nearest, shift):
    """Track nearest-observer distances exactly in squared lattice units."""
    import numpy as np

    nmesh = nearest.shape[0]
    axes = []
    for value in shift:
        delta = (np.arange(nmesh, dtype=np.int64) - value + nmesh // 2) % nmesh - nmesh // 2
        axes.append(delta * delta)
    yz = axes[1][:, None] + axes[2][None, :]
    for start in range(0, nmesh, 8):
        stop = min(start + 8, nmesh)
        distances = axes[0][start:stop, None, None] + yz[None, :, :]
        np.minimum(nearest[start:stop], distances, out=nearest[start:stop])


def restore_integer_scores(scores):
    """Remove FFT roundoff in chunks and retain the measured maximum residual."""
    import numpy as np

    residual = 0.0
    for start in range(0, scores.shape[0], 8):
        block = scores[start:start + 8]
        rounded = np.rint(block)
        residual = max(residual, float(np.max(np.abs(block - rounded))))
        np.maximum(rounded, 0, out=block)
    if residual >= 0.25:
        raise ArithmeticError(f"FFT residual {residual:g} is too large to restore integer overlap counts.")
    return residual


def best_translation(scores, nearest, valid):
    """Minimize counts, maximize nearest distance, then minimize flat index."""
    import numpy as np

    scores[~valid] = np.inf
    count = int(scores.min())
    tied = scores == count
    distance_squared = int(np.max(nearest, where=tied, initial=-1))
    tied &= nearest == distance_squared
    flat_index = int(tied.argmax())
    return count, distance_squared, flat_index


def plot_coverage(path, coverage, observers, box_size):
    """Save three Cartesian projections of the final integer coverage."""
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    for collapsed, axis in enumerate(axes):
        remaining = [index for index in range(3) if index != collapsed]
        image = axis.imshow(coverage.sum(axis=collapsed).T, origin="lower",
                            extent=[0, box_size, 0, box_size], cmap="viridis")
        for index, observer in enumerate(observers):
            x, y = observer[remaining[0]], observer[remaining[1]]
            axis.scatter(x, y, color="red", marker="+", s=40)
            axis.annotate(str(index), (x, y), xytext=(4, 4), textcoords="offset points", color="red")
        axis.set_xlabel("xyz"[remaining[0]] + " (Mpc/h)")
        axis.set_ylabel("xyz"[remaining[1]] + " (Mpc/h)")
        figure.colorbar(image, ax=axis, label="Summed coverage along " + "xyz"[collapsed], shrink=0.75)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(args, output, log):
    import numpy as np
    from scipy import fft
    from scipy.spatial.transform import Rotation
    from orientation_geometry import (
        Orientation, SkyMask, angular_directions, comoving_distance, jaccard, mask_signature,
        rotation_distance, shell_geometry,
    )

    started = time.perf_counter()
    shape = (args.nmesh,) * 3
    total = args.nmesh**3
    spacing = args.box_size / args.nmesh
    voxel_volume = spacing**3
    anchor = np.asarray([args.x, args.y, args.z]) % args.box_size
    base = Rotation.from_euler("xyz", args.base_euler, degrees=True).as_matrix()
    input_range = args.z_range or args.r_range
    range_mode = "z_range" if args.z_range else "r_range"
    rmin, rmax = [comoving_distance(z) for z in input_range] if args.z_range else input_range
    if not 0 <= rmin < rmax <= args.box_size / 2:
        raise ValueError("Shell must satisfy 0 <= rmin < rmax <= box_size/2.")
    config = {key: str(value.absolute()) if isinstance(value, Path) else value for key, value in vars(args).items()}
    versions = {name: importlib.metadata.version(name) for name in ["numpy", "scipy", "astropy", "healpy", "matplotlib"]}
    write_json(output / "run.json", {
        "method": "periodic_fft", "arguments": config, "versions": versions,
        "command": sys.argv, "observer_grid": "(anchor + integer_shift * box_size/nmesh) modulo box_size",
        "voxel_centers": "(index + 0.5) * box_size/nmesh; xyz axes; C order",
        "tie_breaking": ["minimum mean prior coverage (exact integer ratios)", "maximum nearest periodic observer distance", "minimum C-order flat position index", "minimum library index"],
        "random_pool": "same seed and pool-size for random and mask-diverse; legacy scripts unchanged",
        "fft_cache": "conjugated complex128 template spectra retained in memory only",
    })
    log.info("strategy=%s nmesh=%d spacing=%.8f Mpc/h target=%d dmin=%g Mpc/h shell=[%.8f, %.8f)",
             args.strategy, args.nmesh, spacing, args.num_cones, args.min_observer_distance, rmin, rmax)

    mask = SkyMask(args.mask, args.mask_values)
    try:
        area = mask.area()
        if not area:
            raise ValueError("No mask pixels match --mask-values.")
        analytic_volume = area * (np.pi / 180)**2 * (rmax**3 - rmin**3) / 3
        saved_sizes = None
        if args.resume_from:
            with np.load(args.resume_from / "library.npz", allow_pickle=False) as archive:
                library = [Orientation(str(label), matrix) for label, matrix in
                           zip(archive["labels"], archive["matrices_sky_to_box"])]
                signatures = archive["angular_signatures"]
                saved_sizes = archive["occupied_voxels"]
            log.info("Using saved candidate library from %s", args.resume_from)
        else:
            directions = angular_directions(args.angular_nside)
            library, signatures = make_fft_library(args, base, mask, directions)
        log.info("Building %d templates from native mask, area=%.8f deg^2", len(library), area)
        shell_indices, shell_directions = shell_geometry(
            args.box_size, args.nmesh, anchor, rmin, rmax, args.chunk_size,
        )
        spectra, template_indices, reference_intersections = [], [], []
        base_occupied = np.zeros(total, dtype=bool)
        for candidate_id, orientation in enumerate(library):
            stamp = time.perf_counter()
            indices = shell_indices[mask_signature(mask, shell_directions, orientation.matrix)]
            if not indices.size:
                raise ValueError(f"Empty template {orientation.label}; increase --nmesh.")
            if saved_sizes is not None and indices.size != saved_sizes[candidate_id]:
                raise ValueError(f"Rebuilt template {orientation.label} differs from the parent run.")
            window = np.zeros(total, dtype=bool)
            window[indices] = True
            if candidate_id == 0:
                base_occupied[indices] = True
            reference_intersections.append(int(np.count_nonzero(base_occupied[indices])))
            template_indices.append(indices)
            spectrum = fft.rfftn(window.reshape(shape), workers=args.workers)
            np.conjugate(spectrum, out=spectrum)
            spectra.append(spectrum)
            log.info("Template %d/%d %-16s occupied=%d fft=%.2fs", candidate_id + 1, len(library),
                     orientation.label, indices.size, time.perf_counter() - stamp)
            del window
        del shell_indices, shell_directions, base_occupied
        log.info("Template spectra in RAM: %.3f GiB", sum(item.nbytes for item in spectra) / 2**30)
        matrices = np.asarray([item.matrix for item in library])
        np.savez_compressed(
            output / "library.npz", matrices_sky_to_box=matrices,
            quaternions_xyzw=Rotation.from_matrix(matrices).as_quat(),
            labels=np.asarray([item.label for item in library]),
            occupied_voxels=np.asarray([len(item) for item in template_indices]),
            angular_signatures=signatures,
        )

        initial_count, previous_elapsed = 0, 0.0
        if args.resume_from:
            state = restore_resume_state(args, template_indices)
            coverage, nearest = state["coverage"], state["nearest"]
            selection_rows, selection_records = state["rows"], state["records"]
            candidate_rows, selected_shifts = state["candidates"], state["shifts"]
            covered_voxels, coverage_sum = state["covered_voxels"], state["coverage_sum"]
            coverage_square_sum, max_coverage = state["coverage_square_sum"], state["max_coverage"]
            previous_elapsed = state["previous_elapsed_sec"]
            initial_count = len(selection_rows)
            log.info("Restored and verified %d windows; continuing with observer=%d", initial_count, initial_count)
        else:
            coverage = np.zeros(shape, dtype=np.uint32)
            nearest = np.full(shape, np.iinfo(np.int64).max, dtype=np.int64)
            selection_rows, selection_records, candidate_rows, selected_shifts = [], [], [], []
            covered_voxels = coverage_sum = coverage_square_sum = max_coverage = 0

        def accept(candidate_id, shift, expected_count, distance_squared, elapsed):
            nonlocal covered_voxels, coverage_sum, coverage_square_sum, max_coverage
            indices = shifted_indices(template_indices[candidate_id], shift, args.nmesh)
            previous = coverage.ravel()[indices]
            prior_sum = int(previous.sum(dtype=np.uint64))
            if prior_sum != expected_count:
                raise ArithmeticError(f"Selected window count {prior_sum} differs from FFT count {expected_count}.")
            size = len(indices)
            new_voxels = int(np.count_nonzero(previous == 0))
            intersection = reference_intersections[candidate_id]
            covered_voxels += new_voxels
            coverage_sum += size
            increment = 2 * prior_sum + size
            coverage_square_sum += increment
            max_coverage = max(max_coverage, int(previous.max()) + 1)
            coverage.ravel()[indices] += 1
            observer = (anchor + np.asarray(shift) * spacing) % args.box_size
            row = {
                "observer_id": len(selection_rows), "observer_x": float(observer[0]),
                "observer_y": float(observer[1]), "observer_z": float(observer[2]),
                "shift_x": int(shift[0]), "shift_y": int(shift[1]), "shift_z": int(shift[2]),
                "candidate_id": candidate_id, "label": library[candidate_id].label,
                "rotation_from_base_deg": rotation_distance(library[candidate_id].matrix, base),
                "angular_iou_with_base": jaccard(signatures[candidate_id], signatures[0]),
                "occupied_voxels": size, "prior_coverage_sum": prior_sum,
                "mean_prior_coverage": prior_sum / size, "new_voxels": new_voxels,
                "covered_before_voxels": size - new_voxels, "coverage_square_increment": increment,
                "reference_intersection_voxels": intersection,
                "reference_iou": intersection / (size + len(template_indices[0]) - intersection),
                "reference_overlap_fraction": intersection / len(template_indices[0]),
                "nearest_observer_distance": math.sqrt(distance_squared) * spacing if distance_squared is not None else None,
                "volume_mpc_h_cubed": size * voxel_volume,
                "volume_relative_error": size * voxel_volume / analytic_volume - 1,
                "box_covered_fraction": covered_voxels / total,
                "coverage_mean": coverage_sum / total,
                "coverage_variance": coverage_square_sum / total - (coverage_sum / total)**2,
                "elapsed_sec": elapsed,
            }
            selection_rows.append(row)
            selection_records.append({**row, "matrix_sky_to_box": matrices[candidate_id].tolist(),
                                      "quaternion_xyzw": Rotation.from_matrix(matrices[candidate_id]).as_quat().tolist()})
            selected_shifts.append(tuple(int(value) for value in shift))
            update_nearest_squared(nearest, shift)
            log.info("Accepted observer=%d xyz=%s label=%s prior=%d mean_prior=%.8f nearest=%s box_covered=%.8f",
                     row["observer_id"], observer.tolist(), row["label"], prior_sum, row["mean_prior_coverage"],
                     row["nearest_observer_distance"], row["box_covered_fraction"])

        if not args.resume_from:
            accept(0, (0, 0, 0), 0, None, time.perf_counter() - started)
        stop_reason = "target_reached"
        for observer_id in range(len(selection_rows), args.num_cones):
            round_started = time.perf_counter()
            valid = nearest >= (args.min_observer_distance / spacing)**2
            valid_count = int(np.count_nonzero(valid))
            if not valid_count:
                stop_reason = "no_legal_position"
                log.info("Stopping: no position satisfies minimum observer distance.")
                break
            log.info("Searching observer=%d legal_positions=%d", observer_id, valid_count)
            coverage_spectrum = fft.rfftn(coverage.astype(np.float64), workers=args.workers)
            best_key, choice = None, None
            for candidate_id, spectrum in enumerate(spectra):
                stamp = time.perf_counter()
                product = coverage_spectrum * spectrum
                scores = fft.irfftn(product, s=shape, workers=args.workers, overwrite_x=True)
                del product
                residual = restore_integer_scores(scores)
                count, distance_squared, flat_index = best_translation(scores, nearest, valid)
                shift = tuple(int(value) for value in np.unravel_index(flat_index, shape))
                size = len(template_indices[candidate_id])
                key = (Fraction(count, size), -distance_squared, flat_index, candidate_id)
                row = {
                    "observer_id": observer_id, "candidate_id": candidate_id,
                    "label": library[candidate_id].label, "legal_positions": valid_count,
                    "shift_x": shift[0], "shift_y": shift[1], "shift_z": shift[2],
                    "prior_coverage_sum": count, "occupied_voxels": size,
                    "mean_prior_coverage": count / size,
                    "nearest_observer_distance": math.sqrt(distance_squared) * spacing,
                    "max_rounding_residual": residual, "selected": 0,
                    "elapsed_sec": time.perf_counter() - stamp,
                }
                candidate_rows.append(row)
                if best_key is None or key < best_key:
                    best_key, choice = key, (candidate_id, shift, count, distance_squared, len(candidate_rows) - 1)
                log.info("Search %d candidate=%d/%d %-16s mean_prior=%.8f nearest=%.4f residual=%.3g time=%.2fs",
                         observer_id, candidate_id + 1, len(library), row["label"], row["mean_prior_coverage"],
                         row["nearest_observer_distance"], residual, row["elapsed_sec"])
                del scores
            del coverage_spectrum, valid
            candidate_id, shift, count, distance_squared, row_index = choice
            if args.max_mean_prior is not None and float(best_key[0]) > args.max_mean_prior:
                stop_reason = "mean_prior_threshold_exceeded"
                log.info("Stopping: best mean prior coverage exceeds threshold.")
                break
            candidate_rows[row_index]["selected"] = 1
            accept(candidate_id, shift, count, distance_squared, time.perf_counter() - round_started)

        pairs = []
        for first in range(len(selected_shifts)):
            for second in range(first + 1, len(selected_shifts)):
                delta = (np.asarray(selected_shifts[first]) - selected_shifts[second] + args.nmesh // 2) % args.nmesh - args.nmesh // 2
                pairs.append({"observer_i": first, "observer_j": second,
                              "periodic_distance_mpc_h": float(np.linalg.norm(delta) * spacing)})
        write_csv(output / "selections.csv", selection_rows, ["observer_id"])
        write_csv(output / "search_candidates.csv", candidate_rows, ["observer_id", "candidate_id"])
        write_csv(output / "observer_distances.csv", pairs, ["observer_i", "observer_j", "periodic_distance_mpc_h"])
        observers = [[row["observer_x"], row["observer_y"], row["observer_z"]] for row in selection_rows]
        np.savez_compressed(output / "coverage.npz", coverage=coverage, box_size=args.box_size,
                            observers=np.asarray(observers), shifts=np.asarray(selected_shifts), rmin=rmin, rmax=rmax)
        plot_coverage(output / "coverage_projection.png", coverage, observers, args.box_size)
        final = {
            "num_observers": len(selection_rows), "target_num_observers": args.num_cones,
            "initial_num_observers": initial_count, "new_num_observers": len(selection_rows) - initial_count,
            "stop_reason": stop_reason, "box_covered_fraction": covered_voxels / total,
            "coverage_mean": coverage_sum / total,
            "coverage_variance": coverage_square_sum / total - (coverage_sum / total)**2,
            "max_voxel_coverage": max_coverage,
            "mean_selected_prior_coverage": float(np.mean([row["mean_prior_coverage"] for row in selection_rows])),
            "total_prior_coverage_sum": sum(row["prior_coverage_sum"] for row in selection_rows),
            "total_coverage_square_increment": coverage_square_sum,
            "mean_volume_relative_error": float(np.mean([row["volume_relative_error"] for row in selection_rows])),
            "mean_absolute_volume_relative_error": float(np.mean([abs(row["volume_relative_error"]) for row in selection_rows])),
            "max_absolute_volume_relative_error": max(abs(row["volume_relative_error"]) for row in selection_rows),
            "minimum_observer_distance": min((pair["periodic_distance_mpc_h"] for pair in pairs), default=None),
            "max_fft_rounding_residual": max((row["max_rounding_residual"] for row in candidate_rows), default=0.0),
            "peak_process_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
            "total_elapsed_sec": time.perf_counter() - started,
        }
        final["cumulative_elapsed_sec"] = previous_elapsed + final["total_elapsed_sec"]
        write_json(output / "result.json", {
            "format_version": 1, "method": "periodic_fft", "strategy": args.strategy,
            "resume_from": str(args.resume_from) if args.resume_from else None,
            "nmesh": args.nmesh, "box_size": args.box_size, "library_size": len(library),
            "shell": {"mode": range_mode, "input_range": input_range, "rmin": rmin, "rmax": rmax, "analytic_volume": analytic_volume},
            "mask": {"path": str(args.mask.resolve()), "nside": mask.nside, "values": args.mask_values, "area_sqdeg": area},
            "arguments": config, "versions": versions, "observers_wrapped": observers,
            "final_metrics": final, "selections": selection_records,
        })
        log.info("Finished: %s", json.dumps(final, ensure_ascii=False))
    finally:
        mask.close()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    resuming = any(token.split("=")[0] == "--resume-from" for token in argv)
    parser = build_resume_parser() if resuming else build_parser()
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if resuming:
        try:
            args = resume_arguments(args)
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))
    radial = args.z_range or args.r_range
    numbers = [args.x, args.y, args.z, args.box_size, args.min_observer_distance, *radial, *args.base_euler, *args.angles_deg]
    if args.max_mean_prior is not None:
        numbers.append(args.max_mean_prior)
    if not all(math.isfinite(value) for value in numbers):
        parser.error("Numeric inputs must be finite.")
    if args.box_size <= 0 or args.nmesh < 2 or args.num_cones < 1 or args.min_observer_distance < 0:
        parser.error("Require box_size > 0, nmesh >= 2, num_cones >= 1, and DMIN >= 0.")
    if radial[0] < 0 or radial[1] <= radial[0]:
        parser.error("Require 0 <= shell minimum < shell maximum.")
    if args.max_mean_prior is not None and args.max_mean_prior < 0:
        parser.error("--max-mean-prior must be nonnegative.")
    if args.candidate_count < 2 or args.pool_size < args.candidate_count:
        parser.error("Require pool-size >= candidate-count >= 2.")
    if args.angular_nside <= 0 or args.angular_nside & (args.angular_nside - 1):
        parser.error("--angular-nside must be a positive power of two.")
    if args.workers < 1 or args.chunk_size < 1:
        parser.error("--workers and --chunk-size must be positive.")
    if not args.mask.is_file():
        parser.error(f"Mask does not exist: {args.mask}")
    output = args.output_dir.absolute()
    if output.exists():
        parser.error(f"Output directory already exists: {output}")
    output.mkdir(parents=True)
    os.environ["MPLCONFIGDIR"] = str(output / "cache" / "matplotlib")
    os.environ["MPLBACKEND"] = "Agg"
    log = logging.getLogger("lightgen.fft")
    log.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s +0800 %(levelname)s %(message)s")
    formatter.converter = lambda value: datetime.fromtimestamp(value, timezone(timedelta(hours=8))).timetuple()
    for handler in [logging.FileHandler(output / "pipeline.log"), logging.StreamHandler(sys.stdout)]:
        handler.setFormatter(formatter)
        log.addHandler(handler)
    status, error = "failed", None
    try:
        run(args, output, log)
        status = "completed"
    except Exception as exc:
        error = str(exc)
        log.exception("FFT placement failed")
    finally:
        files = sorted(str(path.absolute()) for path in output.rglob("*") if path.is_file())
        files.append(str(output / "manifest.json"))
        write_json(output / "manifest.json", {
            "status": status, "error": error, "input_mask": str(args.mask.absolute()),
            "input_mask_resolved": str(args.mask.resolve()), "output_files": files,
            "resume_from": str(args.resume_from) if args.resume_from else None,
            "resume_inputs": [str(args.resume_from / name) for name in
                              ["result.json", "library.npz", "coverage.npz", "search_candidates.csv", "manifest.json"]]
                             if args.resume_from else [],
            "stdout_stderr": "terminal; INFO and captured exception traceback also in pipeline.log",
            "temporary_files": [], "checkpoints": [], "disk_fft_cache": [],
        })
        for handler in list(log.handlers):
            handler.close()
            log.removeHandler(handler)
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
