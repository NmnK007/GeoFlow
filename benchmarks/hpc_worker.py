"""One isolated benchmark process per method/checkpoint, grid and device."""

import argparse
import cProfile
import json
import platform
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from time import perf_counter

started = perf_counter()
import numpy as np

from geoflow.config import Config
from geoflow.hpc.protocol import compatible, device_name, score
from geoflow.neural.data import groups, integrate, load
from geoflow.neural.resources import peak_mib
from geoflow.state import conserved


def benchmark(
    root, grid, method, source, checkpoint, device, threads, output, profile=False
):
    start = perf_counter()
    target, states = load(root / f"data-{grid}-24")
    data_ms = (perf_counter() - start) * 1000
    times = target["times"]
    fit = {}
    load_ms = transfer_ms = 0.0
    gpu = None
    framework = np.__version__
    arch = {}
    if checkpoint:
        import torch

        from geoflow.neural.evaluate import rollout
        from geoflow.neural.train import read_checkpoint

        device = device_name(device, torch.cuda.is_available())
        torch.set_num_threads(threads)
        m = target if source == f"data-{grid}-24" else load(root / source)[0]
        start = perf_counter()
        model, ck = read_checkpoint(root / (checkpoint + ".pt"), m, device)
        arch = ck["architecture"]
        compatible(m, target, arch)
        framework = str(torch.__version__)
        if device == "cuda":
            torch.cuda.synchronize()
            gpu = torch.cuda.get_device_name()
        load_ms = (perf_counter() - start) * 1000
        fit = json.loads((root / (checkpoint + ".json")).read_text())
        params = sum(p.numel() for p in model.parameters())
    else:
        params = 0
        device = "cpu"
        if method == "numba":
            from jit_flux import compiled

            from geoflow import muscl

            muscl.rusanov = compiled
    out = {
        "method": method,
        "grid": grid,
        "source": source,
        "checkpoint": checkpoint,
        "device": device,
        "threads": threads,
        "framework": framework,
        "gpu": gpu,
        "training": fit,
        "architecture": arch,
        "parameters": params,
        "fingerprint": target["fingerprint"],
        "load_ms": load_ms,
        "dataset_load_ms": data_ms,
        "setup_ms": (perf_counter() - started) * 1000,
        "python": platform.python_version(),
        "cases": [],
    }
    if checkpoint:
        out.update(
            source_fingerprint=m["fingerprint"],
            training_count=sum(q["group"] == "train" for q in m["trajectories"]),
        )
    view = root / "views" / (output.stem + ".npz")
    view.parent.mkdir(exist_ok=True)
    for i, spec in enumerate(target["trajectories"]):
        if spec["group"] not in groups(target)[2:]:
            continue
        ref = states[i]
        cfg = replace(
            Config(**target["config"]),
            f_override_s_inv=spec["f"],
            scheme="rusanov" if method == "rusanov" else "muscl",
        )

        def predict(ref=ref, spec=spec, cfg=cfg):
            if checkpoint:
                return rollout(model, m, ref[0], spec["f"], len(times) - 1, device)
            if method == "persistence":
                return np.repeat(ref[:1], len(ref), axis=0)
            return integrate(cfg, conserved(*ref[0]), times)

        if not out["cases"]:
            start = perf_counter()
            compile_times = []
            timer = nullcontext()
            if method == "numba":
                from numba.core.event import install_timer

                timer = install_timer("numba:compile", compile_times.append)
            with timer:
                predict()
            out["compile_ms"] = sum(compile_times) * 1000
            if device == "cuda":
                torch.cuda.synchronize()
            out["first_rollout_ms"] = (perf_counter() - start) * 1000
        samples = []
        for _ in range(3):
            if device == "cuda":
                torch.cuda.synchronize()
            start = perf_counter()
            pred = predict()
            if device == "cuda":
                torch.cuda.synchronize()
            samples.append((perf_counter() - start) * 1000)
        if method in ("muscl", "numba"):
            np.testing.assert_allclose(pred, ref, atol=1e-11, rtol=1e-11)
        metrics = score(pred, ref, target)
        if not out["cases"]:
            np.savez_compressed(view, reference=ref, prediction=pred, time_s=times)
            if profile:
                cProfile.runctx(
                    "predict()", globals(), locals(), str(output.with_suffix(".prof"))
                )
            if device == "cuda":
                # Measure transfers of one float32 state in, one complete float32 history out.
                x = torch.zeros(ref.shape[1:])
                y = torch.zeros(ref.shape, device=device)
                torch.cuda.synchronize()
                start = perf_counter()
                for _ in range(10):
                    x.to(device)
                    y.cpu()
                torch.cuda.synchronize()
                transfer_ms = (perf_counter() - start) * 100
        out["cases"].append(
            {
                "seed": spec["seed"],
                "group": spec["group"],
                "ms": samples,
                "metrics": {str(j): metrics[j] for j in (1, 4, 16, len(times) - 1)},
                "finite": all(r["finite"] for r in metrics),
                "minimum_depth": min(
                    (r["min_h"] for r in metrics if r["finite"]), default=None
                ),
            }
        )
    out.update(
        transfer_ms=transfer_ms,
        peak_mib=peak_mib(),
        gpu_peak_mib=torch.cuda.max_memory_allocated() / 2**20
        if device == "cuda"
        else None,
    )
    output.write_text(json.dumps(out, allow_nan=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("grid", type=int)
    p.add_argument(
        "method", choices=("muscl", "numba", "rusanov", "cnn", "fno", "persistence")
    )
    p.add_argument("output", type=Path)
    p.add_argument("--source")
    p.add_argument("--checkpoint")
    p.add_argument("--device", default="cpu")
    p.add_argument("--threads", type=int, default=1)
    p.add_argument("--profile", action="store_true")
    benchmark(**vars(p.parse_args()))
