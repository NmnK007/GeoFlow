"""Matched-horizon, batch-one open-loop evaluation against independent solver trajectories."""

import json
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np
import torch

from geoflow.config import Config
from geoflow.state import conserved

from .data import groups, indices, integrate, load
from .metrics import diagnostics
from .models import denormalize, normalize
from .resources import peak_mib
from .train import read_checkpoint


@torch.inference_mode()
def rollout(model, m, start, f, steps, device="cpu"):
    if steps < 0:
        raise ValueError("negative rollout horizon")
    x = torch.as_tensor(normalize(start, m), dtype=torch.float32, device=device)[None]
    rotation = torch.tensor([f / 1e-4], dtype=x.dtype, device=device)
    later = []
    for _ in range(steps):
        x = model(x, rotation)
        later.append(x[0])
    if not later:
        return start[None].copy()
    return np.concatenate(
        (start[None], denormalize(torch.stack(later).cpu().numpy(), m))
    )


def timed(fn, *args):
    start = perf_counter()
    value = fn(*args)
    return value, (perf_counter() - start) * 1000


def predict(name, c, ref, model, m, times, device):
    if name == "muscl":
        return integrate(c, conserved(*ref[0]), times)
    if name == "persistence":
        return np.repeat(ref[:1], len(times), axis=0)
    return rollout(model, m, ref[0], c.f, len(times) - 1, device)


def evaluate(dataset, out, checkpoint=None, device="cpu"):
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    torch.set_num_threads(1)
    m, states = load(dataset)
    times = np.asarray(m["times"])
    paths = list(checkpoint or [])
    if len({Path(p).stem for p in paths} | {"muscl", "persistence"}) != len(paths) + 2:
        raise ValueError("duplicate model names")
    record = {
        "dataset": m["fingerprint"],
        "device": device,
        "threads": 1,
        "horizon_s": times[-1],
        "models": {},
    }
    for name, path in [("muscl", None), ("persistence", None)] + [
        (Path(p).stem, p) for p in paths
    ]:
        info = {"load_ms": 0.0, "cases": []}
        model = None
        if path:
            (model, ck), info["load_ms"] = timed(read_checkpoint, path, m, device)
            info.update(
                kind=ck["architecture"]["kind"],
                seed=ck["settings"]["seed"],
                best_epoch=ck["best_epoch"],
                params=sum(p.numel() for p in model.parameters()),
                weights=ck["settings"]["weights"],
            )
        for group in groups(m)[2:]:
            for idx in indices(m, group):
                ref = states[idx]
                spec = m["trajectories"][idx]
                c = Config(**(m["config"] | {"f_override_s_inv": spec["f"]}))

                if not info["cases"]:
                    _, info["warmup_ms"] = timed(
                        predict, name, c, ref, model, m, times, device
                    )
                runtimes = []
                for _ in range(3):
                    pred, ms = timed(predict, name, c, ref, model, m, times, device)
                    runtimes.append(ms)
                if name == "muscl" and not np.array_equal(pred, ref):
                    # Roundoff from primitive -> conserved conversion is possible for general inputs.
                    np.testing.assert_allclose(pred, ref, rtol=1e-12, atol=1e-12)
                info["cases"].append(
                    {
                        "index": idx,
                        "group": group,
                        "seed": spec["seed"],
                        "runtime_ms": median(runtimes),
                        "metrics": diagnostics(pred, ref, m),
                    }
                )
        record["models"][name] = info
    record.update(
        process_peak_mib=peak_mib(),
        gpu_peak_mib=torch.cuda.max_memory_allocated() / 2**20
        if device == "cuda"
        else None,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, allow_nan=False)
    with out.open("x", encoding="utf8") as stream:
        stream.write(payload)
    return {"report": str(out), "models": list(record["models"])}


def infer(dataset, out, checkpoint, index, steps=None, device="cpu"):
    m, states = load(dataset)
    if not 0 <= index < len(states):
        raise ValueError("unknown trajectory")
    steps = len(m["times"]) - 1 if steps is None else steps
    if not 0 <= steps < len(m["times"]):
        raise ValueError("outside available reference horizon")
    model, ck = read_checkpoint(checkpoint, m, device)
    torch.set_num_threads(1)
    p = rollout(
        model, m, states[index, 0], m["trajectories"][index]["f"], steps, device
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as stream:
        np.savez(
            stream,
            prediction=p,
            reference=states[index, : steps + 1],
            time_s=m["times"][: steps + 1],
            dataset=m["fingerprint"],
            seed=m["trajectories"][index]["seed"],
            best_epoch=ck["best_epoch"],
        )
    return {"output": str(out), "finite": bool(np.isfinite(p).all()), "steps": steps}
