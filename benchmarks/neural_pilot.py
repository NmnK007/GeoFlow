"""Reproduce the CPU pilot in a fresh output directory: python benchmarks/neural_pilot.py outputs/my-pilot."""

import json
import subprocess
import sys
from pathlib import Path


def run(out):
    out.mkdir(parents=True, exist_ok=False)

    def command(name, *args):
        result = subprocess.run(
            [sys.executable, "-m", "geoflow.neural.cli", *map(str, args)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        info = json.loads(result.stdout)
        (out / (name + ".json")).write_text(json.dumps(info, indent=2))
        print(name, info, flush=True)

    data = out / "data"
    command("generation", "generate", data)
    checkpoints = []
    variants = [
        ("cnn", "cnn", ()),
        ("fno", "fno", ()),
        (
            "physics",
            "fno",
            ("--mass", 0.1, "--energy", 0.05, "--positive", 1, "--multi", 0.25),
        ),
    ]
    for term, weight in (
        ("mass", 0.1),
        ("energy", 0.05),
        ("positive", 1.0),
        ("multi", 0.25),
    ):
        variants.append((term, "fno", ("--" + term, weight)))
    for seed in (11, 29):
        for name, kind, extra in variants:
            job = f"{name}-{seed}"
            ck = out / (job + ".pt")
            command(job, "train", data, ck, "--kind", kind, "--seed", seed, *extra)
            checkpoints.extend(("--checkpoint", ck))
    command("evaluation", "evaluate", data, out / "report.json", *checkpoints)


if __name__ == "__main__":
    run(Path(sys.argv[1]))
