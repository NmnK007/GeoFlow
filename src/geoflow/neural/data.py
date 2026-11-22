"""Seeded trajectories from the production finite-volume time integrator. All reference arrays use SI float64."""

import hashlib
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import numpy as np

from geoflow import __version__
from geoflow.config import Config
from geoflow.grid import centers
from geoflow.solver import evolve_to_outputs
from geoflow.state import conserved, primitive

GROUPS = ("train", "validation", "id", "amplitude_location", "rotation")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(manifest):
    body = {
        k: v for k, v in manifest.items() if k not in ("fingerprint", "generation_s")
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def parameters(seed, group):
    rng = np.random.default_rng(seed)
    harder = group == "amplitude_location"
    a = rng.uniform(1.4, 1.8) if harder else rng.uniform(0.4, 1.2)
    lo, hi = (0.76, 0.96) if harder else (0.15, 0.65)
    return {
        "seed": seed,
        "group": group,
        "amplitude": float(a * rng.choice([-1, 1])),
        "cx": rng.uniform(lo, hi),
        "cy": rng.uniform(lo, hi),
        "width": rng.uniform(0.07, 0.14),
        "phases": rng.uniform(0, 2 * np.pi, 4).tolist(),
        "velocity": rng.uniform(0.04, 0.17),
        "f": float(rng.choice([-0.5, 0.5] if group == "rotation" else [-1, 0, 1]))
        * 1e-4,
    }


def initial(config, spec):
    x, y = centers(config)
    x = x / config.lx_m
    y = y[:, None] / config.ly_m
    # Smooth periodic Gaussian-like bump; coordinates are fractions of the domain.
    r = (
        np.sin(np.pi * (x - spec["cx"])) ** 2 + np.sin(np.pi * (y - spec["cy"])) ** 2
    ) / np.pi**2
    eta = spec["amplitude"] * np.exp(-0.5 * r / spec["width"] ** 2)
    p = spec["phases"]
    u = spec["velocity"] * (
        np.sin(2 * np.pi * y + p[0]) + 0.5 * np.cos(2 * np.pi * x + p[1])
    )
    v = spec["velocity"] * (
        np.sin(2 * np.pi * x + p[2]) + 0.5 * np.cos(2 * np.pi * y + p[3])
    )
    return conserved(config.depth_m + eta, u, v)


def integrate(config, q, times):
    states = np.empty((len(times), 3, config.ny, config.nx), np.float64)
    for i, (state, *_) in enumerate(evolve_to_outputs(q, config, times)):
        states[i] = primitive(state)
    return states


def generate(
    out, grid=16, train=16, validation=4, test=4, steps=16, interval=240.0, seed=1200
):
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    if not (
        8 <= grid <= 256
        and min(train, validation, test) >= 1
        and 4 <= steps <= 256
        and 0 < interval <= 3600
        and seed >= 0
    ):
        raise ValueError("invalid grid, split count, horizon, interval or seed")
    n = train + validation + 3 * test
    shape = (n, steps + 1, 3, grid, grid)
    if n * (steps + 1) * 3 * grid**2 * 8 > 2**31:
        raise ValueError("dataset exceeds the 2 GiB generation limit")
    config = Config(
        scheme="muscl",
        limiter="mc",
        nx=grid,
        ny=grid,
        lx_m=2e5,
        ly_m=2e5,
        sample_s=interval,
        duration_s=steps * interval,
    )
    times = np.arange(steps + 1) * interval
    out.parent.mkdir(parents=True, exist_ok=True)
    from dataclasses import replace

    start = perf_counter()
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / "dataset"
        stage.mkdir()
        states = np.lib.format.open_memmap(
            stage / "states.npy", "w+", dtype="float64", shape=shape
        )
        specs = []
        for group, count in zip(
            GROUPS, (train, validation, test, test, test), strict=True
        ):
            for _ in range(count):
                i = len(specs)
                spec = parameters(seed + i, group)
                c = replace(config, f_override_s_inv=spec["f"])
                states[i] = integrate(c, initial(c, spec), times)
                specs.append(spec)
        # Fit exclusively on the training trajectories and the short training window.
        fit_steps = min(6, steps)
        samples = np.asarray(states[:train, : fit_steps + 1])
        mean = samples.mean(axis=(0, 1, 3, 4))
        std = samples.std(axis=(0, 1, 3, 4))
        del samples, states
        m = {
            "format": 1,
            "geoflow": __version__,
            "numpy": np.__version__,
            "config": asdict(config),
            "times": times.tolist(),
            "trajectories": specs,
            "train_steps": fit_steps,
            "mean": mean.tolist(),
            "std": std.tolist(),
            "channels": ["h_m", "u_m_s", "v_m_s"],
            "sha256": digest(stage / "states.npy"),
            "generation_s": perf_counter() - start,
        }
        m["fingerprint"] = fingerprint(m)
        (stage / "manifest.json").write_text(
            json.dumps(m, indent=2, allow_nan=False), encoding="utf8"
        )
        stage.rename(out)
    return m


def load(path):
    path = Path(path)
    m = json.loads((path / "manifest.json").read_text(encoding="utf8"))
    if (
        m.get("format") != 1
        or m.get("fingerprint") != fingerprint(m)
        or digest(path / "states.npy") != m["sha256"]
    ):
        raise ValueError("invalid neural dataset fingerprint")
    states = np.load(path / "states.npy", allow_pickle=False, mmap_mode="r")
    c = Config(**m["config"])
    specs = m["trajectories"]
    if (
        states.shape != (len(specs), len(m["times"]), 3, c.ny, c.nx)
        or states.dtype != np.float64
        or len({s["seed"] for s in specs}) != len(specs)
        or {s["group"] for s in specs} != set(GROUPS)
        or not np.all(np.asarray(m["std"]) > 0)
        or not np.isfinite(m["mean"] + m["std"]).all()
    ):
        raise ValueError("invalid neural dataset schema")
    return m, states


def indices(m, group):
    return [i for i, s in enumerate(m["trajectories"]) if s["group"] == group]
