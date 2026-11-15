#!/usr/bin/env python3
"""Explore masked-shell orientations at prescribed observers without FFT."""

import argparse
import csv
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        usage="%(prog)s X Y Z BOXSIZE --mask MASK --nmesh N [N ...] "
              "(--z-range ZMIN ZMAX | --r-range RMIN RMAX) "
              "--output-dir OUTPUT_DIR [options]",
    )
    parser.add_argument("x", type=float, metavar="X", help="First observer x coordinate in Mpc/h.")
    parser.add_argument("y", type=float, metavar="Y", help="First observer y coordinate in Mpc/h.")
    parser.add_argument("z", type=float, metavar="Z", help="First observer z coordinate in Mpc/h.")
    parser.add_argument("box_size", type=float, metavar="BOXSIZE", help="Periodic box side in Mpc/h.")
    parser.add_argument("--mask", type=Path, required=True, help="Full HEALPix FITS mask; first table field.")
    parser.add_argument("--mask-values", type=int, nargs="+", default=[4], help="Accepted pixel labels; BGS default: 4.")
    parser.add_argument("--nmesh", type=int, nargs="+", required=True, help="Grid cells per axis; can compare several grids.")
    parser.add_argument("--observer", type=float, nargs=3, action="append", default=[], metavar=("X", "Y", "Z"), help="Additional observer in Mpc/h; repeat in placement order after the positional observer.")
    radial = parser.add_mutually_exclusive_group(required=True)
    radial.add_argument("--z-range", type=float, nargs=2, action="append", metavar=("ZMIN", "ZMAX"), help="Observed-redshift interval; repeat for separate shells. HR4 Omega_m=0.26.")
    radial.add_argument("--r-range", type=float, nargs=2, action="append", metavar=("RMIN", "RMAX"), help="Direct radial interval in Mpc/h; repeat for separate shells.")
    parser.add_argument("--strategies", nargs="+", choices=["axes", "random", "mask-diverse"], default=["axes", "random", "mask-diverse"])
    parser.add_argument("--angles-deg", type=float, nargs="+", default=[30, 60, 90, 120, 150, 180], help="Box-axis angles for axes strategy; identity is always included.")
    parser.add_argument("--candidate-count", type=int, default=12, help="Including identity/base, for random and mask-diverse.")
    parser.add_argument("--pool-size", type=int, default=64, help="Initial random pool for mask-diverse, including base.")
    parser.add_argument("--angular-nside", type=int, default=32, help="Equal-area angular sample grid; the input mask retains its original NSIDE.")
    parser.add_argument("--base-euler", type=float, nargs=3, default=[0, 0, 0], metavar=("X", "Y", "Z"), help="Extrinsic xyz Euler angles in degrees; matrix maps sky vectors into box vectors.")
    parser.add_argument("--refine-steps", type=float, nargs="+", default=[], help="Optional local angle steps, e.g. 3 1; each tests +/- rotations about all box axes.")
    parser.add_argument("--refine-rounds", type=int, default=2, help="Maximum accepted-neighbor search rounds per local angle step.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=262144, help="Grid centers generated per in-memory chunk.")
    parser.add_argument("--save-windows", action="store_true", help="Also save bit-packed occupancy for all evaluated candidates.")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True, help="A new run directory; existing paths are never overwritten.")
    return parser


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def scan_plot(path, rows, selected_index):
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for label in dict.fromkeys(row["axis"] or row["stage"] for row in rows):
        group = [r for r in rows if (r["axis"] or r["stage"]) == label]
        x = [r["rotation_from_base_deg"] for r in group]
        axes[0].scatter(x, [r["reference_iou"] for r in group], label=label, s=22)
        axes[1].scatter(x, [r["mean_prior_coverage"] if np.isfinite(r["mean_prior_coverage"]) else np.nan for r in group], label=label, s=22)
    selected = rows[selected_index]
    for ax, key in zip(axes, ("reference_iou", "mean_prior_coverage")):
        ax.scatter(selected["rotation_from_base_deg"], selected[key], marker="*", s=150, color="black", label="selected")
        ax.set_xlabel("Rotation angle from base (deg)")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("Voxel IoU with base at this observer")
    axes[1].set_ylabel("Mean previous coverage inside candidate")
    axes[1].legend(fontsize=8)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def projection_plot(path, coverage, box_size, observers):
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    for ax, collapsed in zip(axes, range(3)):
        remaining = [i for i in range(3) if i != collapsed]
        image = ax.imshow(coverage.sum(axis=collapsed).T, origin="lower", extent=[0, box_size, 0, box_size], cmap="viridis")
        points = np.asarray(observers)
        ax.scatter(points[:, remaining[0]], points[:, remaining[1]], marker="+", color="red", s=24)
        ax.set_xlabel("xyz"[remaining[0]] + " (Mpc/h)")
        ax.set_ylabel("xyz"[remaining[1]] + " (Mpc/h)")
        fig.colorbar(image, ax=ax, label="Summed coverage along " + "xyz"[collapsed], shrink=0.7)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(args, output):
    import numpy as np
    from scipy.spatial.transform import Rotation
    from orientation_geometry import (
        Orientation, SkyMask, angular_directions, angular_overlap,
        axis_rotation, comoving_distance, evaluate_window, jaccard,
        make_library, mask_signature, occupied_window, overlap_matrices,
        rotation_distance, shell_geometry,
    )

    log = logging.getLogger("orientation")
    base = Rotation.from_euler("xyz", args.base_euler, degrees=True).as_matrix()
    observers = np.asarray(args.observer) % args.box_size
    intervals = args.z_range or args.r_range
    shells = []
    for interval in intervals:
        if args.z_range:
            rmin, rmax = [comoving_distance(z) for z in interval]
        else:
            rmin, rmax = interval
        if not 0 <= rmin < rmax <= args.box_size / 2:
            raise ValueError("Each shell must satisfy 0 <= rmin < rmax <= box_size/2; use --r-range for a smaller box.")
        shells.append({"input_range": interval, "rmin": rmin, "rmax": rmax})

    mask = SkyMask(args.mask, args.mask_values)
    try:
        area = mask.area()
        if area == 0:
            raise ValueError("No mask pixels match --mask-values.")
        log.info("Mask: %s; NSIDE=%d; values=%s; area=%.8f deg^2", mask.path, mask.nside, args.mask_values, area)
        directions = angular_directions(args.angular_nside)
        base_signature = mask_signature(mask, directions, base)
        libraries = {}
        library_root = output / "libraries"
        library_root.mkdir()
        for name in args.strategies:
            rng = np.random.default_rng(np.random.SeedSequence([args.seed, ["axes", "random", "mask-diverse"].index(name)]))
            orientations, signatures = make_library(
                name, base, args.angles_deg, args.candidate_count,
                args.pool_size, rng, mask, directions,
            )
            libraries[name] = (orientations, signatures)
            np.savez_compressed(
                library_root / f"{name}.npz",
                matrices_sky_to_box=np.asarray([o.matrix for o in orientations]),
                quaternions_xyzw=Rotation.from_matrix(np.asarray([o.matrix for o in orientations])).as_quat(),
                labels=np.asarray([o.label for o in orientations]),
                angular_signatures=signatures,
                angular_iou=angular_overlap(signatures),
                angular_nside=args.angular_nside,
            )
            log.info("Strategy %s: %d library orientations", name, len(orientations))
        config = {key: str(value.absolute()) if isinstance(value, Path) else value for key, value in vars(args).items()}
        write_json(output / "run.json", {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "arguments": config, "observers_wrapped": observers.tolist(),
            "shells": shells, "omega_m": 0.26, "distance_unit": "Mpc/h",
            "mask_resolved": str(args.mask.resolve()), "mask_header": mask.header,
            "mask_area_sqdeg": area, "mask_size_bytes": args.mask.stat().st_size,
            "mask_mtime_ns": args.mask.stat().st_mtime_ns,
            "sky_frame": "Native mask axes; supplied BGS map is queried as equatorial RA/DEC",
            "selection_objective": "mean_prior_coverage; stable ties choose first candidate",
            "rotation_convention": "column v_box = Q @ v_sky; row sky_direction = box_direction @ Q",
            "grid_convention": "centers (i+0.5)*L/nmesh; C-order axes x,y,z; minimum-image PBC; rmin <= r < rmax",
            "versions": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "astropy", "healpy", "matplotlib")},
            "source_files": [str(Path(__file__).absolute()), str(Path(__file__).with_name("orientation_geometry.py").absolute())],
        })
        summary = []
        for shell_index, shell in enumerate(shells):
            analytic_volume = area * (np.pi / 180)**2 * (shell["rmax"]**3 - shell["rmin"]**3) / 3
            for nmesh in args.nmesh:
                total = nmesh**3
                voxel_volume = (args.box_size / nmesh)**3
                coverages = {name: np.zeros(total, dtype=np.uint32) for name in args.strategies}
                selections = {name: [] for name in args.strategies}
                for observer_index, observer in enumerate(observers):
                    log.info("Shell %d, nmesh=%d, observer=%d %s", shell_index, nmesh, observer_index, observer.tolist())
                    indices, shell_directions = shell_geometry(
                        args.box_size, nmesh, observer, shell["rmin"],
                        shell["rmax"], args.chunk_size,
                    )
                    reference = occupied_window(mask, indices, shell_directions, base, total)
                    for name, (library, signatures) in libraries.items():
                        folder = output / f"shell_{shell_index:02d}" / f"nmesh_{nmesh:04d}" / name / f"observer_{observer_index:03d}"
                        folder.mkdir(parents=True)
                        coverage = coverages[name]
                        rows, packed, tested = [], [], []

                        def evaluate(orientation, signature=None):
                            occupied = occupied_window(mask, indices, shell_directions, orientation.matrix, total)
                            metrics = evaluate_window(occupied, coverage, reference)
                            if signature is None:
                                signature = mask_signature(mask, directions, orientation.matrix)
                            row = {
                                "candidate_id": len(rows), "label": orientation.label,
                                "stage": orientation.stage, "axis": orientation.axis,
                                "axis_angle_deg": orientation.angle_deg,
                                "rotation_from_base_deg": rotation_distance(orientation.matrix, base),
                                "angular_iou_with_base": jaccard(signature, base_signature),
                                **metrics,
                                "volume_mpc_h_cubed": metrics["occupied_voxels"] * voxel_volume,
                                "volume_relative_error": metrics["occupied_voxels"] * voxel_volume / analytic_volume - 1,
                            }
                            rows.append(row)
                            packed.append(np.packbits(occupied))
                            tested.append(orientation)
                            return len(rows) - 1

                        for orientation, signature in zip(library, signatures):
                            evaluate(orientation, signature)
                        best = min(range(len(rows)), key=lambda i: rows[i]["mean_prior_coverage"])
                        if not np.isfinite(rows[best]["mean_prior_coverage"]):
                            raise ValueError(f"No occupied voxels at {folder}; increase nmesh or check mask/range.")
                        for step in args.refine_steps:
                            for turn in range(args.refine_rounds):
                                current = best
                                pivot = tested[current].matrix
                                for axis in "xyz":
                                    for sign in (-1, 1):
                                        candidate = Orientation(
                                            f"local_{step:g}_{turn}_{axis}_{sign:+d}",
                                            axis_rotation(axis, sign * step) @ pivot,
                                            axis, sign * step, "local",
                                        )
                                        idx = evaluate(candidate)
                                        if rows[idx]["mean_prior_coverage"] < rows[best]["mean_prior_coverage"] - 1e-12:
                                            best = idx
                                if current == best:
                                    break
                        for i, row in enumerate(rows):
                            row["selected"] = int(i == best)
                        write_csv(folder / "candidates.csv", rows)
                        intersection, iou = overlap_matrices(packed, [r["occupied_voxels"] for r in rows])
                        matrices = np.asarray([o.matrix for o in tested])
                        np.savez_compressed(
                            folder / "overlap.npz", intersection_voxels=intersection,
                            iou=iou, matrices_sky_to_box=matrices,
                            quaternions_xyzw=Rotation.from_matrix(matrices).as_quat(),
                            labels=np.asarray([o.label for o in tested]), selected_index=best,
                        )
                        if args.save_windows:
                            np.savez_compressed(folder / "windows.npz", packed=np.asarray(packed), nmesh=nmesh, bitorder="big", order="C")
                        chosen = np.unpackbits(packed[best], count=total).astype(bool)
                        coverage[chosen] += 1
                        selection = {
                            "shell_id": shell_index, "nmesh": nmesh, "strategy": name,
                            "observer_id": observer_index, "observer_x": observer[0],
                            "observer_y": observer[1], "observer_z": observer[2],
                            **rows[best],
                            "box_covered_fraction": float(np.count_nonzero(coverage) / total),
                            "coverage_mean": float(coverage.mean()),
                            "coverage_variance": float(coverage.var()),
                        }
                        selections[name].append(selection)
                        summary.append(selection)
                        if not args.no_plots:
                            scan_plot(folder / "orientation_scan.png", rows, best)
                        log.info("%s: selected %s; mean prior=%.5f; box covered=%.5f", name, rows[best]["label"], rows[best]["mean_prior_coverage"], selection["box_covered_fraction"])
                for name in args.strategies:
                    folder = output / f"shell_{shell_index:02d}" / f"nmesh_{nmesh:04d}" / name
                    write_csv(folder / "selections.csv", selections[name])
                    cube = coverages[name].reshape((nmesh,) * 3)
                    np.savez_compressed(
                        folder / "coverage.npz", coverage=cube,
                        box_size=args.box_size, observers=observers,
                        rmin=shell["rmin"], rmax=shell["rmax"],
                    )
                    if not args.no_plots:
                        projection_plot(folder / "coverage_projection.png", cube, args.box_size, observers)
        write_csv(output / "summary.csv", summary)
    finally:
        mask.close()


def main(argv=None):
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    import math

    args.observer = [[args.x, args.y, args.z], *args.observer]
    numbers = [args.box_size, *args.base_euler, *args.angles_deg, *args.refine_steps]
    numbers += [v for row in args.observer for v in row]
    numbers += [v for row in (args.z_range or args.r_range) for v in row]
    if not all(math.isfinite(v) for v in numbers) or args.box_size <= 0:
        parser.error("All numeric inputs must be finite and box-size must be positive.")
    if any(n < 2 for n in args.nmesh) or len(set(args.nmesh)) != len(args.nmesh):
        parser.error("--nmesh values must be distinct integers >= 2.")
    if any(a < 0 or b <= a for a, b in (args.z_range or args.r_range)):
        parser.error("Radial or redshift intervals must satisfy 0 <= min < max.")
    if args.candidate_count < 2 or args.pool_size < args.candidate_count:
        parser.error("Require pool-size >= candidate-count >= 2.")
    if args.angular_nside <= 0 or args.angular_nside & (args.angular_nside - 1):
        parser.error("--angular-nside must be a positive power of two.")
    if args.chunk_size <= 0 or args.refine_rounds < 1 or any(s <= 0 for s in args.refine_steps):
        parser.error("Chunk size, refinement rounds and angle steps must be positive.")
    if len(set(args.strategies)) != len(args.strategies):
        parser.error("Strategies must not be repeated.")
    if not args.mask.is_file():
        parser.error(f"Mask file does not exist: {args.mask}")
    output = args.output_dir.absolute()
    if output.exists():
        parser.error(f"Output directory already exists; choose a new path: {output}")
    output.mkdir(parents=True)
    os.environ["MPLCONFIGDIR"] = str(output / "cache" / "matplotlib")
    os.environ["MPLBACKEND"] = "Agg"
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(output / "pipeline.log"), logging.StreamHandler(sys.stdout)],
    )
    logging.captureWarnings(True)
    status = "completed"
    code = 0
    try:
        run(args, output)
    except Exception:
        logging.exception("Geometry experiment failed; partial outputs are retained.")
        status, code = "failed", 1
    logging.info("Run %s: %s", status, output)
    inputs = [str(args.mask.absolute()), str(args.mask.resolve()), str(Path(__file__).absolute()), str(Path(__file__).with_name("orientation_geometry.py").absolute())]
    files = sorted(str(p) for p in output.rglob("*") if p.is_file())
    files.append(str(output / "manifest.json"))
    write_json(output / "manifest.json", {
        "status": status, "inputs": inputs, "outputs": sorted(files),
        "stdout": "Emitted to the invoking terminal; logging messages are also in pipeline.log.",
        "stderr": "No separate file; captured warnings and caught exceptions are in pipeline.log.",
        "temporary_files": "No application temporary files or checkpoints; intermediate arrays remain in memory.",
        "cache": str(output / "cache" / "matplotlib"),
        "overwrite_policy": "Existing output directories are rejected; failed runs retain partial files.",
    })
    return code


if __name__ == "__main__":
    raise SystemExit(main())
