"""Quick reproducible experiments. All references use independent analytic expressions."""

import math
from dataclasses import replace

import numpy as np

from .benchmarks import balanced_stability, diffusion, propagation, refinement
from .config import Config
from .solver import run_simulation


def verify() -> dict:
    checks = {}
    convergence = []
    errors = {}

    def record(name, experiment, *args):
        try:
            measurements, passed = experiment(*args)
            checks[name] = dict(passed=bool(passed), **measurements)
        except (ArithmeticError, ValueError, RuntimeError) as exc:
            checks[name] = {"passed": False}
            errors[name] = str(exc)

    base = Config(nx=12, ny=7, lx_m=34000, ly_m=21000, duration_s=620, sample_s=310)

    def constant(c, u, v):
        r = run_simulation(c)
        error = max(
            np.max(abs(r.h - c.depth_m)),
            np.max(abs(r.h * r.u - c.depth_m * u)),
            np.max(abs(r.h * r.v - c.depth_m * v)),
        )
        return {"max_abs_state_error": float(error)}, error <= 1e-10

    for wall in ("periodic", "wall"):
        for f in (0.0, 1e-4):
            c = replace(
                base,
                experiment="rest",
                boundary_x=wall,
                boundary_y=wall,
                f_override_s_inv=f,
            )
            record(f"rest_{wall}_{f}", constant, c, 0, 0)
    record(
        "translation",
        lambda: constant(replace(base, experiment="uniform", v0_m_s=-0.4), 1, -0.4),
    )

    def inertial(f):
        period = 2 * math.pi / abs(f)
        r = run_simulation(
            replace(
                base,
                experiment="uniform",
                f_override_s_inv=f,
                duration_s=period,
                sample_s=period / 4,
            )
        )
        angle = f * r.time[:, None, None]
        # RMS vector error per frame, normalized by the unit reference speed.
        error = np.sqrt(
            ((r.u - np.cos(angle)) ** 2 + (r.v + np.sin(angle)) ** 2).mean(axis=(1, 2))
        ).max()
        return {"max_relative_velocity_l2": float(error)}, error <= 1e-10

    for f in (-1e-4, 1e-4):
        record(f"inertial_{f}", inertial, f)

    def wave():
        speed = math.sqrt(base.gravity_m_s2 * base.depth_m)
        duration = base.lx_m / (4 * speed)
        k = 2 * math.pi / base.lx_m
        for nx in (32, 64, 128):
            c = replace(
                base,
                experiment="wave",
                nx=nx,
                ny=4,
                duration_s=duration,
                sample_s=duration,
            )
            r = run_simulation(c)
            exact = c.epsilon * c.depth_m * np.sin(k * (r.x - speed * duration))
            anomaly = r.h[:, 0, :] - c.depth_m
            error = float(np.linalg.norm(anomaly[-1] - exact) / np.linalg.norm(exact))
            mode = np.fft.rfft(anomaly, axis=1)[:, 1]
            measured = float(-np.angle(mode[-1] / mode[0]) / (k * duration))
            order = (
                math.log2(convergence[-1]["relative_l2"] / error)
                if convergence
                else None
            )
            convergence.append(
                {"nx": nx, "relative_l2": error, "speed_m_s": measured, "order": order}
            )
        a, b, d = convergence
        return {"theory_m_s": speed}, (
            a["relative_l2"] > b["relative_l2"] > d["relative_l2"]
            and abs(d["speed_m_s"] / speed - 1) <= 0.10
        )

    record("gravity_wave", wave)

    def bump(boundary, latitude):
        c = replace(base, boundary_y=boundary, latitude_deg=latitude, sigma_m=3800)
        r = run_simulation(c)
        drift = max(row["volume_drift"] for row in r.diagnostics)
        minimum = float(r.h.min())
        symmetry = max(
            float(np.max(abs(r.h - r.h[:, :, ::-1]))),
            float(np.max(abs(r.h - r.h[:, ::-1, :]))),
        )
        return {
            "volume_drift": drift,
            "min_h_m": minimum,
            "depth_mirror_error_m": symmetry,
        }, (drift <= 1e-10 and minimum > 0 and (latitude != 0 or symmetry <= 1e-10))

    for boundary in ("periodic", "wall"):
        for latitude in (0, 45):
            record(f"bump_{boundary}_{latitude}", bump, boundary, latitude)
    for mode in ("rossby", "kelvin", "poincare"):
        record(mode, propagation, mode)
    record("ten_period_jet", balanced_stability)
    record("refinement", refinement)
    record("gaussian_diffusion", diffusion)
    return {
        "passed": all(c["passed"] for c in checks.values()),
        "checks": checks,
        "convergence": convergence,
        "errors": errors,
    }
