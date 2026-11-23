"""Generate datasets and train the predefined CPU scaling matrix. Resumable in a dedicated directory."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(root, grids=(16, 32, 64)):
    root.mkdir(parents=True, exist_ok=True)
    env = os.environ | {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }

    def command(label, *args):
        log = root / (label + ".json")
        if log.exists():
            return
        proc = subprocess.run(
            [sys.executable, "-m", "geoflow.neural.cli", *map(str, args)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr)
        info = json.loads(proc.stdout)
        log.write_text(json.dumps(info, indent=2))
        print(label, flush=True)

    for grid in grids:
        for size in (24, 8) if grid == 32 else (24,):
            data = root / f"data-{grid}-{size}"
            command(
                data.name,
                "generate",
                data,
                "--grid",
                grid,
                "--train",
                size,
                "--validation",
                3,
                "--test",
                3,
                "--steps",
                24,
                "--scaling",
                "--workers",
                2,
            )
            for kind in ("cnn", "fno"):
                for large in (False, True) if grid == 32 and size == 24 else (False,):
                    for seed in (11, 29):
                        job = f"{kind}-{grid}-{size}-{'large' if large else 'base'}-{seed}"
                        extra = (
                            ("--width", 16, "--depth", 3, "--modes", 6) if large else ()
                        )
                        command(
                            job,
                            "train",
                            data,
                            root / (job + ".pt"),
                            "--kind",
                            kind,
                            "--seed",
                            seed,
                            "--epochs",
                            16,
                            *extra,
                        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--grids", nargs="+", type=int, default=[16, 32, 64])
    args = p.parse_args()
    run(args.root, args.grids)
