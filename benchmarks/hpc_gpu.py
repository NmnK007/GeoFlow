"""Optional CUDA batch and precision probes in the selected torch environment."""

import argparse
import importlib.util
import json
from pathlib import Path
from statistics import median
from time import perf_counter

import torch

from geoflow.neural.data import indices, load
from geoflow.neural.models import normalize
from geoflow.neural.train import read_checkpoint, train


def study(root):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    m, x = load(root / "data-32-24")
    out = {
        "torch": str(torch.__version__),
        "gpu": torch.cuda.get_device_name(),
        "batch": [],
        "triton_available": importlib.util.find_spec("triton") is not None,
    }
    ids = (
        indices(m, "id")
        + indices(m, "amplitude")
        + indices(m, "position")
        + indices(m, "rotation")
    )
    for kind in ("cnn", "fno"):
        ck = root / f"{kind}-32-24-base-11.pt"
        for device in ("cpu", "cuda"):
            model, _ = read_checkpoint(ck, m, device)
            torch.set_num_threads(1)
            for batch in (1, 4, 12):
                t = torch.tensor(
                    normalize(x[ids[:batch], 0], m), dtype=torch.float32, device=device
                )
                f = torch.tensor(
                    [m["trajectories"][i]["f"] / 1e-4 for i in ids[:batch]],
                    device=device,
                )
                with torch.inference_mode():
                    model(t, f)
                    times = []
                    for _ in range(5):
                        if device == "cuda":
                            torch.cuda.synchronize()
                        start = perf_counter()
                        y = t
                        for _ in range(24):
                            y = model(y, f)
                        if device == "cuda":
                            torch.cuda.synchronize()
                        times.append((perf_counter() - start) * 1000)
                    row = {
                        "kind": kind,
                        "device": device,
                        "batch": batch,
                        "resident_ms": median(times),
                    }
                    if device == "cuda" and kind == "cnn":
                        with torch.autocast(device_type="cuda", dtype=torch.float16):
                            mixed = t
                            for _ in range(24):
                                mixed = model(mixed, f)
                        row["mixed_vs_fp32_relative"] = float(
                            torch.linalg.norm(mixed - y) / torch.linalg.norm(y)
                        )
                    out["batch"].append(row)
    # Fixed epoch count; timing includes the same optimizer and validation work.
    for b in (8, 32):
        torch.cuda.reset_peak_memory_stats()
        path = root / f"gpu-training-b{b}.pt"
        log = root / f"gpu-training-b{b}.json"
        if not log.exists():
            fit = train(
                root / "data-32-24", path, kind="fno", epochs=4, batch=b, device="cuda"
            )
            log.write_text(
                json.dumps(
                    {
                        "epochs": len(fit["history"]),
                        "best_validation": fit["best_loss"],
                        "seconds": fit["training_s"],
                        "gpu_peak_mib": torch.cuda.max_memory_allocated() / 2**20,
                    }
                )
            )
        out[f"train_batch{b}"] = json.loads(log.read_text())
    (root / "gpu.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    study(p.parse_args().root)
