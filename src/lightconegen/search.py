"""Joint periodic-FFT observer/rotation search without file or plotting side effects."""

from fractions import Fraction
import logging
from pathlib import Path
import time

import numpy as np
from scipy import fft
from scipy.spatial.transform import Rotation

from .geometry import (
    Orientation, SkyMask, angular_directions, jaccard, make_library, mask_signature,
    matrix_to_angles, rotation_distance, shell_geometry, shifted_indices, using_mask,
)
from .models import Lightcone, LightconeLayout, SearchResult

_LOG = logging.getLogger(__name__)


def search_lightcones(boxsize, mask, *, z_range=None, r_range=None, observer=None,
                     nmesh=64, num_cones=5, strategy="axes", angles_deg=(30, 60, 90, 120),
                     base_euler=(0, 0, 0), candidate_count=13, pool_size=64, angular_nside=32,
                     seed=20261115, min_observer_distance=0, max_mean_prior=None,
                     workers=8, chunk_size=262144, result_mode="layout", cosmology="HR4"):
    """Search one shell; result_mode controls retained results, not the optimizer.

    observer defaults to the box center. The first cone uses base_euler, all
    lengths are Mpc/h, and num_cones includes this fixed first cone. mask can
    be a FITS path or a caller-owned SkyMask. No output files are created.
    """
    observer = tuple(observer) if observer is not None else (boxsize / 2,) * 3
    config = {
        "x": observer[0], "y": observer[1], "z": observer[2], "box_size": boxsize,
        "z_range": list(z_range) if z_range is not None else None,
        "r_range": list(r_range) if r_range is not None else None,
        "nmesh": nmesh, "num_cones": num_cones, "strategy": strategy,
        "angles_deg": list(angles_deg), "base_euler": list(base_euler),
        "candidate_count": candidate_count, "pool_size": pool_size,
        "angular_nside": angular_nside, "seed": seed,
        "min_observer_distance": min_observer_distance, "max_mean_prior": max_mean_prior,
        "workers": workers, "chunk_size": chunk_size, "cosmology": cosmology,
    }
    return _search(config, mask, result_mode)


def resume_search(source, num_cones, *, mask=None, result_mode="full", workers=None,
                  chunk_size=None, max_mean_prior=None):
    """Continue a full SearchResult or completed full-result directory."""
    from .io import load_result

    previous = source if isinstance(source, SearchResult) else load_result(source)
    if previous.mode != "full" or previous.library is None or previous.coverage is None:
        raise ValueError("Resume needs a full result with coverage and its original candidate library.")
    if num_cones <= len(previous.layout.lightcones):
        raise ValueError("num_cones must exceed the number of saved windows.")
    config = previous.arguments.copy()
    config["num_cones"] = num_cones
    config.setdefault("cosmology", "HR4")
    for name, value in [("workers", workers), ("chunk_size", chunk_size), ("max_mean_prior", max_mean_prior)]:
        if value is not None:
            config[name] = value
    if mask is None:
        mask = config.get("mask", previous.layout.mask)
    if not isinstance(mask, SkyMask):
        with SkyMask(mask, values=previous.mask_info.get("values", (4,))) as resumed_mask:
            return _search(config, resumed_mask, result_mode, previous)
    return _search(config, mask, result_mode, previous)


def _validate(config, result_mode):
    if result_mode not in ("layout", "full"):
        raise ValueError("result_mode must be 'layout' or 'full'.")
    if config["strategy"] not in ("base", "axes", "random", "mask-diverse"):
        raise ValueError("strategy must be base, axes, random or mask-diverse.")
    if (config["z_range"] is None) == (config["r_range"] is None):
        raise ValueError("Supply exactly one of z_range or r_range.")
    radial = config["z_range"] if config["z_range"] is not None else config["r_range"]
    numbers = [config[key] for key in ("box_size", "x", "y", "z", "min_observer_distance")]
    numbers += [*radial, *config["angles_deg"], *config["base_euler"]]
    if config["max_mean_prior"] is not None:
        numbers.append(config["max_mean_prior"])
    if not np.isfinite(numbers).all():
        raise ValueError("Numeric inputs must be finite.")
    if config["box_size"] <= 0 or len(radial) != 2 or not 0 <= radial[0] < radial[1]:
        raise ValueError("Require boxsize > 0 and 0 <= shell minimum < shell maximum.")
    if len(config["base_euler"]) != 3:
        raise ValueError("base_euler must contain three angles in degrees.")
    for key, minimum in [("nmesh", 2), ("num_cones", 1), ("workers", 1), ("chunk_size", 1)]:
        if not isinstance(config[key], (int, np.integer)) or config[key] < minimum:
            raise ValueError(f"{key} must be an integer >= {minimum}.")
    if config["min_observer_distance"] < 0 or (config["max_mean_prior"] is not None and config["max_mean_prior"] < 0):
        raise ValueError("Distance and overlap thresholds must be nonnegative.")
    if config["candidate_count"] < 2 or config["pool_size"] < config["candidate_count"]:
        raise ValueError("Require pool_size >= candidate_count >= 2.")
    nside = config["angular_nside"]
    if not isinstance(nside, (int, np.integer)) or nside <= 0 or nside & (nside - 1):
        raise ValueError("angular_nside must be a positive power of two.")


def _make_library(config, mask, base):
    directions = angular_directions(config["angular_nside"])
    strategy = "axes" if config["strategy"] == "base" else config["strategy"]
    angles = [] if config["strategy"] == "base" else config["angles_deg"]
    count = config["pool_size"] if strategy == "random" else config["candidate_count"]
    library, signatures = make_library(
        strategy, base, angles, count, config["pool_size"], np.random.default_rng(config["seed"]), mask, directions,
    )
    if strategy == "random":
        library = library[:config["candidate_count"]]
        signatures = signatures[:config["candidate_count"]]
    return library, signatures


def _update_nearest_squared(nearest, shift):
    nmesh = nearest.shape[0]
    axes = []
    for value in shift:
        delta = (np.arange(nmesh, dtype=np.int64) - value + nmesh // 2) % nmesh - nmesh // 2
        axes.append(delta * delta)
    yz = axes[1][:, None] + axes[2][None, :]
    for start in range(0, nmesh, 8):
        stop = min(start + 8, nmesh)
        np.minimum(nearest[start:stop], axes[0][start:stop, None, None] + yz, out=nearest[start:stop])


def _restore_integer_scores(scores):
    residual = 0.0
    for start in range(0, scores.shape[0], 8):
        block = scores[start:start + 8]
        rounded = np.rint(block)
        residual = max(residual, float(np.max(np.abs(block - rounded))))
        np.maximum(rounded, 0, out=block)
    if residual >= 0.25:
        raise ArithmeticError(f"FFT residual {residual:g} is too large to restore integer overlap counts.")
    return residual


def _best_translation(scores, nearest, valid):
    scores[~valid] = np.inf
    count = int(scores.min())
    tied = scores == count
    distance_squared = int(np.max(nearest, where=tied, initial=-1))
    tied &= nearest == distance_squared
    return count, distance_squared, int(tied.argmax())


def _search(config, mask, result_mode, previous=None):
    _validate(config, result_mode)
    started = time.perf_counter()
    nmesh, boxsize = config["nmesh"], config["box_size"]
    shape = (nmesh,) * 3
    total = nmesh**3
    spacing = boxsize / nmesh
    anchor = np.asarray([config[axis] for axis in "xyz"], dtype=float) % boxsize
    base = Rotation.from_euler("xyz", config["base_euler"], degrees=True).as_matrix()
    with using_mask(mask) as sky_mask:
        config = {**config, "mask": str(sky_mask.path.absolute())}
        layout = LightconeLayout(float(boxsize), nmesh, sky_mask.path.name, [],
                                 tuple(config["z_range"]) if config["z_range"] is not None else None,
                                 tuple(config["r_range"]) if config["r_range"] is not None else None,
                                 config["cosmology"])
        rmin, rmax = layout.radial_range
        if not 0 <= rmin < rmax <= boxsize / 2:
            raise ValueError("Shell must satisfy 0 <= rmin < rmax <= boxsize/2.")
        area = sky_mask.area()
        if not area:
            raise ValueError("No mask pixels match the accepted labels.")
        analytic_volume = area * (np.pi / 180)**2 * (rmax**3 - rmin**3) / 3
        if previous is None:
            library, signatures = _make_library(config, sky_mask, base)
        else:
            library = [Orientation(str(label), matrix) for label, matrix in
                       zip(previous.library["labels"], previous.library["matrices_sky_to_box"])]
            signatures = previous.library["angular_signatures"]
        matrices = np.asarray([item.matrix for item in library])
        angles = [matrix_to_angles(matrix) for matrix in matrices]
        indices, directions = shell_geometry(boxsize, nmesh, anchor, rmin, rmax, config["chunk_size"])
        spectra, templates, reference_intersections = [], [], []
        reference = np.zeros(total, dtype=bool)
        for candidate_id, orientation in enumerate(library):
            occupied = indices[mask_signature(sky_mask, directions, orientation.matrix)]
            if not occupied.size:
                raise ValueError(f"Empty template {orientation.label}; increase nmesh.")
            if previous is not None and occupied.size != previous.library["occupied_voxels"][candidate_id]:
                raise ValueError("The current mask does not reproduce the saved template sizes.")
            if candidate_id == 0:
                reference[occupied] = True
            reference_intersections.append(int(np.count_nonzero(reference[occupied])))
            templates.append(occupied)
            window = np.zeros(shape, dtype=bool)
            window.ravel()[occupied] = True
            spectrum = fft.rfftn(window, workers=config["workers"])
            np.conjugate(spectrum, out=spectrum)
            spectra.append(spectrum)
            _LOG.info("Built template %s: %d occupied voxels", orientation.label, occupied.size)
        del indices, directions, reference, window, spectrum
        coverage = np.zeros(shape, dtype=np.uint32)
        nearest = np.full(shape, np.iinfo(np.int64).max, dtype=np.int64)
        records, history = [], []
        previous_elapsed = 0.0
        if previous is not None:
            for cone, row in zip(previous.layout.lightcones, previous.selections):
                occupied = shifted_indices(templates[row["candidate_id"]], cone.shift, nmesh)
                if int(coverage.ravel()[occupied].sum(dtype=np.uint64)) != row["prior_coverage_sum"]:
                    raise ValueError("The current mask does not reproduce the saved overlap history.")
                coverage.ravel()[occupied] += 1
                _update_nearest_squared(nearest, cone.shift)
            if not np.array_equal(coverage, previous.coverage):
                raise ValueError("The current geometry does not reproduce the saved coverage.")
            layout.lightcones.extend(previous.layout.lightcones)
            records = [row.copy() for row in previous.selections]
            if result_mode == "full":
                history = [row.copy() for row in previous.candidates]
            previous_elapsed = previous.final_metrics.get("cumulative_elapsed_sec", previous.final_metrics["total_elapsed_sec"])
        initial_count = len(layout.lightcones)
        covered_voxels = int(np.count_nonzero(coverage))
        coverage_sum = sum(row["occupied_voxels"] for row in records)
        coverage_square_sum = sum(row["coverage_square_increment"] for row in records)
        max_coverage = int(coverage.max())
        max_residual = previous.final_metrics.get("max_fft_rounding_residual", 0.0) if previous else 0.0

        def accept(candidate_id, shift, expected_count, distance_squared, elapsed):
            nonlocal covered_voxels, coverage_sum, coverage_square_sum, max_coverage
            occupied = shifted_indices(templates[candidate_id], shift, nmesh)
            prior = coverage.ravel()[occupied]
            prior_sum = int(prior.sum(dtype=np.uint64))
            if prior_sum != expected_count:
                raise ArithmeticError("Selected window count differs from its FFT count.")
            size = len(occupied)
            new_voxels = int(np.count_nonzero(prior == 0))
            covered_voxels += new_voxels
            coverage_sum += size
            increment = 2 * prior_sum + size
            coverage_square_sum += increment
            max_coverage = max(max_coverage, int(prior.max()) + 1)
            coverage.ravel()[occupied] += 1
            observer = tuple(float(value) for value in (anchor + np.asarray(shift) * spacing) % boxsize)
            intersection = reference_intersections[candidate_id]
            row = {
                "observer_id": len(layout.lightcones),
                **{f"observer_{axis}": value for axis, value in zip("xyz", observer)},
                **{f"shift_{axis}": int(value) for axis, value in zip("xyz", shift)},
                "candidate_id": candidate_id, "label": library[candidate_id].label,
                "rotation_from_base_deg": rotation_distance(matrices[candidate_id], base),
                "angular_iou_with_base": jaccard(signatures[candidate_id], signatures[0]),
                "occupied_voxels": size, "prior_coverage_sum": prior_sum,
                "mean_prior_coverage": prior_sum / size, "new_voxels": new_voxels,
                "covered_before_voxels": size - new_voxels, "coverage_square_increment": increment,
                "reference_intersection_voxels": intersection,
                "reference_iou": intersection / (size + len(templates[0]) - intersection),
                "reference_overlap_fraction": intersection / len(templates[0]),
                "nearest_observer_distance": float(np.sqrt(distance_squared) * spacing) if distance_squared is not None else None,
                "volume_mpc_h_cubed": size * spacing**3,
                "volume_relative_error": size * spacing**3 / analytic_volume - 1,
                "box_covered_fraction": covered_voxels / total, "coverage_mean": coverage_sum / total,
                "coverage_variance": coverage_square_sum / total - (coverage_sum / total)**2,
                "elapsed_sec": elapsed,
                "matrix_sky_to_box": matrices[candidate_id].tolist(),
                "quaternion_xyzw": Rotation.from_matrix(matrices[candidate_id]).as_quat().tolist(),
            }
            records.append(row)
            layout.lightcones.append(Lightcone(observer, angles[candidate_id], tuple(int(value) for value in shift)))
            _update_nearest_squared(nearest, shift)
            _LOG.info("Accepted observer %d, orientation %s, mean prior %.8g",
                      row["observer_id"], row["label"], row["mean_prior_coverage"])

        if previous is None:
            accept(0, (0, 0, 0), 0, None, time.perf_counter() - started)
        stop_reason = "target_reached"
        for observer_id in range(len(layout.lightcones), config["num_cones"]):
            round_started = time.perf_counter()
            valid = nearest >= (config["min_observer_distance"] / spacing)**2
            valid_count = int(np.count_nonzero(valid))
            if not valid_count:
                stop_reason = "no_legal_position"
                break
            coverage_spectrum = fft.rfftn(coverage.astype(np.float64), workers=config["workers"])
            best_key, choice = None, None
            for candidate_id, spectrum in enumerate(spectra):
                stamp = time.perf_counter()
                scores = fft.irfftn(coverage_spectrum * spectrum, s=shape, workers=config["workers"], overwrite_x=True)
                residual = _restore_integer_scores(scores)
                max_residual = max(max_residual, residual)
                count, distance_squared, flat_index = _best_translation(scores, nearest, valid)
                shift = tuple(int(value) for value in np.unravel_index(flat_index, shape))
                key = (Fraction(count, len(templates[candidate_id])), -distance_squared, flat_index, candidate_id)
                row = {"observer_id": observer_id, "candidate_id": candidate_id,
                       "label": library[candidate_id].label, "legal_positions": valid_count,
                       **{f"shift_{axis}": value for axis, value in zip("xyz", shift)},
                       "prior_coverage_sum": count, "occupied_voxels": len(templates[candidate_id]),
                       "mean_prior_coverage": count / len(templates[candidate_id]),
                       "nearest_observer_distance": float(np.sqrt(distance_squared) * spacing),
                       "max_rounding_residual": residual, "selected": 0,
                       "elapsed_sec": time.perf_counter() - stamp}
                if result_mode == "full":
                    history.append(row)
                if best_key is None or key < best_key:
                    best_key, choice = key, (candidate_id, shift, count, distance_squared, row)
                del scores
            del coverage_spectrum, valid
            if config["max_mean_prior"] is not None and float(best_key[0]) > config["max_mean_prior"]:
                stop_reason = "mean_prior_threshold_exceeded"
                break
            candidate_id, shift, count, distance_squared, row = choice
            row["selected"] = 1
            accept(candidate_id, shift, count, distance_squared, time.perf_counter() - round_started)

        if result_mode == "layout":
            return SearchResult(layout, "layout", stop_reason)
        from .io import _observer_distances

        pairs = _observer_distances(layout)
        metrics = {
            "num_observers": len(layout.lightcones), "target_num_observers": config["num_cones"],
            "initial_num_observers": initial_count, "new_num_observers": len(layout.lightcones) - initial_count,
            "stop_reason": stop_reason, "box_covered_fraction": covered_voxels / total,
            "coverage_mean": coverage_sum / total,
            "coverage_variance": coverage_square_sum / total - (coverage_sum / total)**2,
            "max_voxel_coverage": max_coverage,
            "mean_selected_prior_coverage": float(np.mean([row["mean_prior_coverage"] for row in records])),
            "total_prior_coverage_sum": sum(row["prior_coverage_sum"] for row in records),
            "total_coverage_square_increment": coverage_square_sum,
            "mean_volume_relative_error": float(np.mean([row["volume_relative_error"] for row in records])),
            "mean_absolute_volume_relative_error": float(np.mean([abs(row["volume_relative_error"]) for row in records])),
            "max_absolute_volume_relative_error": max(abs(row["volume_relative_error"]) for row in records),
            "minimum_observer_distance": min((pair["periodic_distance_mpc_h"] for pair in pairs), default=None),
            "max_fft_rounding_residual": max_residual, "total_elapsed_sec": time.perf_counter() - started,
        }
        metrics["cumulative_elapsed_sec"] = previous_elapsed + metrics["total_elapsed_sec"]
        return SearchResult(
            layout, "full", stop_reason, coverage,
            {"matrices_sky_to_box": matrices, "quaternions_xyzw": Rotation.from_matrix(matrices).as_quat(),
             "labels": np.asarray([item.label for item in library]),
             "occupied_voxels": np.asarray([len(item) for item in templates]), "angular_signatures": signatures},
            records, history, config, metrics,
            {"path": str(sky_mask.path.resolve()), "nside": sky_mask.nside, "values": sky_mask.values.tolist(), "area_sqdeg": area},
        )
