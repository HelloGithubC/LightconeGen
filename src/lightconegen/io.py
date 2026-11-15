"""Explicit layout/result persistence; nothing is written during import or search."""

import csv
import json
from pathlib import Path

import numpy as np

from .geometry import matrix_to_angles
from .models import Lightcone, LightconeLayout, SearchResult


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _write_csv(path, rows, fields):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else fields)
        writer.writeheader()
        writer.writerows(rows)


def _layout_dict(layout):
    result = {
        "boxsize": layout.boxsize, "cosmology": layout.cosmology,
        "mask": Path(layout.mask).name, "nmesh": layout.nmesh,
        "lightcones": [
            {"observer": list(cone.observer), "orientation": list(cone.orientation), "shift": list(cone.shift)}
            for cone in layout.lightcones
        ],
    }
    if layout.z_range is not None:
        result["z_range"] = list(layout.z_range)
    else:
        result["r_range"] = list(layout.r_range)
    return result


def load_layout(path):
    """Read layout.json, or convert the existing eval_fft result.json in memory."""
    path = Path(path)
    if path.is_dir():
        path = path / ("layout.json" if (path / "layout.json").is_file() else "result.json")
    data = json.loads(path.read_text())
    if "lightcones" in data:
        return LightconeLayout(
            boxsize=float(data["boxsize"]), nmesh=int(data["nmesh"]), mask=Path(data["mask"]).name,
            lightcones=[Lightcone(tuple(row["observer"]), tuple(row["orientation"]), tuple(row["shift"]))
                        for row in data["lightcones"]],
            z_range=tuple(data["z_range"]) if data.get("z_range") is not None else None,
            r_range=tuple(data["r_range"]) if data.get("r_range") is not None else None,
            cosmology=data.get("cosmology", "HR4"),
        )
    if data.get("method") != "periodic_fft":
        raise ValueError("Expected a lightcone layout or a periodic_fft result.json.")
    shell = data["shell"]
    return LightconeLayout(
        boxsize=float(data["box_size"]), nmesh=int(data["nmesh"]), mask=Path(data["mask"]["path"]).name,
        lightcones=[Lightcone(
            tuple(row[f"observer_{axis}"] for axis in "xyz"),
            matrix_to_angles(row["matrix_sky_to_box"]),
            tuple(row[f"shift_{axis}"] for axis in "xyz"),
        ) for row in data["selections"]],
        z_range=tuple(shell["input_range"]) if shell["mode"] == "z_range" else None,
        r_range=(shell["rmin"], shell["rmax"]) if shell["mode"] == "r_range" else None,
        cosmology=data["arguments"].get("cosmology", "HR4"),
    )


def load_result(directory):
    """Read a complete full-mode archive, including legacy FFT archives."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("status") != "completed":
        raise ValueError("Only completed full results can be resumed.")
    data = json.loads((directory / "result.json").read_text())
    layout = load_layout(directory)
    if data.get("method") != "periodic_fft":
        raise ValueError("Expected a periodic_fft full result.")
    with np.load(directory / "coverage.npz", allow_pickle=False) as archive:
        coverage = archive["coverage"].copy()
    with np.load(directory / "library.npz", allow_pickle=False) as archive:
        library = {key: archive[key].copy() for key in archive.files}
    integer_fields = {"observer_id", "candidate_id", "legal_positions", "shift_x", "shift_y", "shift_z",
                      "prior_coverage_sum", "occupied_voxels", "selected"}
    with (directory / "search_candidates.csv").open() as stream:
        candidates = [{key: int(value) if key in integer_fields else value if key == "label" else float(value)
                       for key, value in row.items()} for row in csv.DictReader(stream)]
    return SearchResult(
        layout=layout, mode="full", coverage=coverage, library=library,
        selections=data["selections"], candidates=candidates, arguments=data["arguments"],
        final_metrics=data["final_metrics"], mask_info=data["mask"],
        stop_reason=data["final_metrics"]["stop_reason"],
    )


def _observer_distances(layout):
    rows = []
    for first, cone in enumerate(layout.lightcones):
        for second in range(first + 1, len(layout.lightcones)):
            delta = (np.asarray(cone.shift) - layout.lightcones[second].shift + layout.nmesh // 2) % layout.nmesh - layout.nmesh // 2
            rows.append({"observer_i": first, "observer_j": second,
                         "periodic_distance_mpc_h": float(np.linalg.norm(delta) * layout.boxsize / layout.nmesh)})
    return rows


def save_result(result, output_dir):
    """Write a new directory: one layout JSON, or the full eight-file archive."""
    output = Path(output_dir)
    if result.mode not in ("layout", "full"):
        raise ValueError("result.mode must be 'layout' or 'full'.")
    if result.mode == "full" and (result.coverage is None or result.library is None):
        raise ValueError("A full result needs its coverage and candidate library.")
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "layout.json", _layout_dict(result.layout))
    if result.mode == "layout":
        return output
    layout = result.layout
    rmin, rmax = layout.radial_range
    observers = np.asarray([cone.observer for cone in layout.lightcones])
    np.savez_compressed(output / "coverage.npz", coverage=result.coverage, box_size=layout.boxsize,
                        observers=observers, shifts=np.asarray([cone.shift for cone in layout.lightcones]),
                        rmin=rmin, rmax=rmax)
    np.savez_compressed(output / "library.npz", **result.library)
    selections = [{key: value for key, value in row.items()
                   if key not in ("matrix_sky_to_box", "quaternion_xyzw")} for row in result.selections]
    _write_csv(output / "selections.csv", selections, ["observer_id"])
    _write_csv(output / "search_candidates.csv", result.candidates, ["observer_id", "candidate_id"])
    _write_csv(output / "observer_distances.csv", _observer_distances(layout), ["observer_i", "observer_j", "periodic_distance_mpc_h"])
    mode = "z_range" if layout.z_range is not None else "r_range"
    _write_json(output / "result.json", {
        "method": "periodic_fft", "strategy": result.arguments["strategy"],
        "nmesh": layout.nmesh, "box_size": layout.boxsize,
        "library_size": len(result.library["labels"]),
        "shell": {"mode": mode, "input_range": layout.z_range if mode == "z_range" else layout.r_range,
                  "rmin": rmin, "rmax": rmax,
                  "analytic_volume": result.mask_info["area_sqdeg"] * (np.pi / 180)**2 * (rmax**3 - rmin**3) / 3},
        "mask": result.mask_info, "arguments": result.arguments,
        "observers_wrapped": observers.tolist(), "final_metrics": result.final_metrics,
        "selections": result.selections,
    })
    _write_json(output / "manifest.json", {
        "status": "completed", "output_files": sorted(path.name for path in output.iterdir()) + ["manifest.json"],
    })
    return output


def plot_coverage(coverage, path, *, boxsize, observers=()):
    """Explicitly save three coverage projections; import plotting only here."""
    import matplotlib.pyplot as plt

    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    try:
        for collapsed, axis in enumerate(axes):
            remaining = [index for index in range(3) if index != collapsed]
            picture = axis.imshow(coverage.sum(axis=collapsed).T, origin="lower",
                                  extent=[0, boxsize, 0, boxsize], cmap="viridis")
            for index, observer in enumerate(observers):
                x, y = observer[remaining[0]], observer[remaining[1]]
                axis.scatter(x, y, color="red", marker="+", s=40)
                axis.annotate(str(index), (x, y), xytext=(4, 4), textcoords="offset points", color="red")
            axis.set_xlabel("xyz"[remaining[0]] + " (Mpc/h)")
            axis.set_ylabel("xyz"[remaining[1]] + " (Mpc/h)")
            figure.colorbar(picture, ax=axis, label="Summed coverage along " + "xyz"[collapsed], shrink=0.75)
        figure.savefig(path, dpi=160)
    finally:
        plt.close(figure)
    return path
