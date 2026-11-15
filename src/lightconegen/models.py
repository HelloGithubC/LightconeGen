"""Small in-memory objects for search results and portable layouts."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial.transform import Rotation


@dataclass
class Lightcone:
    observer: tuple[float, float, float]
    orientation: tuple[float, float, float]
    shift: tuple[int, int, int]

    @property
    def matrix(self):
        """Map sky column vectors to the periodic box frame."""
        return Rotation.from_euler("xyz", self.orientation, degrees=True).as_matrix()


@dataclass
class LightconeLayout:
    boxsize: float
    nmesh: int
    mask: str
    lightcones: list[Lightcone]
    z_range: tuple[float, float] | None = None
    r_range: tuple[float, float] | None = None
    cosmology: str = "HR4"

    @property
    def radial_range(self):
        from .geometry import comoving_distance

        if self.cosmology != "HR4":
            raise ValueError("The current module supports the HR4 cosmology.")
        if self.z_range is not None:
            return tuple(comoving_distance(z) for z in self.z_range)
        return tuple(self.r_range)

    @property
    def anchor(self):
        return self.lightcones[0].observer


@dataclass
class SearchResult:
    layout: LightconeLayout
    mode: str
    stop_reason: str = "target_reached"
    coverage: np.ndarray | None = None
    library: dict | None = None
    selections: list[dict] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    arguments: dict = field(default_factory=dict)
    final_metrics: dict = field(default_factory=dict)
    mask_info: dict = field(default_factory=dict)
