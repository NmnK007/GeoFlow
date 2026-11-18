import csv
import json
from pathlib import Path

import numpy as np
import pytest

from geoflow import cli
from geoflow.config import load_config
from geoflow.solver import run_simulation


@pytest.mark.parametrize("path", sorted(Path("configs").glob("*.json")))
def test_preset(path):
    c = load_config(path)
    r = run_simulation(c)
    assert r.time[-1] == c.duration_s
    assert max(row["volume_drift"] for row in r.diagnostics) <= 1e-10
    assert all(row["cfl"] <= c.cfl + 1e-15 for row in r.diagnostics)


def test_run_roundtrip(tmp_path):
    out = tmp_path / "demo"
    args = ["run", "--config", "configs/lake_rest.json", "--out", str(out)]
    assert cli.main(args) == 0
    c = load_config(Path(args[2]))
    with np.load(out / "fields.npz", allow_pickle=False) as f:
        assert f["h"].shape == (c.intervals + 1, c.ny, c.nx)
        np.testing.assert_equal(f["h"], c.depth_m)
        assert set(f.files) == {"h", "u", "v", "x", "y", "time"}
    with (out / "diagnostics.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert float(rows[-1]["time_s"]) == c.duration_s
    assert rows[-1]["relative_energy_change"] == ""
    info = json.loads((out / "metadata.json").read_text())
    assert info["status"] == "completed" and info["config"]["boundary_x"] == "periodic"
    assert (out / "height_anomaly.png").read_bytes().startswith(b"\x89PNG")
    assert cli.main(args) == 1
    assert cli.main(args + ["--overwrite"]) == 0


def test_failed_run(tmp_path):
    config = tmp_path / "bad.json"
    config.write_text('{"max_steps":1}')
    out = tmp_path / "out"
    assert cli.main(["run", "--config", str(config), "--out", str(out)]) == 1
    info = json.loads((out / "metadata.json").read_text())
    assert info["status"] == "failed" and "step limit" in info["error"]


def test_failed_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli,
        "verify",
        lambda: {"passed": False, "convergence": [], "errors": {"wave": "failed"}},
    )
    assert cli.main(["verify", "--out", str(tmp_path)]) == 1
    assert json.loads((tmp_path / "verification.json").read_text())["errors"]
