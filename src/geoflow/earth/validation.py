"""One 24-hour matched experiment per eligible drifter. Observations never drive the gridded integrator."""

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from .geo import R, distance, wrap
from .tracking import Current, track


def observations(path):
    # ERDDAP CSV includes a units row. Preserve large trajectory IDs as strings.
    if Path(path).suffix.lower() in (".nc", ".nc4"):
        with xr.open_dataset(path) as ds:
            names = ["ID", "time", "longitude", "latitude", "ve", "vn"]
            if "drogue_lost_date" in ds:
                names.append("drogue_lost_date")
            if not set(names) <= set(ds.variables) or ds.time.ndim != 1:
                raise ValueError("GDP NetCDF requires an hourly observation dimension")
            dim = ds.time.dims[0]
            counts = next(
                (
                    v
                    for v in ds.data_vars.values()
                    if v.attrs.get("sample_dimension") == dim
                ),
                None,
            )
            columns = {}
            for name in names:
                var = ds[name]
                if var.dims == (dim,):
                    columns[name] = var.values
                elif (
                    counts is not None
                    and var.dims == counts.dims
                    and counts.sum().item() == ds.sizes[dim]
                ):
                    columns[name] = np.repeat(var.values, counts.values.astype(int))
                else:
                    raise ValueError("unsupported GDP trajectory encoding")
            obs = pd.DataFrame(columns)
    else:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = [r for r in reader if r["time"] != "UTC"]
        obs = pd.DataFrame(rows)
    required = {"ID", "time", "longitude", "latitude", "ve", "vn"}
    if required - set(obs):
        raise ValueError(
            "expected hourly GDP ERDDAP CSV with ID, time, longitude, latitude, ve, vn"
        )
    obs["ID"] = obs.ID.astype(str)
    obs["time"] = pd.to_datetime(obs.time, utc=True).dt.tz_localize(None)
    for name in ("longitude", "latitude", "ve", "vn"):
        obs[name] = pd.to_numeric(obs[name], errors="coerce")
        obs.loc[abs(obs[name]) >= 99999, name] = np.nan
    return obs.sort_values(["ID", "time"])


def constant_position(lon, lat, u, v, seconds):
    # Constant local east/north components follow a rhumb line.
    phi = np.radians(lat)
    delta = v * np.asarray(seconds) / R
    end = phi + delta
    if np.any(abs(end) >= np.pi / 2):
        raise ValueError("baseline reached a pole")
    east = u * np.asarray(seconds) / (R * np.cos(phi))
    if abs(v) > 1e-8:
        east = u / v * (np.arcsinh(np.tan(end)) - np.arcsinh(np.tan(phi)))
    return wrap(lon + np.degrees(east)), np.degrees(end)


def summary(errors):
    a = np.asarray(errors, float)
    return (
        {
            "mean_m": float(np.mean(a)),
            "rms_m": float(np.sqrt(np.mean(a * a))),
            "count": len(a),
        }
        if len(a)
        else {"mean_m": None, "rms_m": None, "count": 0}
    )


def validate(ds, obs, hours=24, dt=900.0):
    if not isinstance(hours, int) or not 1 <= hours <= 168 or dt <= 0:
        raise ValueError("invalid validation horizon or dt")
    flow = Current(ds)
    records = []
    runs = []
    excluded = {}
    for ident, group in obs.groupby("ID", sort=True):
        group = group.sort_values("time")
        group = group[
            (group.time >= ds.time.values[0]) & (group.time <= ds.time.values[-1])
        ]
        if group.empty:
            excluded[str(ident)] = "no overlapping times"
            continue
        start = group.iloc[0]
        window = group[group.time <= start.time + pd.Timedelta(hours=hours)]
        ts = (window.time - start.time).dt.total_seconds().to_numpy()
        if (
            not np.array_equal(ts, np.arange(hours + 1) * 3600)
            or not np.isfinite(window[["longitude", "latitude"]]).all().all()
            or not np.isfinite([start.ve, start.vn]).all()
        ):
            excluded[str(ident)] = (
                "incomplete consecutive hourly positions or missing initial observed velocity"
            )
            continue
        t0 = flow.seconds(start.time)
        if t0 + ts[-1] > flow.axes[0][-1]:
            excluded[str(ident)] = "short model coverage"
            continue
        path = track(flow, start.longitude, start.latitude, t0, t0 + ts[-1], dt)
        pred = np.column_stack(
            [np.interp(t0 + ts, path.time, path.position[:, j]) for j in (0, 1)]
        )
        pred[t0 + ts > path.time[-1]] = np.nan
        if path.status != "completed" and len(path.time) == 1:
            pred[:] = np.nan
        clon, clat = constant_position(
            start.longitude, start.latitude, start.ve, start.vn, ts
        )
        for label, x, y in (
            ("gridded_RK4", pred[:, 0], pred[:, 1]),
            (
                "stationary",
                np.full(len(ts), start.longitude),
                np.full(len(ts), start.latitude),
            ),
            ("constant_initial_observed_velocity", clon, clat),
        ):
            errs = distance(
                x, y, window.longitude.to_numpy(), window.latitude.to_numpy()
            )
            for j, e in enumerate(errs):
                if not np.isfinite(e):
                    continue
                row = window.iloc[j]
                records.append(
                    {
                        "ID": str(ident),
                        "method": label,
                        "horizon_h": j,
                        "time_utc": row.time.isoformat(),
                        "observed_lon": float(row.longitude),
                        "observed_lat": float(row.latitude),
                        "longitude": float(wrap(x[j])),
                        "latitude": float(y[j]),
                        "separation_m": float(e),
                    }
                )
        lost = str(start.get("drogue_lost_date", "unknown"))
        runs.append(
            {
                "ID": str(ident),
                "release_utc": start.time.isoformat(),
                "status": path.status,
                "drogue_lost_date": lost,
                "observed_initial_u": float(start.ve),
                "observed_initial_v": float(start.vn),
            }
        )
    methods = {}
    for label in ("gridded_RK4", "stationary", "constant_initial_observed_velocity"):
        subset = [r for r in records if r["method"] == label and r["horizon_h"] > 0]
        by_h = {
            str(h): summary([r["separation_m"] for r in subset if r["horizon_h"] == h])
            for h in range(1, hours + 1)
        }
        methods[label] = dict(
            **summary([r["separation_m"] for r in subset]),
            by_horizon=by_h,
            final_mean_separation_m=by_h[str(hours)]["mean_m"],
            coverage=len(subset) / (len(runs) * hours) if runs else None,
        )
    return {
        "hours": hours,
        "dt_s": dt,
        "eligible": len(runs),
        "excluded": excluded,
        "tracks": runs,
        "methods": methods,
        "termination_rate": sum(r["status"] != "completed" for r in runs) / len(runs)
        if runs
        else None,
        "current_depth_m": float(ds.depth) if "depth" in ds.coords else None,
        "current_kind": ds.attrs.get("source_kind", "imported prescribed currents"),
        "selection": "first overlapping sample per returned ID, consecutive hourly observations, finite initial velocity",
        "current_source": ds.attrs.get("title", "local file"),
        "current_import": ds.attrs.get("import_spec", ""),
    }, records
