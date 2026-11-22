import shutil
from pathlib import Path

import numpy as np
import pytest

from geoflow.config import Config
from geoflow.neural.data import GROUPS, generate, indices, integrate, load
from geoflow.state import conserved


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    folder = tmp_path_factory.mktemp("neural")
    generate(folder / "data", grid=8, train=2, validation=1, test=1, steps=4)
    return folder


def test_reproducibility_and_split_isolation(dataset, tmp_path):
    m, x = load(dataset / "data")
    other = generate(tmp_path / "copy", grid=8, train=2, validation=1, test=1, steps=4)
    assert m["fingerprint"] == other["fingerprint"]
    groups = [{m["trajectories"][i]["seed"] for i in indices(m, g)} for g in GROUPS]
    assert sum(map(len, groups)) == len(set.union(*groups)) == len(x)
    train = x[indices(m, "train"), : m["train_steps"] + 1]
    np.testing.assert_allclose(m["mean"], train.mean(axis=(0, 1, 3, 4)))
    np.testing.assert_allclose(m["std"], train.std(axis=(0, 1, 3, 4)))
    assert all(
        abs(s["f"]) == 5e-5 for s in m["trajectories"] if s["group"] == "rotation"
    )
    assert all(
        s["cx"] > 0.75 and abs(s["amplitude"]) >= 1.4
        for s in m["trajectories"]
        if s["group"] == "amplitude_location"
    )
    with (tmp_path / "copy" / "states.npy").open("ab") as f:
        f.write(b"broken")
    with pytest.raises(ValueError, match="fingerprint"):
        load(tmp_path / "copy")


def test_uniform_inertial_reference():
    c = Config(scheme="muscl", nx=8, ny=8, f_override_s_inv=1e-4)
    times = np.array([0.0, 240.0, 480.0])
    h = np.full((8, 8), 100.0)
    s = integrate(c, conserved(h, np.ones_like(h), np.zeros_like(h)), times)
    np.testing.assert_allclose(s[:, 0], 100.0)
    np.testing.assert_allclose(s[:, 1, 0, 0], np.cos(c.f * times), atol=2e-14)
    np.testing.assert_allclose(s[:, 2, 0, 0], -np.sin(c.f * times), atol=2e-14)


@pytest.mark.parametrize("kind", ["cnn", "fno"])
def test_models_and_normalization(dataset, kind):
    torch = pytest.importorskip("torch")
    from geoflow.neural.models import Operator, denormalize, normalize

    m, x = load(dataset / "data")
    np.testing.assert_allclose(denormalize(normalize(x[0], m), m), x[0], atol=1e-13)
    t = torch.tensor(normalize(x[0, :2], m), dtype=torch.float32)
    pred = Operator(kind, width=4, modes=2)(t, torch.zeros(2))
    assert pred.shape == t.shape and torch.isfinite(pred).all()


def test_physical_metrics(dataset):
    pytest.importorskip("torch")
    from geoflow.neural.evaluate import diagnostics

    m, _ = load(dataset / "data")
    s = np.zeros((2, 3, 8, 8))
    s[:, 0] = 101
    p = s.copy()
    p[1, 0] += 1
    row = diagnostics(p, s, m)[1]
    assert row["rmse"] == [1.0, 0.0, 0.0]
    assert row["relative_l2"] == pytest.approx(1.0)
    assert row["mass_drift"] == pytest.approx(1 / 101)
    assert row["energy_drift"] == pytest.approx(3.0)
    assert row["min_h"] == 102.0


@pytest.fixture(scope="module")
def trained(dataset):
    pytest.importorskip("torch")
    from geoflow.neural.train import train

    ck = dataset / "tiny.pt"
    train(dataset / "data", ck, width=4, modes=2, epochs=1)
    return ck


def test_saved_rollout_resume_and_invalid_checkpoint(dataset, trained, tmp_path):
    import torch

    from geoflow.neural.evaluate import infer
    from geoflow.neural.train import read_checkpoint, train

    m, _ = load(dataset / "data")
    for name in ("a", "b"):
        infer(dataset / "data", tmp_path / (name + ".npz"), trained, 3, steps=3)
    with np.load(tmp_path / "a.npz") as a, np.load(tmp_path / "b.npz") as b:
        np.testing.assert_array_equal(a["prediction"], b["prediction"])
        np.testing.assert_array_equal(a["prediction"][0], a["reference"][0])
        assert a["prediction"].shape == (4, 3, 8, 8)
    with pytest.raises(ValueError, match="fingerprint"):
        read_checkpoint(trained, m | {"fingerprint": "bad"})
    with pytest.raises(ValueError):
        infer(dataset / "data", tmp_path / "bad.npz", trained, 99)
    direct = train(dataset / "data", tmp_path / "direct.pt", width=4, modes=2, epochs=2)
    copy = tmp_path / "resumed.pt"
    shutil.copyfile(trained, copy)
    resumed = train(dataset / "data", copy, width=4, modes=2, epochs=2, resume=True)
    assert direct["history"] == resumed["history"]
    for k in direct["last"]:
        assert torch.equal(direct["last"][k], resumed["last"][k])


def test_neural_lab(dataset, trained):
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_file(Path("app.py").resolve(), default_timeout=60).run()
    app.radio(key="lab_mode").set_value("Neural").run()
    app.text_input[0].set_value(str(dataset)).run()
    next(b for b in app.button if b.label == "Compare rollout on CPU").click().run()
    assert not app.exception and not app.error
    original = app.session_state["neural_result"]
    app.slider[0].set_value(2).run()
    assert not app.exception and original[1] is app.session_state["neural_result"][1]
