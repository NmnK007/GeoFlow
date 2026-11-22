"""Offline commands for the optional Neural laboratory."""

import argparse
import json
from pathlib import Path

from .data import generate
from .resources import peak_mib


def main(argv=None):
    parser = argparse.ArgumentParser(prog="geoflow-neural")
    sub = parser.add_subparsers(dest="action", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("out", type=Path)
    for name, default in (
        ("grid", 16),
        ("steps", 16),
        ("train", 16),
        ("validation", 4),
        ("test", 4),
        ("seed", 1200),
    ):
        gen.add_argument("--" + name, type=int, default=default)
    gen.add_argument("--interval", type=float, default=240.0)
    tr = sub.add_parser("train")
    tr.add_argument("dataset", type=Path)
    tr.add_argument("checkpoint", type=Path)
    tr.add_argument("--kind", choices=("cnn", "fno"), default="fno")
    for name, default in (
        ("epochs", 24),
        ("seed", 11),
        ("batch", 16),
        ("patience", 8),
        ("width", 12),
        ("modes", 4),
        ("threads", 1),
    ):
        tr.add_argument("--" + name, type=int, default=default)
    tr.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    tr.add_argument("--lr", type=float, default=0.003)
    for name in ("mass", "energy", "positive", "multi"):
        tr.add_argument("--" + name, type=float, default=0.0)
    tr.add_argument("--resume", action="store_true")
    for action in ("evaluate", "infer"):
        p = sub.add_parser(action)
        p.add_argument("dataset", type=Path)
        p.add_argument("out", type=Path)
        p.add_argument(
            "--checkpoint",
            type=Path,
            required=action == "infer",
            action="append" if action == "evaluate" else "store",
        )
        if action == "infer":
            p.add_argument("--index", type=int, required=True)
            p.add_argument("--steps", type=int)
        p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    opts = vars(parser.parse_args(argv))
    action = opts.pop("action")
    try:
        if action == "generate":
            m = generate(**opts)
            result = {k: m[k] for k in ("generation_s", "fingerprint")}
        elif action == "train":
            import torch

            from .train import train

            opts["weights"] = {
                key: opts.pop(key) for key in ("mass", "energy", "positive", "multi")
            }
            ck = train(**opts)
            result = {k: ck[k] for k in ("best_epoch", "best_loss", "training_s")}
            result["gpu_peak_mib"] = (
                torch.cuda.max_memory_allocated() / 2**20
                if opts["device"] == "cuda"
                else None
            )
        else:
            from .evaluate import evaluate, infer

            result = (infer if action == "infer" else evaluate)(**opts)
    except (
        ImportError,
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        FloatingPointError,
    ) as e:
        parser.exit(1, f"GeoFlow Neural: {e}\n")
    print(json.dumps(dict(result, process_peak_mib=peak_mib()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
