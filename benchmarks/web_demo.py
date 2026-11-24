"""Rebuild offline demos from the solver and optional verified release artifacts."""

import argparse
import hashlib
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np

from geoflow.web.service import (
    DEMO,
    MODELS,
    configuration,
    model_row,
    simulation,
    write,
)


def bundle_study(study):
    from geoflow.neural.data import indices, load
    from geoflow.neural.metrics import diagnostics
    from geoflow.neural.train import read_checkpoint

    manifest, states = load(study / "data-16-24")
    first = indices(manifest, "id")[0]
    summaries = {}
    for kind in MODELS:
        row = model_row(kind)
        path = study / "views" / (row["run"] + ".npz")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != row["view_sha256"]:
                raise ValueError("field archive differs from v0.5")
        _, ck = read_checkpoint(study / (row["checkpoint"] + ".pt"), manifest)
        with np.load(path) as data:
            ref, pred = data["reference"], data["prediction"]
            np.testing.assert_array_equal(ref, states[first])
            summaries[kind] = {
                "times": manifest["times"],
                "seed": manifest["trajectories"][first]["seed"],
                "config": manifest["config"],
                "fingerprint": manifest["fingerprint"],
                "architecture": ck["architecture"],
                "history": ck["history"],
                "diagnostics": diagnostics(pred, ref, manifest),
                "reference_diagnostics": diagnostics(ref, ref, manifest),
            }
        shutil.copyfile(path, DEMO / (kind + ".npz"))
    write(DEMO / "models.json", summaries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", type=Path)
    parser.add_argument("--earth-case", type=Path)
    args = parser.parse_args()
    for name, latitude in (("gaussian", 0), ("rotating", 45)):
        out = DEMO / name
        out.mkdir(exist_ok=True, parents=True)
        cfg = configuration("gaussian_bump", {})
        simulation(
            out, replace(cfg, nx=32, ny=32, sample_s=1800, latitude_deg=latitude)
        )
    if args.study:
        bundle_study(args.study)
    if args.earth_case:
        for name in ("region.nc", "matched.csv", "validation.json"):
            shutil.copyfile(args.earth_case / name, DEMO / name)
