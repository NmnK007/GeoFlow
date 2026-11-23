"""Controlled generation, allocation and nested-grid experiments. Run apart from timed workers."""

import argparse
import json
import tracemalloc
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np

from geoflow.neural.data import generate, indices, load
from geoflow.neural.models import normalize


def checks(root):
    out = {}
    with TemporaryDirectory(dir=root) as temp:
        ms = {w: [] for w in (1, 2)}
        hashes = set()
        for rep in range(3):
            for w in (1, 2) if rep % 2 == 0 else (2, 1):
                m = generate(
                    Path(temp) / f"{rep}-{w}",
                    grid=32,
                    train=4,
                    validation=1,
                    test=1,
                    steps=24,
                    scaling=True,
                    workers=w,
                )
                ms[w].append(m["generation_s"])
                hashes.add(m["fingerprint"])
        if len(hashes) != 1:
            raise ValueError("generation varies by worker count")
        out["generation_32_pilot_s"] = ms
    m, x = load(root / "data-64-24")
    ids = indices(m, "train")

    def old():
        arr = x[ids, :7]
        return (arr - np.asarray(m["mean"])[:, None, None]) / np.asarray(m["std"])[
            :, None, None
        ]

    def new():
        return normalize(x[: len(ids), :7], m)

    np.testing.assert_array_equal(old(), new())
    for name, fn in (("old", old), ("new", new)):
        samples = []
        for _ in range(5):
            start = perf_counter()
            fn()
            samples.append((perf_counter() - start) * 1000)
        tracemalloc.start()
        fn()
        peak = tracemalloc.get_traced_memory()[1] / 2**20
        tracemalloc.stop()
        out["normalization_" + name] = {"median_ms": median(samples), "peak_mib": peak}
    for n in (16, 32):
        mc, xc = load(root / f"data-{n}-24")
        errors = []
        for j in indices(mc, "id"):
            assert mc["trajectories"][j] == m["trajectories"][j]
            factor = 64 // n
            fine = x[j, -1]

            def restrict(a, n=n, factor=factor):
                return a.reshape(n, factor, n, factor).mean(axis=(1, 3))

            h = restrict(fine[0])
            coarse = np.stack(
                [h, restrict(fine[0] * fine[1]) / h, restrict(fine[0] * fine[2]) / h]
            )
            errors.append(float(np.mean((xc[j, -1, 0] - coarse[0]) ** 2) ** 0.5))
        out[f"refinement_{n}_to_64_height_rmse_m"] = mean(errors)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    args = p.parse_args()
    (args.root / "checks.json").write_text(json.dumps(checks(args.root), indent=2))
