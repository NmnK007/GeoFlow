import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from geoflow.hpc.protocol import compatible, device_name, score
from geoflow.neural.data import generate, load


def test_split_protocol_and_parallel_generation(tmp_path):
    opts = {
        "grid": 8,
        "steps": 4,
        "train": 2,
        "validation": 1,
        "test": 1,
        "scaling": True,
    }
    small = generate(tmp_path / "serial", **opts)
    parallel = generate(tmp_path / "parallel", **opts, workers=2)
    assert small["fingerprint"] == parallel["fingerprint"]
    big = generate(tmp_path / "fine", **(opts | {"train": 3, "grid": 12}))
    test = [s for s in small["trajectories"] if s["group"] != "train"]
    assert test == [s for s in big["trajectories"] if s["group"] != "train"]
    a = next(s for s in test if s["group"] == "amplitude")
    b = next(s for s in test if s["group"] == "position")
    assert abs(a["amplitude"]) >= 1.4 and a["cx"] <= 0.65 and a["cy"] <= 0.65
    assert abs(b["amplitude"]) <= 1.2 and b["cx"] >= 0.76 and b["cy"] >= 0.76
    compatible(small, big, {"kind": "fno", "modes": 3})
    with pytest.raises(ValueError):
        compatible(small, big, {"kind": "cnn"})
    with pytest.raises(ValueError):
        compatible(small, big, {"kind": "fno", "modes": 7})
    with pytest.raises(ValueError):
        compatible(small, big | {"times": [0]}, {"kind": "fno", "modes": 2})
    m, states = load(tmp_path / "fine")
    ref = states[0].copy()
    pred = ref.copy()
    pred[:, 0] += 0.1
    r = score(pred, ref, m)[-1]
    norm = np.asarray(m["std"])[:, None, None]
    anomaly = ref[-1] - np.array([100, 0, 0])[:, None, None]
    assert r["relative_l1"] == pytest.approx(
        np.abs((pred[-1] - ref[-1]) / norm).sum() / np.abs(anomaly / norm).sum()
    )
    assert r["rmse"][0] == pytest.approx(0.1)


def test_transfer_shape_and_device():
    torch = pytest.importorskip("torch")
    from geoflow.neural.models import Operator

    assert device_name("auto", False) == "cpu" and device_name("auto", True) == "cuda"
    with pytest.raises(ValueError):
        device_name("cuda", False)
    model = Operator("fno", width=6, depth=3, modes=3)
    for n in (8, 16):
        x = torch.zeros(1, 3, n, n)
        assert model(x, torch.zeros(1)).shape == x.shape
    with pytest.raises(ValueError):
        model(torch.zeros(1, 3, 4, 4), torch.zeros(1))


def test_hpc_lab():
    st = pytest.importorskip("streamlit.testing.v1")
    app = st.AppTest.from_file(Path("app.py").resolve(), default_timeout=60).run()
    app.radio(key="lab_mode").set_value("HPC").run()
    assert not app.error and not app.exception
    app.selectbox[0].set_value(32).run()
    assert app.dataframe and not app.exception
    app.multiselect[0].set_value(["fno"]).run()
    assert len(app.dataframe[0].value) > 0 and not app.exception


def test_benchmark_times_and_metadata(tmp_path):
    manifest = generate(
        tmp_path / "data-8-24",
        grid=8,
        steps=16,
        train=1,
        validation=1,
        test=1,
        scaling=True,
    )
    output = tmp_path / "pilot.json"
    script = Path(__file__).resolve().parents[1] / "benchmarks" / "hpc_worker.py"
    subprocess.run(
        [sys.executable, str(script), str(tmp_path), "8", "persistence", str(output)],
        check=True,
    )
    row = json.loads(output.read_text())
    assert row["fingerprint"] == manifest["fingerprint"]
    assert row["device"] == "cpu" and row["gpu_peak_mib"] is None
    assert row["dataset_load_ms"] >= 0 and row["first_rollout_ms"] > 0
    assert row["setup_ms"] >= row["dataset_load_ms"] and row["peak_mib"] > 0
    assert {c["group"] for c in row["cases"]} == {
        "id",
        "amplitude",
        "position",
        "rotation",
    }
    for case in row["cases"]:
        assert len(case["ms"]) == 3 and min(case["ms"]) > 0
        assert case["finite"] and case["metrics"]["16"]["mass_drift"] == 0
    with np.load(tmp_path / "views" / "pilot.npz") as arrays:
        np.testing.assert_array_equal(arrays["prediction"][-1], arrays["reference"][0])
