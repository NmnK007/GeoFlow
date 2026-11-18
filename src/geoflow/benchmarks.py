"""Matched numerical experiments used by the verification CLI."""

import math
from dataclasses import replace

import numpy as np

from .config import Config
from .solver import run_simulation


def refinement():
    results = {}
    c = Config(experiment="wave", epsilon=1e-6, lx_m=34000, ly_m=21000, ny=4)
    speed = math.sqrt(c.gravity_m_s2 * c.depth_m)
    t = c.lx_m / (4 * speed)
    for scheme, limiter in [("rusanov", "mc"), ("muscl", "minmod"), ("muscl", "mc")]:
        rows = []
        for n in (32, 64, 128, 256):
            r = run_simulation(
                replace(
                    c, nx=n, scheme=scheme, limiter=limiter, duration_s=t, sample_s=t
                )
            )
            exact = (
                c.depth_m * c.epsilon * np.sin(2 * np.pi * (r.x - speed * t) / c.lx_m)
            )
            diff = r.h[-1, 0] - c.depth_m - exact
            error = float(np.sum(abs(diff)) / np.sum(abs(exact)))
            rows.append(
                {
                    "nx": n,
                    "relative_l1": error,
                    "relative_l2": float(np.linalg.norm(diff) / np.linalg.norm(exact)),
                    "order": math.log2(rows[-1]["relative_l1"] / error)
                    if rows
                    else None,
                }
            )
        results[f"{scheme}_{limiter}"] = rows
    return results, (
        results["muscl_mc"][-1]["order"] > 1.8
        and all(
            rows[-1]["relative_l1"] < rows[0]["relative_l1"]
            for rows in results.values()
        )
    )


def diffusion():
    losses = {}
    for scheme, limiter in [("rusanov", "mc"), ("muscl", "minmod"), ("muscl", "mc")]:
        r = run_simulation(Config(nx=64, ny=64, scheme=scheme, limiter=limiter))
        losses[f"{scheme}_{limiter}"] = -r.diagnostics[-1]["relative_energy_change"]
    return losses, 0 < losses["muscl_mc"] < losses["muscl_minmod"] < losses[
        "rusanov_mc"
    ]


def propagation(mode):

    settings = {
        "kelvin": {
            "lx_m": 250000,
            "ly_m": 180000,
            "reduced_gravity_m_s2": 0.1,
            "ny": 32,
            "duration_s": 20000,
        },
        "rossby": {
            "lx_m": 4e6,
            "ly_m": 1.5e6,
            "ny": 24,
            "plane": "beta",
            "duration_s": 400000,
        },
        "poincare": {"ly_m": 1e6, "ny": 8, "duration_s": 6000},
    }
    c = Config(
        experiment=mode,
        scheme="muscl",
        latitude_deg=45,
        nx=48,
        boundary_y="periodic" if mode == "poincare" else "wall",
        sample_s=settings[mode]["duration_s"] / 10,
        **settings[mode],
    )
    r = run_simulation(c)
    k = 2 * np.pi / c.lx_m
    coef = np.fft.rfft(r.h - c.depth_m, axis=2)[:, :, 1].mean(axis=1)
    phase = np.unwrap(np.angle(coef))
    measured = -(phase[-1] - phase[0]) / (k * r.time[-1])
    speed = math.sqrt(c.g * c.depth_m)
    if mode == "rossby":
        theory = -c.beta / (k**2 + (np.pi / c.ly_m) ** 2 + (c.f / speed) ** 2)
    elif mode == "kelvin":
        theory = math.copysign(speed, c.f)
    else:
        theory = math.hypot(c.f, speed * k) / k
    err = abs(measured / theory - 1)
    result = {
        "measured_m_s": float(measured),
        "theory_m_s": float(theory),
        "relative_speed_error": float(err),
        "relative_height_l2": r.diagnostics[-1]["height_reference_relative_l2"],
        "amplitude_ratio": float(abs(coef[-1] / coef[0])),
        "max_volume_drift": max(d["volume_drift"] for d in r.diagnostics),
        "min_depth_m": float(r.h.min()),
    }
    return result, (
        err < (0.15 if mode == "rossby" else 0.05)
        and result["relative_height_l2"] < 0.2
        and result["max_volume_drift"] < 1e-10
        and result["min_depth_m"] > 0
    )


def balanced_stability():
    from .diagnostics import potential_vorticity

    f = 1e-4
    period = 2 * np.pi / f
    c = Config(
        experiment="balanced",
        scheme="muscl",
        nx=4,
        ny=64,
        latitude_deg=45,
        f_override_s_inv=f,
        duration_s=10 * period,
        sample_s=period,
        epsilon=1e-3,
    )
    r = run_simulation(c)
    dy = c.ly_m / c.ny

    def residual(i):
        grad = (np.roll(r.h[i], -1, axis=0) - np.roll(r.h[i], 1, axis=0)) / (2 * dy)
        return np.linalg.norm(c.g * grad + f * r.u[i]) / np.linalg.norm(f * r.u[0])

    # For the steady jet q=(f-du/dy)/h. Compare anomalies to avoid masking error with f/H.
    l = 2 * np.pi / c.ly_m
    reference = (
        f - c.g / f * c.depth_m * c.epsilon * l * l * np.cos(l * r.y[:, None])
    ) / (c.depth_m * (1 + c.epsilon * np.cos(l * r.y[:, None])))
    reference = np.broadcast_to(reference, r.h[0].shape)
    pv = potential_vorticity(r.h[-1], r.u[-1], r.v[-1], c)
    pv_error = np.linalg.norm(pv - reference) / np.linalg.norm(
        reference - f / c.depth_m
    )
    stats = {
        "inertial_periods": 10,
        "steps": r.diagnostics[-1]["steps"],
        "initial_force_residual": float(residual(0)),
        "final_force_residual": float(residual(-1)),
        "relative_pv_anomaly_l2": float(pv_error),
        "enstrophy_change": r.diagnostics[-1]["relative_enstrophy_change"],
        "min_depth_m": float(r.h.min()),
        "max_volume_drift": max(d["volume_drift"] for d in r.diagnostics),
    }
    return stats, (
        stats["final_force_residual"] < 0.1
        and pv_error < 0.2
        and stats["min_depth_m"] > 0
        and stats["max_volume_drift"] < 1e-10
    )
