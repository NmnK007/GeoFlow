"""Scientific adapters shared by the HTTP layer, offline demos and parity tests."""

import csv
import json
import os
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from threading import Lock
from zipfile import ZipFile

import numpy as np

from geoflow.config import Config, load_config
from geoflow.plotting import LABELS, field
from geoflow.solver import SimulationResult, run_simulation

ROOT = Path(os.getenv("GEOFLOW_ROOT", Path(__file__).resolve().parents[3])).resolve()
DEMO = ROOT / "benchmarks" / "web-demo"
STUDY = Path(os.getenv("GEOFLOW_STUDY", ROOT / "outputs/hpc-v05"))
PRESETS = {p.stem: p for p in (ROOT / "configs").glob("*.json")}
MODELS = ("cnn", "fno")
OCEAN_LOCK = Lock()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf8")


def configuration(preset, overrides):
    if preset not in PRESETS:
        raise ValueError("unknown experiment preset")
    values = asdict(load_config(PRESETS[preset])) | overrides
    if any(type(values[k]) is not int or values[k] > 192 for k in ("nx", "ny")):
        raise ValueError("web grid limit is 192 cells per side")
    return Config(
        **(
            values
            | {
                "max_frames": 129,
                "snapshot_mib": 48,
                "working_mib": 64,
                "max_steps": 20000,
            }
        )
    )


def grid(values, x, y, name, unit, axes):
    data = np.asarray(values)
    return {
        "values": np.where(np.isfinite(data), data, None).tolist(),
        "x": x.tolist(),
        "y": y.tolist(),
        "name": name,
        "unit": unit,
        "axes": axes,
    }


def simulation(out, config, progress=None):
    result = run_simulation(config, progress)
    for name in ("time", "x", "y", "h", "u", "v"):
        np.save(out / (name + ".npy"), getattr(result, name))
    write(
        out / "result.json",
        {
            "metadata": result.metadata,
            "times": result.time.tolist(),
            "diagnostics": result.diagnostics,
            "fields": LABELS,
        },
    )
    archive(out)


def archive(out):
    with ZipFile(out / "export.zip", "w") as bundle:
        for p in sorted(out.iterdir()):
            if p.suffix == ".npy" or p.name == "result.json":
                bundle.write(p, p.name)


def frame(out, index, name, at_s=None, vectors=False):
    info = read(out / "result.json")
    if not 0 <= index < len(info["times"]) or name not in LABELS:
        raise ValueError("frame or field outside available range")
    config = Config(**info["metadata"]["config"])
    arrays = [
        np.load(out / (k + ".npy"), mmap_mode="r")
        for k in ("time", "x", "y", "h", "u", "v")
    ]
    result = SimulationResult(config, *arrays, [], info["metadata"])
    if at_s is not None:
        from geoflow.comparison import frame as at_time

        result = at_time(result, at_s)
        index = 0
    value = grid(
        field(result, name, index),
        result.x,
        result.y,
        name,
        LABELS[name],
        ["East (m)", "North (m)"],
    )
    if vectors:
        value["vectors"] = [
            [int(x), int(y), float(result.u[index, y, x]), float(result.v[index, y, x])]
            for y in range(0, config.ny, max(1, (config.ny + 15) // 16))
            for x in range(0, config.nx, max(1, (config.nx + 15) // 16))
        ]
    return value


@lru_cache(maxsize=1)
def earth_sources():
    registry = os.getenv("GEOFLOW_EARTH_REGISTRY")
    extra = read(Path(registry)) if registry else {}
    if {"arabian", "fixture"}.intersection(extra) or len(extra) > 6:
        raise ValueError("invalid server Earth registry")
    return {"arabian": None, "fixture": None, **extra}


@lru_cache(maxsize=3)
def earth_data(dataset="arabian"):
    import xarray as xr

    from geoflow.earth.data import import_region
    from geoflow.earth.fixture import fixture

    if dataset not in earth_sources():
        raise ValueError("unknown Earth dataset")
    if dataset == "fixture":
        return fixture()
    with OCEAN_LOCK:
        if dataset == "arabian":
            with xr.open_dataset(DEMO / "region.nc") as ds:
                return ds.load()
        spec = earth_sources()[dataset]
        return import_region(
            spec["path"], spec["box"], spec["start"], spec["end"], spec.get("depth_m")
        )


@lru_cache(maxsize=8)
def earth_fields(index, dataset="arabian"):
    from geoflow.earth.diagnostics import fields

    ds = earth_data(dataset)
    if not 0 <= index < ds.sizes["time"]:
        raise ValueError("unknown ocean time index")
    return fields(ds, index)


def earth_catalog(dataset="arabian"):
    ds = earth_data(dataset)
    with (DEMO / "matched.csv").open(encoding="utf8") as stream:
        matches = list(csv.DictReader(stream))
    return {
        "dataset": dataset,
        "sources": list(earth_sources()),
        "times": [str(x) for x in ds.time.values],
        "fields": {
            k: v.attrs.get("units", "")
            for k, v in earth_fields(0, dataset).data_vars.items()
        },
        "provenance": {
            k: ds.attrs.get(k)
            for k in ("title", "institution", "license", "import_spec")
        },
        "matches": matches if dataset == "arabian" else [],
        "validation": read(DEMO / "validation.json") if dataset == "arabian" else None,
    }


def earth_frame(index, name, dataset="arabian"):
    ds = earth_fields(index, dataset)
    if name not in ds.data_vars:
        raise ValueError("unknown ocean field")
    a = ds[name]
    return grid(
        a.values,
        ds.lon.values,
        ds.lat.values,
        name,
        a.attrs.get("units", ""),
        ["Longitude (°E)", "Latitude (°N)"],
    )


@lru_cache(maxsize=1)
def benchmarks():
    return read(ROOT / "benchmarks/hpc-results.json")


def model_row(kind):
    key = f"16-{kind}-16-24-base-11-cpu-1"
    return next(r for r in benchmarks()["runs"] if r["run"] == key)


def live_available(kind):
    return (STUDY / f"{kind}-16-24-base-11.pt").is_file() and (
        STUDY / "data-16-24/states.npy"
    ).is_file()


def inference(out, kind, group, member):
    import torch

    from geoflow.neural.data import indices, load
    from geoflow.neural.evaluate import rollout
    from geoflow.neural.metrics import diagnostics
    from geoflow.neural.train import read_checkpoint

    torch.set_num_threads(1)
    m, states = load(STUDY / "data-16-24")
    idx = indices(m, group)[member]
    ref = states[idx]
    model, ck = read_checkpoint(STUDY / f"{kind}-16-24-base-11.pt", m)
    spec = m["trajectories"][idx]
    pred = rollout(model, m, ref[0], spec["f"], len(ref) - 1)
    for name, value in (("prediction", pred), ("reference", ref)):
        np.save(out / (name + ".npy"), value)
    write(
        out / "result.json",
        {
            "times": m["times"],
            "seed": spec["seed"],
            "fingerprint": m["fingerprint"],
            "architecture": ck["architecture"],
            "model": kind,
            "config": m["config"],
            "history": ck["history"],
            "diagnostics": diagnostics(pred, ref, m),
            "reference_diagnostics": diagnostics(ref, ref, m),
        },
    )
    archive(out)


def comparison(index, channel, kind=None, out=None, archive_path=None):
    if out:
        info = read(out / "result.json")
        arrays = [
            np.load(out / (k + ".npy"), mmap_mode="r")
            for k in ("reference", "prediction")
        ]
        times = info["times"]
    else:
        with np.load(archive_path or DEMO / (kind + ".npz")) as a:
            arrays = [a[k] for k in ("reference", "prediction")]
            times = a["time_s"]
    if not 0 <= index < len(times):
        raise ValueError("unknown prediction step")
    name, unit = (("Depth", "m"), ("East velocity", "m/s"), ("North velocity", "m/s"))[
        channel
    ]
    n = arrays[0].shape[-1]
    coord = (np.arange(n) + 0.5) * 200000 / n
    return [
        grid(a[index, channel], coord, coord, name, unit, ["East (m)", "North (m)"])
        for a in arrays
    ]
