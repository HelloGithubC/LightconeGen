"""Mask queries, rotations and periodic shell geometry in Mpc/h."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import warnings

import numpy as np
from astropy.io import fits
from scipy.integrate import quad
from scipy.spatial.transform import Rotation


@dataclass
class Orientation:
    label: str
    matrix: np.ndarray
    axis: str = ""
    angle_deg: float = float("nan")
    stage: str = "library"


class SkyMask:
    """Query the original HEALPix map without rotating or degrading it."""

    def __init__(self, path, values=(4,)):
        self.path = Path(path).absolute()
        self.values = np.asarray(values)
        self._area = None
        self.hdus = fits.open(self.path, memmap=True)
        hdu = self.hdus[1]
        header = hdu.header
        if header.get("PIXTYPE", "").strip() != "HEALPIX":
            self.close()
            raise ValueError("The mask must be a HEALPix FITS table.")
        if header.get("INDXSCHM", "IMPLICIT").strip() != "IMPLICIT":
            self.close()
            raise ValueError("Only full, implicitly indexed HEALPix maps are supported.")
        ordering = header.get("ORDERING", "").strip().upper()
        if ordering not in ("NESTED", "RING"):
            self.close()
            raise ValueError("Mask ORDERING must be NESTED or RING.")
        self.nest = ordering == "NESTED"
        self.nside = int(header["NSIDE"])
        self.data = hdu.data.field(0).reshape(-1)
        if self.data.size != 12 * self.nside**2:
            self.close()
            raise ValueError("The FITS field length does not match NSIDE.")
        self.header = {
            key: header.get(key)
            for key in ("PIXTYPE", "NSIDE", "ORDERING", "COORDSYS", "INDXSCHM")
        }

    def close(self):
        self.hdus.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def contains(self, directions):
        import healpy as hp

        pix = hp.vec2pix(
            self.nside, directions[:, 0], directions[:, 1],
            directions[:, 2], nest=self.nest,
        )
        return np.isin(self.data[pix], self.values)

    def area(self, chunk_size=2_000_000):
        if self._area is not None:
            return self._area
        count = 0
        for start in range(0, self.data.size, chunk_size):
            count += np.count_nonzero(
                np.isin(self.data[start:start + chunk_size], self.values)
            )
        self._area = float(count * (4 * np.pi / self.data.size) * (180 / np.pi)**2)
        return self._area


@contextmanager
def using_mask(mask=None, *, filename=None, mask_dir="."):
    """Close only masks opened here; caller-owned masks remain open."""
    if isinstance(mask, SkyMask):
        yield mask
    else:
        path = mask if mask is not None else Path(mask_dir) / filename
        with SkyMask(path) as opened:
            yield opened


def matrix_to_angles(matrix):
    """Return extrinsic xyz Euler angles in degrees, including singular cases."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Gimbal lock detected.*", category=UserWarning)
        return tuple(float(value) for value in Rotation.from_matrix(matrix).as_euler("xyz", degrees=True))


def shifted_indices(indices, shift, nmesh):
    """Translate occupied C-order xyz indices by an integer periodic shift."""
    x = (indices // (nmesh * nmesh) + shift[0]) % nmesh
    y = ((indices // nmesh) % nmesh + shift[1]) % nmesh
    z = (indices % nmesh + shift[2]) % nmesh
    return (x * nmesh + y) * nmesh + z


def comoving_distance(z, omega_m=0.26):
    """Return flat-LambdaCDM comoving distance in Mpc/h, ignoring radiation."""
    return 2997.92458 * quad(
        lambda t: 1 / np.sqrt(omega_m * (1 + t)**3 + 1 - omega_m),
        0, z,
    )[0]


def angular_directions(nside):
    """Use equal-area HEALPix centers to compare rotated angular masks."""
    import healpy as hp

    return np.column_stack(hp.pix2vec(nside, np.arange(12 * nside**2), nest=True))


def mask_signature(mask, directions, matrix):
    # Column vectors obey v_box = matrix @ v_sky; row vectors use its inverse.
    return mask.contains(directions @ matrix)


def jaccard(first, second):
    union = np.count_nonzero(first | second)
    return float(np.count_nonzero(first & second) / union) if union else float("nan")


def angular_overlap(signatures):
    size = len(signatures)
    result = np.empty((size, size))
    for i in range(size):
        for j in range(i, size):
            result[i, j] = result[j, i] = jaccard(signatures[i], signatures[j])
    return result


def axis_rotation(axis, angle_deg):
    vector = np.zeros(3)
    vector["xyz".index(axis)] = np.radians(angle_deg)
    return Rotation.from_rotvec(vector).as_matrix()


def rotation_distance(first, second):
    return float(np.degrees(Rotation.from_matrix(first @ second.T).magnitude()))


def make_library(strategy, base, angles, count, pool_size, rng, mask, directions):
    candidates = [Orientation("base", base)]
    if strategy == "axes":
        seen = {tuple(np.round(base.ravel(), 12))}
        for axis in "xyz":
            for angle in angles:
                matrix = axis_rotation(axis, angle) @ base
                key = tuple(np.round(matrix.ravel(), 12))
                if key not in seen:
                    candidates.append(Orientation(
                        f"{axis}_{angle:g}", matrix, axis, float(angle),
                    ))
                    seen.add(key)
    else:
        size = count if strategy == "random" else pool_size
        for i, matrix in enumerate(
            Rotation.random(size - 1, random_state=rng).as_matrix()
        ):
            candidates.append(Orientation(f"random_{i:03d}", matrix @ base))

    signatures = np.asarray([
        mask_signature(mask, directions, item.matrix) for item in candidates
    ])
    if np.any(signatures.sum(axis=1) == 0):
        raise ValueError("Angular sampling misses the mask; increase --angular-nside.")
    if strategy == "mask-diverse":
        # Keep the base, then greedily reduce the worst angular IoU to the set.
        selected = [0]
        worst = np.full(len(candidates), -np.inf)
        for i in range(len(candidates)):
            worst[i] = jaccard(signatures[0], signatures[i])
        while len(selected) < count:
            worst[selected] = np.inf
            choice = int(np.argmin(worst))
            selected.append(choice)
            for i in range(len(candidates)):
                if i not in selected:
                    worst[i] = max(worst[i], jaccard(signatures[choice], signatures[i]))
        candidates = [candidates[i] for i in selected]
        signatures = signatures[selected]
    return candidates, signatures


def shell_geometry(box_size, nmesh, observer, rmin, rmax, chunk_size):
    """Find shell voxel centers; flatten arrays in C order with axes x,y,z."""
    indices, directions = [], []
    spacing = box_size / nmesh
    observer = np.asarray(observer)
    for start in range(0, nmesh**3, chunk_size):
        flat = np.arange(start, min(start + chunk_size, nmesh**3), dtype=np.int64)
        ijk = np.column_stack(np.unravel_index(flat, (nmesh,) * 3))
        displacement = (ijk + 0.5) * spacing - observer
        displacement = (displacement + box_size / 2) % box_size - box_size / 2
        radius = np.linalg.norm(displacement, axis=1)
        keep = (radius >= rmin) & (radius < rmax) & (radius > 0)
        indices.append(flat[keep])
        directions.append(displacement[keep] / radius[keep, None])
    return np.concatenate(indices), np.concatenate(directions)


def occupied_window(mask, indices, directions, matrix, total_voxels):
    occupied = np.zeros(total_voxels, dtype=bool)
    occupied[indices[mask_signature(mask, directions, matrix)]] = True
    return occupied


def evaluate_window(occupied, coverage, reference):
    size = int(occupied.sum())
    reference_size = int(reference.sum())
    intersection = int(np.count_nonzero(occupied & reference))
    union = size + reference_size - intersection
    prior_sum = int(coverage[occupied].sum(dtype=np.uint64))
    return {
        "occupied_voxels": size,
        "reference_intersection_voxels": intersection,
        "reference_iou": intersection / union if union else float("nan"),
        "reference_overlap_fraction": intersection / reference_size
        if reference_size else float("nan"),
        "prior_coverage_sum": prior_sum,
        "mean_prior_coverage": prior_sum / size if size else float("inf"),
        "new_voxels": int(np.count_nonzero(coverage[occupied] == 0)),
        "covered_before_voxels": int(np.count_nonzero(coverage[occupied] > 0)),
        "coverage_square_increment": 2 * prior_sum + size,
    }


def overlap_matrices(packed, sizes):
    """Count exact binary intersections of the discretized candidate windows."""
    lookup = np.array([int(i).bit_count() for i in range(256)], dtype=np.uint8)
    size = len(packed)
    intersection = np.empty((size, size), dtype=np.int64)
    for i in range(size):
        intersection[i, i] = sizes[i]
        for j in range(i + 1, size):
            value = int(lookup[np.bitwise_and(packed[i], packed[j])].sum())
            intersection[i, j] = intersection[j, i] = value
    union = np.asarray(sizes)[:, None] + np.asarray(sizes)[None, :] - intersection
    iou = np.full((size, size), np.nan)
    np.divide(intersection, union, out=iou, where=union > 0)
    return intersection, iou
