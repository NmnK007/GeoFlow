"""Small, source-linked tables projected from immutable release records."""

from functools import lru_cache

from . import service as s


@lru_cache(maxsize=1)
def evidence():
    checks = s.read(s.DEMO / "verification.json")["checks"]
    region = s.read(s.DEMO / "validation.json")
    runs = s.benchmarks()["runs"]
    accuracy = []
    timing = []
    for r in runs:
        n, method = r["grid"], r["method"]
        key = r["run"]
        if key.endswith("-paired"):
            timing.append([key, n, r["device"], r["median_ms"]])
        elif n == 64 and (
            method in {"muscl", "rusanov", "persistence"}
            or r["checkpoint"] in {f"{method}-64-24-base-11", f"{method}-64-24-base-29"}
        ):
            horizons = r["groups"]["id"]["horizons"]
            accuracy.append(
                [
                    key,
                    *[horizons[str(t)]["relative_l2"] for t in (1, 4, 16, 24)],
                    r["median_ms"],
                ]
            )

    def table(title, method, source, columns, rows):
        return {
            "title": title,
            "method": method,
            "source": source,
            "columns": columns,
            "rows": rows,
        }

    return [
        table(
            "Numerical verification · smooth wave refinement",
            "Small-amplitude travelling wave at a quarter period. Relative L1 is integrated absolute height-anomaly error divided by the analytical anomaly norm. Each order uses the preceding grid doubling.",
            "verification.json · refinement",
            ["Scheme", "Cells per wavelength", "Relative L1", "Order"],
            [
                [scheme, r["nx"], r["relative_l1"], r["order"]]
                for scheme, series in checks["refinement"].items()
                if scheme != "passed"
                for r in series
            ],
        ),
        table(
            "Numerical verification · Gaussian energy loss",
            "One 64 × 64 bump per scheme, 7200 s, CFL 0.4. Loss is a fraction of initial anomaly energy. The smaller MUSCL–MC loss measures numerical dissipation for this smooth experiment.",
            "verification.json · gaussian_diffusion",
            ["Scheme", "Fraction lost"],
            [[k, v] for k, v in checks["gaussian_diffusion"].items() if k != "passed"],
        ),
        table(
            "Numerical verification · channel waves",
            "One prescribed mode per experiment. Signed phase speed uses eastward positive. The Rossby comparison assumes quasi-geostrophic balance. Amplitude ratios below one measure damping.",
            "verification.json · rossby, kelvin",
            ["Mode", "Measured (m/s)", "Theory (m/s)", "Amplitude ratio"],
            [
                [
                    k,
                    checks[k]["measured_m_s"],
                    checks[k]["theory_m_s"],
                    checks[k]["amplitude_ratio"],
                ]
                for k in ("rossby", "kelvin")
            ],
        ),
        table(
            "Observational validation · Arabian Sea drifters",
            "Two NOAA GDP drifters released on 1 July 2020. Hourly great-circle separation over 24 h, RK4 step 900 s using DUACS surface geostrophic currents. One drifter had lost its drogue. Repeated hourly samples are correlated.",
            "validation.json · methods",
            [
                "Method",
                "Position pairs",
                "Mean separation (m)",
                "RMS (m)",
                "24 h mean (m)",
            ],
            [
                [
                    k,
                    v["count"],
                    v["mean_m"],
                    v["rms_m"],
                    v["by_horizon"]["24"]["mean_m"],
                ]
                for k, v in region["methods"].items()
            ],
        ),
        table(
            "Surrogate benchmarks · rollout error at 64 × 64",
            "Relative L2 of normalized state versus float64 MUSCL–MC, averaged over three familiar held-out trajectories. Each step is 240 s. Each learned fit used 24 training trajectories and three validation trajectories. Both seeds are shown separately. CNN error grows dramatically by step 24. A reference self-comparison measures reproducibility.",
            "hpc-results.json · runs / groups / id",
            ["Run", "Step 1", "Step 4", "Step 16", "Step 24", "Warm rollout (ms)"],
            accuracy,
        ),
        table(
            "Hardware benchmarks · paired CPU and GPU",
            "Same seed-11 checkpoint and Torch build within each pair. Timings cover 24 steps and the returned host history. Median of 12 case medians, three warm repeats per case. Device setup, training and scoring are excluded. Timings apply to the measured hardware.",
            "hpc-results.json · paired runs",
            ["Run", "Grid width", "Device", "Median (ms)"],
            timing,
        ),
    ]
