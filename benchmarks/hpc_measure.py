"""Evaluate an existing scaling study. Fresh processes isolate first calls and process RSS."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def measure(root, grids, numba_path=None, cuda_path=None, gpu=False):
    rows = root / "measurements"
    rows.mkdir(exist_ok=True)

    def job(
        grid,
        method,
        src=None,
        ck=None,
        device="cpu",
        threads=1,
        packages=None,
        label="",
    ):
        tag = f"{grid}-{ck or method}-{device}-{threads}{label}"
        dest = rows / (tag + ".json")
        if dest.exists():
            return
        args = [
            sys.executable,
            str(Path(__file__).with_name("hpc_worker.py")),
            str(root),
            str(grid),
            method,
            str(dest),
            "--threads",
            str(threads),
            "--device",
            device,
        ]
        if ck:
            args += ["--source", src, "--checkpoint", ck]
        if grid == 32 and (not ck or ck.endswith("base-11")):
            args += ["--profile"]
        env = os.environ | {
            "OMP_NUM_THREADS": str(threads),
            "MKL_NUM_THREADS": str(threads),
            "OPENBLAS_NUM_THREADS": str(threads),
        }
        if packages is not None:
            env["PYTHONPATH"] = (
                str(packages.resolve()) + os.pathsep + env.get("PYTHONPATH", "")
            )
        subprocess.run(args, env=env, check=True)
        print(tag, flush=True)

    if gpu:
        for n in grids:
            for kind in ("cnn", "fno"):
                ck = f"{kind}-{n}-24-base-11"
                for dev in ("cpu", "cuda"):
                    job(
                        n,
                        kind,
                        f"data-{n}-24",
                        ck,
                        dev,
                        packages=cuda_path,
                        label="-paired",
                    )
        return
    for n in grids:
        for method in ("muscl", "rusanov", "persistence"):
            job(n, method)
        if numba_path is not None:
            job(n, "numba", packages=numba_path)
        for ck in sorted(root.glob(f"*-{n}-*-*.pt")):
            kind, _, size, _, _ = ck.stem.split("-")
            job(n, kind, f"data-{n}-{size}", ck.stem)
        if n != 16:
            for seed in (11, 29):
                job(n, "fno", "data-16-24", f"fno-16-24-base-{seed}")
        if n == 32:
            for kind in ("cnn", "fno"):
                job(n, kind, "data-32-24", f"{kind}-32-24-base-11", threads=4)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--grids", nargs="+", type=int, default=[16, 32, 64])
    p.add_argument("--numba-path", type=Path)
    p.add_argument("--cuda-path", type=Path)
    p.add_argument("--gpu", action="store_true")
    measure(**vars(p.parse_args()))
