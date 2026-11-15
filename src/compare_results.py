#!/usr/bin/env python3
"""Compare and summarize multiple eval_strategy.py runs from result.json files."""

import argparse
import csv
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True


SORT_FIELDS = {
    "box_cov": ("box_covered_fraction", True),
    "avg_prior": ("mean_selected_prior_coverage", False),
    "cov_var": ("coverage_variance", False),
    "prior_sum": ("total_prior_coverage_sum", False),
    "sum_sq": ("total_coverage_square_increment", False),
    "abs_vol_err": ("mean_absolute_volume_relative_error", False),
    "time": ("total_elapsed_sec", False),
    "run": ("run_name", False),
}


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        usage="%(prog)s GROUP_DIRECTORY [options]",
    )
    parser.add_argument(
        "group", type=Path, metavar="GROUP_DIRECTORY",
        help="One comparison-group directory; all result.json files inside it are included.",
    )
    parser.add_argument(
        "--sort-by", choices=list(SORT_FIELDS), default="run",
        help="Optional sort order (default: run name).",
    )
    parser.add_argument(
        "--show-observers", action="store_true",
        help="Also print per-observer selected labels and mean_prior_coverage across runs.",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        help="Optional new CSV file for the summary and complete run arguments; existing files are rejected.",
    )
    return parser


def discover_results(group):
    return sorted(group.rglob("result.json"))


def load_summary_row(result_path, group):
    data = json.loads(result_path.read_text())
    args = data["arguments"]
    shell = data["shell"]
    final = data["final_metrics"]
    selections = data.get("selections", [])
    absolute_errors = [abs(s["volume_relative_error"]) for s in selections]
    mean_abs_error = final.get("mean_absolute_volume_relative_error")
    max_abs_error = final.get("max_absolute_volume_relative_error")
    if mean_abs_error is None and absolute_errors:
        mean_abs_error = sum(absolute_errors) / len(absolute_errors)
    if max_abs_error is None and absolute_errors:
        max_abs_error = max(absolute_errors)
    refine = ",".join(f"{s:g}" for s in args.get("refine_steps", [])) or "-"
    return {
        "run_name": str(result_path.parent.relative_to(group)),
        "result_path": str(result_path),
        "strategy": data["strategy"],
        "nmesh": data["nmesh"],
        "rmin": shell["rmin"],
        "rmax": shell["rmax"],
        "box_size": data["box_size"],
        "mask_path": data["mask"]["path"],
        "mask_values": json.dumps(data["mask"]["values"]),
        "observers_wrapped": json.dumps(data["observers_wrapped"]),
        "range_mode": shell["mode"],
        "input_range": json.dumps(shell["input_range"]),
        "library_size": data["library_size"],
        "angular_nside": args.get("angular_nside", ""),
        "refine_steps": refine,
        "seed": args.get("seed", ""),
        "num_observers": final["num_observers"],
        "box_covered_fraction": final["box_covered_fraction"],
        "coverage_mean": final["coverage_mean"],
        "coverage_variance": final["coverage_variance"],
        "max_voxel_coverage": final["max_voxel_coverage"],
        "mean_selected_prior_coverage": final["mean_selected_prior_coverage"],
        "total_prior_coverage_sum": final["total_prior_coverage_sum"],
        "total_coverage_square_increment": sum(
            item["coverage_square_increment"] for item in selections
        ),
        "mean_volume_relative_error": final["mean_volume_relative_error"],
        "mean_absolute_volume_relative_error": mean_abs_error,
        "max_absolute_volume_relative_error": max_abs_error,
        "total_elapsed_sec": final["total_elapsed_sec"],
        "arguments_json": json.dumps(args, ensure_ascii=False, sort_keys=True),
        "_arguments": args,
        "_selections": selections,
    }


def print_comparison_table(rows):
    header = (
        f"{'run':<26}  {'strategy':<12}  {'nmesh':>5}  {'shell(Mpc/h)':<15}  "
        f"{'lib':>3}  {'refine':<7}  {'seed':>8}  {'obs':>3}  "
        f"{'box_cov':>8}  {'cov_mean':>8}  {'cov_var':>8}  {'max':>3}  "
        f"{'avg_prior':>9}  {'sum_sq':>7}  {'abs_vol':>8}  {'time_s':>6}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        shell_str = f"{row['rmin']:.1f}-{row['rmax']:.1f}"
        print(
            f"{row['run_name'][:26]:<26}  {row['strategy']:<12}  {row['nmesh']:5d}  "
            f"{shell_str:<15}  {row['library_size']:3d}  {row['refine_steps'][:7]:<7}  "
            f"{str(row['seed'])[:8]:>8}  {row['num_observers']:3d}  "
            f"{row['box_covered_fraction']:8.5f}  {row['coverage_mean']:8.5f}  "
            f"{row['coverage_variance']:8.5f}  {row['max_voxel_coverage']:3d}  "
            f"{row['mean_selected_prior_coverage']:9.4g}  "
            f"{row['total_coverage_square_increment']:7d}  "
            f"{row['mean_absolute_volume_relative_error']:8.4f}  {row['total_elapsed_sec']:6.2f}"
        )


def print_conditions(rows):
    print("\nRun conditions (full arguments are also included in the CSV):")
    for row in rows:
        print(f"\n[{row['run_name']}] {row['result_path']}")
        print(f"  mask: {row['mask_path']}  values: {row['mask_values']}")
        print(f"  box_size: {row['box_size']} Mpc/h  observers: {row['observers_wrapped']}")
        print(f"  {row['range_mode']}: {row['input_range']}  nmesh: {row['nmesh']}")
        print(f"  arguments: {row['arguments_json']}")


def print_observer_breakdown(rows):
    print("\nPer-observer breakdown:")
    header = (
        f"{'run':<26}  {'obs':>3}  {'label':<20}  {'rot_deg':>7}  "
        f"{'mean_prior':>10}  {'prior_sum':>9}  {'delta_sq':>8}  "
        f"{'new_vox':>8}  {'ref_iou':>7}  {'vol_err':>8}  {'box_cov':>8}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        for sel in row["_selections"]:
            print(
                f"{row['run_name'][:26]:<26}  {sel['observer_id']:3d}  {sel['label']:<20}  "
                f"{sel['rotation_from_base_deg']:7.2f}  {sel['mean_prior_coverage']:10.4g}  "
                f"{sel['prior_coverage_sum']:9d}  {sel['coverage_square_increment']:8d}  "
                f"{sel['new_voxels']:8d}  {sel['reference_iou']:7.4f}  "
                f"{sel['volume_relative_error']:+8.4f}  {sel['box_covered_fraction']:8.5f}"
            )


def main(argv=None):
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    group = args.group.absolute()
    if not group.is_dir():
        parser.error(f"Comparison group must be an existing directory: {group}")
    result_paths = discover_results(group)
    if not result_paths:
        print("No result.json files found under the provided paths.", file=sys.stderr)
        return 1

    rows = [load_summary_row(p, group) for p in result_paths]
    sort_key, reverse = SORT_FIELDS[args.sort_by]
    rows.sort(key=lambda r: r[sort_key], reverse=reverse)

    print(f"Comparison group: {group}")
    print_comparison_table(rows)
    print_conditions(rows)
    if args.show_observers:
        print_observer_breakdown(rows)

    if args.output_csv:
        export_rows = [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.output_csv.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(export_rows[0]))
            writer.writeheader()
            writer.writerows(export_rows)
        print(f"\nExported CSV: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
