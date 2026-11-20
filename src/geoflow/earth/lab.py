"""Offline case analysis, exports and regional research artifacts."""

import csv
import json
from pathlib import Path

from geoflow import __version__

from .data import fingerprint
from .diagnostics import fields
from .eddies import candidates
from .plots import regional_map, separation_plot
from .validation import observations, validate


def write_rows(path, rows, columns):
    with path.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def match_observations(ds, obs_path, hours, dt):
    report, records = validate(ds, observations(obs_path), hours, dt)
    digest = fingerprint(obs_path)
    manifest = Path(str(obs_path) + ".json")
    if manifest.exists():
        info = json.loads(manifest.read_text())
        if info.get("sha256") == digest:
            report["observational_provenance"] = info
    report.update(drifter_file=Path(obs_path).name, drifter_sha256=digest)
    return report, records


def analyze(
    ds,
    out: Path,
    index=0,
    obs_path=None,
    hours=24,
    dt=900.0,
    ow=0.0,
    sla=0.02,
    minimum=4,
    tracks=(),
    particle_config=None,
    *,
    prepared=None,
    matched=None,
):
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("choose an empty output directory")
    if prepared is None:
        d = fields(ds, index)
        eddies = candidates(d, ow, sla, minimum) if "sla" in d else []
    else:
        d, eddies = prepared
    report = None
    records = []
    if obs_path:
        if ds.attrs.get("source_kind") == "synthetic":
            raise ValueError("observational comparison requires external currents")
        report, records = (
            matched
            if matched is not None
            else match_observations(ds, obs_path, hours, dt)
        )
        (out / "validation.json").write_text(
            json.dumps(report, indent=2, allow_nan=False)
        )
        cols = [
            "ID",
            "method",
            "horizon_h",
            "time_utc",
            "observed_lon",
            "observed_lat",
            "longitude",
            "latitude",
            "separation_m",
        ]
        write_rows(out / "matched.csv", records, cols)
        separation_plot(report).savefig(out / "separation.png", dpi=140)
    write_rows(
        out / "candidates.csv",
        eddies,
        [
            "classification",
            "longitude",
            "latitude",
            "cells",
            "area_m2",
            "radius_m",
            "mean_vorticity_s_inv",
        ],
    )
    particle_rows = (
        {
            "particle": i,
            "time_s": float(t),
            "longitude": float(p[0]),
            "latitude": float(p[1]),
            "status": tr.status,
        }
        for i, tr in enumerate(tracks)
        for t, p in zip(tr.time, tr.position, strict=True)
    )
    write_rows(
        out / "particles.csv",
        particle_rows,
        ["particle", "time_s", "longitude", "latitude", "status"],
    )
    ds.to_netcdf(out / "region.nc")
    d.to_netcdf(out / "diagnostics.nc")
    regional_map(ds, d, "speed", index, tracks, eddies, records).savefig(
        out / "regional.png", dpi=140
    )
    spec = {
        "dataset": dict(ds.attrs),
        "geoflow_version": __version__,
        "index": index,
        "time": str(ds.time.values[index]),
        "time_origin": str(ds.time.values[0]),
        "ow_threshold": ow,
        "sla_min_m": sla,
        "min_cells": minimum,
        "hours": hours,
        "dt_s": dt,
        "particle_integration": particle_config or {},
        "eddy_candidates": len(eddies),
    }
    (out / "analysis.json").write_text(json.dumps(spec, indent=2, default=str))
    return report
