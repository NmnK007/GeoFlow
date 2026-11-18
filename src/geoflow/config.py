"""Immutable SI configuration. Resource ceilings apply before allocating fields."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .physics import OMEGA, coriolis


@dataclass(frozen=True)
class Config:
    experiment: str = "gaussian"
    nx: int = 48
    ny: int = 48
    lx_m: float = 1e6
    ly_m: float = 1e6
    depth_m: float = 100.0
    gravity_m_s2: float = 9.81
    latitude_deg: float = 0.0
    f_override_s_inv: float | None = None
    boundary_x: str = "periodic"
    boundary_y: str = "periodic"
    amplitude_m: float = 1.0
    sigma_m: float = 80000.0
    epsilon: float = 1e-4
    u0_m_s: float = 1.0
    v0_m_s: float = 0.0
    cfl: float = 0.4
    duration_s: float = 7200.0
    sample_s: float = 600.0
    min_depth_m: float = 1e-8
    max_steps: int = 100000
    max_retries: int = 8
    max_frames: int = 512
    snapshot_mib: int = 256
    working_mib: int = 256

    scheme: str = "rusanov"
    limiter: str = "mc"
    plane: str = "f"
    reduced_gravity_m_s2: float | None = None

    @property
    def beta(self) -> float:
        return (
            2 * OMEGA * math.cos(math.radians(self.latitude_deg)) / 6371000
            if self.plane == "beta"
            else 0.0
        )

    @property
    def g(self) -> float:
        return (
            self.gravity_m_s2
            if self.reduced_gravity_m_s2 is None
            else self.reduced_gravity_m_s2
        )

    @property
    def rotation(self):
        if self.plane == "f":
            return self.f
        import numpy as np

        y = (np.arange(self.ny) + 0.5) * (self.ly_m / self.ny)
        return self.f + self.beta * (y[:, None] - self.ly_m / 2)

    @property
    def f(self) -> float:
        return (
            coriolis(self.latitude_deg)
            if self.f_override_s_inv is None
            else self.f_override_s_inv
        )

    @property
    def intervals(self) -> int:
        ratio = self.duration_s / self.sample_s
        if not math.isfinite(ratio) or ratio > self.max_frames:
            raise ValueError("output frame limit exceeded")
        nearest = round(ratio)
        if abs(ratio - nearest) <= 4 * math.ulp(ratio):
            return max(1, nearest)
        return max(1, math.ceil(ratio))

    def __post_init__(self) -> None:
        limits = {
            "nx": (2, 2048),
            "ny": (2, 2048),
            "max_steps": (1, 1000000),
            "max_retries": (0, 16),
            "max_frames": (2, 4096),
            "snapshot_mib": (1, 256),
            "working_mib": (1, 512),
        }
        for name, (low, high) in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
        for name, value in vars(self).items():
            if name in limits or name in (
                "experiment",
                "boundary_x",
                "boundary_y",
                "scheme",
                "limiter",
                "plane",
            ):
                continue
            if name in ("f_override_s_inv", "reduced_gravity_m_s2") and value is None:
                continue
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        for name in (
            "lx_m",
            "ly_m",
            "depth_m",
            "gravity_m_s2",
            "duration_s",
            "sample_s",
            "sigma_m",
            "min_depth_m",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.depth_m <= self.min_depth_m:
            raise ValueError("reference depth below threshold")
        if not -90 <= self.latitude_deg <= 90 or not 0 < self.cfl <= 0.5:
            raise ValueError("latitude must be in [-90,90] and CFL in (0,0.5]")
        if self.experiment not in (
            "rest",
            "uniform",
            "wave",
            "gaussian",
            "rossby",
            "kelvin",
            "poincare",
            "balanced",
            "shear",
            "vortices",
        ):
            raise ValueError("unknown experiment")
        if any(
            b not in ("periodic", "wall") for b in (self.boundary_x, self.boundary_y)
        ):
            raise ValueError("boundaries must be periodic or wall")
        if self.plane not in ("f", "beta") or (
            self.plane == "beta"
            and (self.boundary_y != "wall" or self.boundary_x != "periodic")
        ):
            raise ValueError(
                "beta plane requires a zonally periodic, meridionally bounded channel"
            )
        if not 0 < self.g <= self.gravity_m_s2:
            raise ValueError(
                "effective gravity must be positive and no greater than gravity"
            )
        mode = self.experiment
        if mode == "rossby" and (
            self.plane != "beta"
            or abs(self.f) <= abs(self.beta * self.ly_m / 2)
            or abs(self.latitude_deg) == 90
        ):
            raise ValueError(
                "Rossby mode requires a midlatitude beta channel away from the equator and poles"
            )
        if mode in ("kelvin", "balanced", "vortices") and (
            not self.f or self.plane != "f"
        ):
            raise ValueError("this mode requires a nonzero constant f")
        if mode == "poincare" and self.plane != "f":
            raise ValueError("Poincare mode requires constant f")
        if mode in ("kelvin", "shear") and (self.boundary_x, self.boundary_y) != (
            "periodic",
            "wall",
        ):
            raise ValueError(
                "coastal and shear modes require a zonally periodic wall channel"
            )
        if mode in ("poincare", "balanced", "vortices") and (
            self.boundary_x,
            self.boundary_y,
        ) != ("periodic", "periodic"):
            raise ValueError("this preset requires doubly periodic boundaries")
        if mode == "shear" and (self.f or self.plane != "f"):
            raise ValueError("the shear benchmark assumes zero rotation")
        if self.scheme not in ("rusanov", "muscl") or self.limiter not in (
            "mc",
            "minmod",
        ):
            raise ValueError("unknown transport scheme or limiter")
        frames = self.intervals + 1
        cells = self.nx * self.ny
        if frames > self.max_frames or frames * 24 * cells > self.snapshot_mib * 2**20:
            raise ValueError("snapshot budget exceeded")
        if (1280 if self.scheme == "muscl" else 640) * cells > self.working_mib * 2**20:
            raise ValueError("working memory estimate exceeds budget")


def load_config(path: Path) -> Config:
    with Path(path).open(encoding="utf-8") as stream:
        return Config(**json.load(stream))
