"""Uniform volume sampling inside a masked lightcone."""

from operator import index

import numpy as np

from .geometry import using_mask


def create_random_mock(layout, number_density, cone_id=0, *, mask=None, mask_dir=".",
                       seed=None, frame="box", chunk_size=262144):
    """Sample one cone at a constant comoving density in (h/Mpc)^3.

    Return a float64 array of shape (round(number_density * volume), 3) in Mpc/h.
    The default box frame matches select_points; the sky frame is Cartesian
    with the observer at the origin and axes aligned with the mask.
    """
    if not np.isfinite(number_density) or number_density < 0:
        raise ValueError("number_density must be finite and nonnegative.")
    if frame not in ("box", "sky"):
        raise ValueError("frame must be 'box' or 'sky'.")
    chunk_size = index(chunk_size)
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive.")

    cone = layout.lightcones[cone_id]
    rmin, rmax = layout.radial_range
    if not np.isfinite(layout.boxsize) or not 0 <= rmin < rmax <= layout.boxsize / 2:
        raise ValueError("Shell must satisfy 0 <= rmin < rmax <= boxsize/2.")
    if number_density == 0:
        return np.empty((0, 3), dtype=np.float64)

    rng = np.random.default_rng(seed)
    inner_volume, outer_volume = rmin**3, rmax**3
    rotation = cone.matrix if frame == "box" else None
    with using_mask(mask, filename=layout.mask, mask_dir=mask_dir) as sky_mask:
        solid_angle = sky_mask.area() * (np.pi / 180)**2
        if solid_angle == 0:
            raise ValueError("No mask pixels match the accepted labels.")
        volume = solid_angle * (outer_volume - inner_volume) / 3
        count = round(number_density * volume)
        positions = np.empty((count, 3), dtype=np.float64)
        acceptance = solid_angle / (4 * np.pi)
        filled = 0
        while filled < count:
            proposal_count = min(chunk_size, max(32, int(np.ceil((count - filled) / acceptance))))
            ra = rng.uniform(0, 2 * np.pi, proposal_count)
            sin_dec = rng.uniform(-1, 1, proposal_count)
            cos_dec = np.sqrt(1 - sin_dec**2)
            directions = np.column_stack((cos_dec * np.cos(ra), cos_dec * np.sin(ra), sin_dec))
            directions = directions[sky_mask.contains(directions)][:count - filled]
            size = len(directions)
            radius = np.cbrt(rng.uniform(inner_volume, outer_volume, size))
            points = directions * radius[:, None]
            if frame == "box":
                points = (points @ rotation.T + cone.observer) % layout.boxsize
            positions[filled:filled + size] = points
            filled += size
    return positions
