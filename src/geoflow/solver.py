"""Finite-volume time integration and output sampling."""

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np

from . import __version__
from .boundaries import faces
from .config import Config
from .diagnostics import integrals, potential_vorticity
from .grid import centers
from .initial_conditions import initial_state
from .muscl import InvalidStage, rk2
from .physics import rotate, signal_speed
from .reference import height_reference
from .state import primitive, valid


@dataclass
class SimulationResult:
    config: Config
    time: np.ndarray
    x: np.ndarray
    y: np.ndarray
    h: np.ndarray
    u: np.ndarray
    v: np.ndarray
    diagnostics: list[dict]
    metadata: dict


def metadata(c: Config) -> dict:
    return {
        "version": __version__,
        "config": asdict(c),
        "resolved_f_s_inv": c.f,
        "beta_m_inv_s_inv": c.beta,
        "effective_gravity_m_s2": c.g,
        "deformation_radius_m": math.sqrt(c.g * c.depth_m) / abs(c.f) if c.f else None,
        "scheme": (
            "MUSCL Rusanov, SSP-RK2, Strang rotation"
            if c.scheme == "muscl"
            else "first-order unsplit Rusanov, Euler flux then exact Coriolis rotation"
        ),
        "units": {
            "time": "s",
            "x": "m",
            "y": "m",
            "h": "m",
            "u": "m/s",
            "v": "m/s",
            "volume": "m^3",
            "energy": "m^5/s^2",
        },
    }


def trial(q: np.ndarray, c: Config, dt: float) -> np.ndarray:
    if c.scheme == "muscl":
        angle = c.rotation * (0.5 * dt)
        return rotate(rk2(rotate(q, angle), c, dt), angle)
    fx = faces(q, c.g, 0, c.boundary_x)
    fy = faces(q, c.g, 1, c.boundary_y)
    transported = (
        q
        - dt / (c.lx_m / c.nx) * np.diff(fx, axis=2)
        - dt / (c.ly_m / c.ny) * np.diff(fy, axis=1)
    )
    return rotate(transported, c.rotation * dt)


def advance(
    q: np.ndarray, c: Config, t: float, dt: float
) -> tuple[np.ndarray, float, int]:
    for rejected in range(c.max_retries + 1):
        if dt <= 0 or not math.isfinite(dt) or t + dt == t:
            raise RuntimeError(f"cannot advance time at t={t:g}, dt={dt:g}")
        with np.errstate(over="ignore", invalid="ignore"):
            try:
                candidate = trial(q, c, dt)
            except InvalidStage:
                candidate = None
        if candidate is not None and valid(candidate, c.min_depth_m):
            return candidate, dt, rejected
        dt *= 0.5
    raise RuntimeError(f"invalid trial state at t={t:g} after {c.max_retries} retries")


def run_simulation(
    config: Config, progress_callback: Callable[[float], None] | None = None
) -> SimulationResult:
    """Integrate to each output target. Callback receives simulated fraction [0,1]."""
    c = config
    start = perf_counter()
    x, y = centers(c)
    q = initial_state(c, x, y)
    times = np.arange(c.intervals + 1, dtype=float)
    times[:-1] *= c.sample_s
    times[-1] = c.duration_s
    h, u, v = (np.empty((len(times), c.ny, c.nx)) for _ in range(3))
    rows = []
    steps = rejects = 0
    t = dt = courant = 0.0
    max_f = float(np.max(np.abs(c.rotation)))
    rotation_cap = 0.1 / max_f if max_f else math.inf
    for index, target in enumerate(times):
        while t < target:
            if steps >= c.max_steps:
                raise RuntimeError(f"step limit {c.max_steps} exhausted at t={t:g}")
            rate = signal_speed(q, c.g, 0).max() / (c.lx_m / c.nx) + signal_speed(
                q, c.g, 1
            ).max() / (c.ly_m / c.ny)
            if not 0 < rate < math.inf:
                raise RuntimeError(f"invalid CFL rate at t={t:g}")
            remaining = target - t
            q, dt, rejected = advance(
                q, c, t, min(c.cfl / rate, rotation_cap, remaining)
            )
            t = target if dt == remaining else t + dt
            courant = dt * rate
            rejects += rejected
            steps += 1
        h[index], u[index], v[index] = primitive(q)
        volume, energy = integrals(h[index], u[index], v[index], c)
        if index == 0:
            v0, e0 = volume, energy
        potential = float(
            0.5
            * c.g
            * np.sum((h[index] - c.depth_m) ** 2)
            * (c.lx_m / c.nx)
            * (c.ly_m / c.ny)
        )
        speed = float(np.hypot(u[index], v[index]).max())
        pv = potential_vorticity(h[index], u[index], v[index], c)
        enstrophy = float(
            0.5 * np.sum(h[index] * pv**2) * (c.lx_m / c.nx) * (c.ly_m / c.ny)
        )
        if index == 0:
            initial_enstrophy = enstrophy
        reference = height_reference(c, x, y, target)
        reference_norm = np.linalg.norm(reference) if reference is not None else 0
        row = {
            "height_reference_relative_l2": float(
                np.linalg.norm(h[index] - c.depth_m - reference) / reference_norm
            )
            if reference_norm
            else None,
            "potential_energy": potential,
            "kinetic_energy": float(
                0.5
                * np.sum(h[index] * (u[index] ** 2 + v[index] ** 2))
                * (c.lx_m / c.nx)
                * (c.ly_m / c.ny)
            ),
            "potential_enstrophy": enstrophy,
            "relative_enstrophy_change": (enstrophy - initial_enstrophy)
            / initial_enstrophy
            if initial_enstrophy
            else None,
            "rossby_number": speed / (abs(c.f) * min(c.lx_m, c.ly_m)) if c.f else None,
            "froude_number": speed / math.sqrt(c.g * c.depth_m),
            "time_s": float(target),
            "dt_s": float(dt),
            "cfl": float(courant),
            "steps": steps,
            "rejected_steps": rejects,
            "volume_m3": volume,
            "volume_drift": abs(volume - v0) / v0,
            "energy": energy,
            "energy_change": energy - e0,
            "relative_energy_change": (energy - e0) / e0 if e0 else None,
            "min_h_m": float(h[index].min()),
            "max_h_m": float(h[index].max()),
            "max_speed_m_s": float(np.hypot(u[index], v[index]).max()),
            "wall_time_s": perf_counter() - start,
        }
        if any(
            value is not None and not math.isfinite(value) for value in row.values()
        ):
            raise RuntimeError(f"nonfinite diagnostic at t={t:g}")
        rows.append(row)
        if progress_callback:
            progress_callback(float(target / c.duration_s))
    info = dict(
        metadata(c), status="completed", error=None, runtime_s=perf_counter() - start
    )
    return SimulationResult(c, times, x, y, h, u, v, rows, info)
