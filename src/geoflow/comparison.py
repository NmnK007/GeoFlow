"""Comparison at common physical times without spatial resampling."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from .io import export, write_csv, write_json
from .solver import SimulationResult


def frame(r: SimulationResult, t: float) -> SimulationResult:
    if not r.time[0] <= t <= r.time[-1]:
        raise ValueError("comparison time outside trajectory")
    j = int(np.searchsorted(r.time, t))
    i = max(0, j - 1)
    weight = (t - r.time[i]) / (r.time[j] - r.time[i]) if j != i else 0.0

    def sample(a):
        return ((1 - weight) * a[i] + weight * a[j])[None]

    return replace(r, time=np.array([t]), h=sample(r.h), u=sample(r.u), v=sample(r.v))


def common_times(a, b):
    end = min(a.time[-1], b.time[-1])
    return np.union1d(a.time[a.time <= end], b.time[b.time <= end])


def export_comparison(a, b, path: Path):
    for name, r in (("A", a), ("B", b)):
        directory = path / name
        directory.mkdir()
        export(r, directory)
    rows = []
    matched = np.array_equal(a.x, b.x) and np.array_equal(a.y, b.y)
    for t in common_times(a, b):
        row = {"time_s": float(t)}
        for label, r in (("A", a), ("B", b)):
            for key in (
                "energy",
                "kinetic_energy",
                "potential_energy",
                "volume_drift",
                "height_reference_relative_l2",
            ):
                values = [d[key] for d in r.diagnostics]
                row[f"{label}_{key}"] = (
                    float(np.interp(t, r.time, values))
                    if all(v is not None for v in values)
                    else None
                )
        if matched:
            ha = frame(a, t).h[0] - a.config.depth_m
            hb = frame(b, t).h[0] - b.config.depth_m
            row["anomaly_difference_rms_m"] = float(np.sqrt(np.mean((ha - hb) ** 2)))
        rows.append(row)
    write_csv(path / "comparison.csv", rows, list(rows[0]))
    write_json(
        path / "comparison.json",
        {
            "status": "completed",
            "A": a.metadata,
            "B": b.metadata,
            "time_alignment": "union of saved times over overlap, linear temporal interpolation",
            "spatial_grids_match": matched,
        },
    )
