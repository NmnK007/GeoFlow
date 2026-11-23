"""Collect independent worker results and render the scaling figure."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean, median, pstdev

from matplotlib.figure import Figure


def collect(root):
    rows = []
    for path in sorted((root / "measurements").glob("*.json")):
        item = json.loads(path.read_text())
        cases = item.pop("cases")
        samples = [median(c["ms"]) for c in cases]
        item.update(
            run=path.stem, median_ms=median(samples), sd_ms=pstdev(samples), groups={}
        )
        for group in sorted({c["group"] for c in cases}):
            selected = [c for c in cases if c["group"] == group]
            horizons = {}
            for step in selected[0]["metrics"]:
                metrics = [c["metrics"][step] for c in selected]
                if not all(r["finite"] for r in metrics):
                    horizons[step] = {"finite": False}
                    continue
                horizons[step] = {
                    k: mean(r[k] for r in metrics)
                    for k in ("relative_l1", "relative_l2", "scaled_rmse")
                }
                horizons[step].update(
                    l2_sd=pstdev(r["relative_l2"] for r in metrics),
                    rmse=[mean(r["rmse"][i] for r in metrics) for i in range(3)],
                    abs_mass=mean(abs(r["mass_drift"]) for r in metrics),
                    abs_energy=mean(abs(r["energy_drift"]) for r in metrics),
                )
            item["groups"][group] = {
                "horizons": horizons,
                "finite": all(c["finite"] for c in selected),
                "minimum_depth": min(c["minimum_depth"] for c in selected),
                "seeds": [c["seed"] for c in selected],
            }
        view = root / "views" / (path.stem + ".npz")
        if view.is_file():
            with view.open("rb") as stream:
                item["view_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        rows.append(item)
    return {
        "format": 1,
        "experiments": {
            p.stem: json.loads(p.read_text())
            for p in [root / "checks.json", root / "gpu.json"]
            if p.is_file()
        },
        "datasets": {
            p.stem: json.loads(p.read_text()) for p in sorted(root.glob("data-*.json"))
        },
        "runs": rows,
    }


def base_rows(rows, method, n):
    return [
        r
        for r in rows
        if r["grid"] == n
        and r["method"] == method
        and r["threads"] == 1
        and r["device"] == "cpu"
        and not r["run"].endswith("paired")
        and (
            not r["checkpoint"] or r["checkpoint"].startswith(f"{method}-{n}-24-base-")
        )
    ]


def plot(data, path):
    fig = Figure(figsize=(9, 3.8), layout="constrained")
    cost, accuracy = fig.subplots(1, 2)
    grids = sorted({r["grid"] for r in data["runs"]})
    for method in ("muscl", "numba", "rusanov", "cnn", "fno"):
        points = [(n, base_rows(data["runs"], method, n)) for n in grids]
        points = [(n, r) for n, r in points if r]
        if not points:
            continue
        x = [n for n, _ in points]
        cost.plot(
            x,
            [mean(r["median_ms"] for r in rs) for _, rs in points],
            ".-",
            label=method.upper(),
        )
        if method in ("cnn", "fno", "rusanov"):
            accuracy.plot(
                x,
                [
                    mean(r["groups"]["id"]["horizons"]["24"]["relative_l2"] for r in rs)
                    for _, rs in points
                ],
                ".-",
                label=method.upper(),
            )
    cost.set(yscale="log", ylabel="Warm rollout (ms, log scale)")
    accuracy.set(ylabel="ID relative L2 at 96 min")
    for ax in (cost, accuracy):
        ax.set(xlabel="Cells per side", xticks=grids)
        ax.legend(fontsize=8)
    fig.savefig(path, dpi=150)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("json", type=Path)
    p.add_argument("figure", type=Path)
    args = p.parse_args()
    report = collect(args.root)
    args.json.write_text(json.dumps(report, separators=(",", ":"), allow_nan=False))
    plot(report, args.figure)
