#!/usr/bin/env python3
"""Fast single-strategy orientation test on a single periodic voxel grid."""

import argparse
import csv
import json
import math
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        usage="%(prog)s X Y Z BOXSIZE --mask MASK --nmesh N "
              "(--z-range ZMIN ZMAX | --r-range RMIN RMAX) "
              "--strategy {axes,random,mask-diverse} --output-dir OUTPUT_DIR [options]",
    )
    parser.add_argument("x", type=float, metavar="X", help="First observer x coordinate in Mpc/h.")
    parser.add_argument("y", type=float, metavar="Y", help="First observer y coordinate in Mpc/h.")
    parser.add_argument("z", type=float, metavar="Z", help="First observer z coordinate in Mpc/h.")
    parser.add_argument("box_size", type=float, metavar="BOXSIZE", help="Periodic box side in Mpc/h.")
    parser.add_argument("--mask", type=Path, required=True, help="Full HEALPix FITS mask; first table field.")
    parser.add_argument("--mask-values", type=int, nargs="+", default=[4], help="Accepted pixel labels; BGS default: 4.")
    parser.add_argument("--nmesh", type=int, required=True, help="Grid cells per axis (>= 2).")
    parser.add_argument(
        "--observer", type=float, nargs=3, action="append", default=[],
        metavar=("X", "Y", "Z"),
        help="Additional observer in Mpc/h; repeat in placement order after the positional observer.",
    )
    radial = parser.add_mutually_exclusive_group(required=True)
    radial.add_argument("--z-range", type=float, nargs=2, metavar=("ZMIN", "ZMAX"), help="Observed-redshift interval (HR4 Omega_m=0.26).")
    radial.add_argument("--r-range", type=float, nargs=2, metavar=("RMIN", "RMAX"), help="Direct radial interval in Mpc/h.")
    parser.add_argument("--strategy", choices=["axes", "random", "mask-diverse"], required=True, help="Single orientation candidate strategy to test.")
    parser.add_argument("--angles-deg", type=float, nargs="+", default=[30, 60, 90, 120, 150, 180], help="Box-axis angles for axes strategy; identity is always included.")
    parser.add_argument("--candidate-count", type=int, default=12, help="Including base, for random and mask-diverse.")
    parser.add_argument("--pool-size", type=int, default=64, help="Initial random pool for mask-diverse, including base.")
    parser.add_argument("--angular-nside", type=int, default=32, help="Equal-area angular sample grid for candidate library.")
    parser.add_argument("--base-euler", type=float, nargs=3, default=[0, 0, 0], metavar=("X", "Y", "Z"), help="Extrinsic xyz Euler angles in degrees.")
    parser.add_argument("--refine-steps", type=float, nargs="+", default=[], help="Optional local angle steps in degrees.")
    parser.add_argument("--refine-rounds", type=int, default=2, help="Max neighbor-search rounds per local angle step.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=262144, help="Grid centers generated per in-memory chunk.")
    parser.add_argument("--save-candidates", action="store_true", help="Also save candidate tables and rotation matrices for each observer.")
    parser.add_argument("--save-coverage", action="store_true", help="Also write final 3D coverage cube to coverage.npz.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory; existing paths are rejected.")
    return parser


def json_safe(value):
    """Convert non-finite floats to None so strict JSON serialization succeeds."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def write_json(path, payload):
    path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def print_run_summary(summary_payload, selection_rows, output):
    shell = summary_payload["shell"]
    print(
        f"[eval_strategy] strategy={summary_payload['strategy']}  "
        f"nmesh={summary_payload['nmesh']}  "
        f"r=[{shell['rmin']:.2f}, {shell['rmax']:.2f}) Mpc/h  "
        f"library={summary_payload['library_size']}  "
        f"refine={summary_payload['arguments']['refine_steps'] or 'none'}  "
        f"seed={summary_payload['arguments']['seed']}"
    )
    header = (
        f"{'obs':>3}  {'label':<20}  {'rot_deg':>7}  {'mean_prior':>10}  "
        f"{'prior_sum':>10}  {'new_vox':>8}  {'box_cov':>8}  {'vol_err':>8}  {'time_s':>6}"
    )
    print(header)
    print("-" * len(header))
    for row in selection_rows:
        print(
            f"{row['observer_id']:3d}  {row['label']:<20}  "
            f"{row['rotation_from_base_deg']:7.2f}  {row['mean_prior_coverage']:10.5f}  "
            f"{row['prior_coverage_sum']:10d}  {row['new_voxels']:8d}  "
            f"{row['box_covered_fraction']:8.5f}  {row['volume_relative_error']:+8.4f}  "
            f"{row['elapsed_sec']:6.2f}"
        )
    final = summary_payload["final_metrics"]
    print("-" * len(header))
    print(
        f"Final: box_covered={final['box_covered_fraction']:.5f}  "
        f"cov_mean={final['coverage_mean']:.5f}  "
        f"cov_var={final['coverage_variance']:.5f}  "
        f"max_cov={final['max_voxel_coverage']}  "
        f"avg_prior={final['mean_selected_prior_coverage']:.5f}  "
        f"total_time={final['total_elapsed_sec']:.2f}s"
    )
    print(f"Saved: {output / 'result.json'} , {output / 'selections.csv'}")


def run(args, output):
    import numpy as np
    from scipy.spatial.transform import Rotation
    from orientation_geometry import (
        Orientation, SkyMask, angular_directions, axis_rotation,
        comoving_distance, evaluate_window, jaccard, make_library,
        mask_signature, occupied_window, rotation_distance, shell_geometry,
    )

    t_start = time.perf_counter()
    base = Rotation.from_euler("xyz", args.base_euler, degrees=True).as_matrix()
    observers = np.asarray(args.observer) % args.box_size
    if args.z_range:
        input_range = args.z_range
        rmin, rmax = [comoving_distance(z) for z in input_range]
        range_mode = "z_range"
    else:
        input_range = args.r_range
        rmin, rmax = input_range
        range_mode = "r_range"
    if not 0 <= rmin < rmax <= args.box_size / 2:
        raise ValueError("Shell must satisfy 0 <= rmin < rmax <= box_size/2; use --r-range for a smaller box.")

    mask = SkyMask(args.mask, args.mask_values)
    try:
        area = mask.area()
        if area == 0:
            raise ValueError("No mask pixels match --mask-values.")
        directions = angular_directions(args.angular_nside)
        base_signature = mask_signature(mask, directions, base)

        # Match orientation_pipeline.py SeedSequence indexing for reproducible strategy comparisons.
        strategy_idx = ["axes", "random", "mask-diverse"].index(args.strategy)
        rng = np.random.default_rng(np.random.SeedSequence([args.seed, strategy_idx]))
        library, signatures = make_library(
            args.strategy, base, args.angles_deg, args.candidate_count,
            args.pool_size, rng, mask, directions,
        )

        total = args.nmesh**3
        voxel_volume = (args.box_size / args.nmesh)**3
        analytic_volume = area * (np.pi / 180)**2 * (rmax**3 - rmin**3) / 3
        coverage = np.zeros(total, dtype=np.uint32)
        selection_rows = []
        selection_records = []

        for observer_index, observer in enumerate(observers):
            t_obs = time.perf_counter()
            indices, shell_directions = shell_geometry(
                args.box_size, args.nmesh, observer, rmin, rmax, args.chunk_size,
            )
            reference = occupied_window(mask, indices, shell_directions, base, total)

            rows = []
            tested = []
            best = -1
            best_occupied = None

            def evaluate(orientation, signature=None):
                nonlocal best, best_occupied
                occupied = occupied_window(mask, indices, shell_directions, orientation.matrix, total)
                metrics = evaluate_window(occupied, coverage, reference)
                if signature is None:
                    signature = mask_signature(mask, directions, orientation.matrix)
                row = {
                    "candidate_id": len(rows),
                    "label": orientation.label,
                    "stage": orientation.stage,
                    "axis": orientation.axis,
                    "axis_angle_deg": orientation.angle_deg,
                    "rotation_from_base_deg": rotation_distance(orientation.matrix, base),
                    "angular_iou_with_base": jaccard(signature, base_signature),
                    **metrics,
                    "volume_mpc_h_cubed": metrics["occupied_voxels"] * voxel_volume,
                    "volume_relative_error": metrics["occupied_voxels"] * voxel_volume / analytic_volume - 1,
                }
                idx = len(rows)
                rows.append(row)
                tested.append(orientation)
                if best == -1 or row["mean_prior_coverage"] < rows[best]["mean_prior_coverage"] - 1e-12:
                    best = idx
                    best_occupied = occupied
                return idx

            for orientation, signature in zip(library, signatures):
                evaluate(orientation, signature)

            if not np.isfinite(rows[best]["mean_prior_coverage"]):
                raise ValueError(f"No occupied voxels at observer {observer_index}; increase --nmesh or check mask/range.")

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
                            evaluate(candidate)
                    if current == best:
                        break

            coverage[best_occupied] += 1
            obs_elapsed = time.perf_counter() - t_obs

            if args.save_candidates:
                for i, row in enumerate(rows):
                    row["selected"] = int(i == best)
                write_csv(output / f"candidates_observer_{observer_index:03d}.csv", rows)
                matrices = np.asarray([item.matrix for item in tested])
                np.savez_compressed(
                    output / f"candidates_observer_{observer_index:03d}.npz",
                    matrices_sky_to_box=matrices,
                    quaternions_xyzw=Rotation.from_matrix(matrices).as_quat(),
                    labels=np.asarray([item.label for item in tested]),
                    selected_index=best,
                )

            best_matrix = tested[best].matrix
            best_quat = Rotation.from_matrix(best_matrix).as_quat().tolist()
            selection_row = {
                "strategy": args.strategy,
                "nmesh": args.nmesh,
                "observer_id": observer_index,
                "observer_x": float(observer[0]),
                "observer_y": float(observer[1]),
                "observer_z": float(observer[2]),
                "evaluated_candidates": len(rows),
                **{k: v for k, v in rows[best].items() if k != "selected"},
                "box_covered_fraction": float(np.count_nonzero(coverage) / total),
                "coverage_mean": float(coverage.mean()),
                "coverage_variance": float(coverage.var()),
                "elapsed_sec": round(obs_elapsed, 4),
            }
            selection_rows.append(selection_row)
            selection_records.append({
                **selection_row,
                "matrix_sky_to_box": best_matrix.tolist(),
                "quaternion_xyzw": best_quat,
            })

        total_elapsed = time.perf_counter() - t_start
        write_csv(output / "selections.csv", selection_rows)

        if args.save_coverage:
            np.savez_compressed(
                output / "coverage.npz",
                coverage=coverage.reshape((args.nmesh,) * 3),
                box_size=args.box_size,
                observers=observers,
                rmin=rmin,
                rmax=rmax,
            )

        config = {k: str(v.absolute()) if isinstance(v, Path) else v for k, v in vars(args).items()}
        summary_payload = {
            "format_version": 1,
            "strategy": args.strategy,
            "nmesh": args.nmesh,
            "box_size": args.box_size,
            "library_size": len(library),
            "shell": {
                "mode": range_mode,
                "input_range": input_range,
                "rmin": float(rmin),
                "rmax": float(rmax),
                "analytic_volume": float(analytic_volume),
            },
            "mask": {
                "path": str(args.mask.resolve()),
                "nside": mask.nside,
                "values": args.mask_values,
                "area_sqdeg": float(area),
            },
            "observers_wrapped": observers.tolist(),
            "arguments": config,
            "final_metrics": {
                "num_observers": len(observers),
                "box_covered_fraction": float(np.count_nonzero(coverage) / total),
                "coverage_mean": float(coverage.mean()),
                "coverage_variance": float(coverage.var()),
                "max_voxel_coverage": int(coverage.max()),
                "mean_selected_prior_coverage": float(np.mean([r["mean_prior_coverage"] for r in selection_rows])),
                "total_prior_coverage_sum": int(sum(r["prior_coverage_sum"] for r in selection_rows)),
                "mean_volume_relative_error": float(np.mean([r["volume_relative_error"] for r in selection_rows])),
                "mean_absolute_volume_relative_error": float(np.mean([abs(r["volume_relative_error"]) for r in selection_rows])),
                "max_absolute_volume_relative_error": float(np.max([abs(r["volume_relative_error"]) for r in selection_rows])),
                "total_elapsed_sec": round(total_elapsed, 4),
            },
            "selections": selection_records,
        }
        write_json(output / "result.json", summary_payload)
        print_run_summary(summary_payload, selection_rows, output)
    finally:
        mask.close()


def main(argv=None):
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    args.observer = [[args.x, args.y, args.z], *args.observer]
    radial = args.z_range or args.r_range
    numbers = [args.box_size, *args.base_euler, *args.angles_deg, *args.refine_steps, *radial]
    numbers += [v for row in args.observer for v in row]
    if not all(math.isfinite(v) for v in numbers) or args.box_size <= 0:
        parser.error("All numeric inputs must be finite and box-size must be positive.")
    if args.nmesh < 2:
        parser.error("--nmesh must be an integer >= 2.")
    if radial[0] < 0 or radial[1] <= radial[0]:
        parser.error("Radial or redshift interval must satisfy 0 <= min < max.")
    if args.candidate_count < 2 or args.pool_size < args.candidate_count:
        parser.error("Require pool-size >= candidate-count >= 2.")
    if args.angular_nside <= 0 or args.angular_nside & (args.angular_nside - 1):
        parser.error("--angular-nside must be a positive power of two.")
    if args.chunk_size <= 0 or args.refine_rounds < 1 or any(s <= 0 for s in args.refine_steps):
        parser.error("Chunk size, refinement rounds and angle steps must be positive.")
    if not args.mask.is_file():
        parser.error(f"Mask file does not exist: {args.mask}")

    output = args.output_dir.absolute()
    if output.exists():
        parser.error(f"Output directory already exists; choose a new path: {output}")
    output.mkdir(parents=True)

    run(args, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
