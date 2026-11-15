"""Rebuild voxel coverage or select rows from simulation position arrays."""

from collections import defaultdict

import numpy as np

from .geometry import mask_signature, shell_geometry, shifted_indices, using_mask


def rebuild_coverage(layout, *, mask=None, mask_dir=".", chunk_size=262144):
    """Rebuild the original grid using anchor templates and integer shifts."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive.")
    coverage = np.zeros(layout.nmesh**3, dtype=np.uint32)
    groups = defaultdict(list)
    for cone in layout.lightcones:
        groups[tuple(cone.orientation)].append(cone)
    with using_mask(mask, filename=layout.mask, mask_dir=mask_dir) as sky_mask:
        indices, directions = shell_geometry(
            layout.boxsize, layout.nmesh, layout.anchor, *layout.radial_range, chunk_size,
        )
        for cones in groups.values():
            occupied = indices[mask_signature(sky_mask, directions, cones[0].matrix)]
            for cone in cones:
                coverage[shifted_indices(occupied, cone.shift, layout.nmesh)] += 1
    return coverage.reshape((layout.nmesh,) * 3)


def select_points(positions, layout, cone_id=0, *, mask=None, mask_dir=".", chunk_size=262144):
    """Return row indices inside one continuous masked shell, without grid rounding."""
    positions = np.asarray(positions)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("positions must have shape (N, 3) in Mpc/h.")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive.")
    cone = layout.lightcones[cone_id]
    rmin, rmax = layout.radial_range
    matrix = cone.matrix
    selected = []
    with using_mask(mask, filename=layout.mask, mask_dir=mask_dir) as sky_mask:
        for start in range(0, len(positions), chunk_size):
            delta = np.asarray(positions[start:start + chunk_size], dtype=np.float64) - cone.observer
            delta = (delta + layout.boxsize / 2) % layout.boxsize - layout.boxsize / 2
            radius = np.linalg.norm(delta, axis=1)
            rows = np.flatnonzero((radius >= rmin) & (radius < rmax) & (radius > 0))
            if rows.size:
                keep = mask_signature(sky_mask, delta[rows] / radius[rows, None], matrix)
                selected.append(start + rows[keep])
    return np.concatenate(selected) if selected else np.empty(0, dtype=np.int64)
