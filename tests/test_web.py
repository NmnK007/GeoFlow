"""HTTP contract and numerical parity through the same API used by Next.js."""

import io
import time
from zipfile import ZipFile

import numpy as np
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from geoflow.solver import run_simulation
from geoflow.web import service as s
from geoflow.web.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFLOW_ARTIFACTS", str(tmp_path))
    with TestClient(app) as c:
        yield c
    assert not list(tmp_path.iterdir())


def done(client, key):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{key}").json()
        if job["state"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.05)
    pytest.fail("job never finished")


def test_solver_round_trip(client):
    v = "/api/v1"
    p = {"nx": 12, "ny": 8, "latitude_deg": 45}
    r = client.post(
        v + "/simulations", json={"preset": "gaussian_bump", "parameters": p}
    )
    assert r.status_code == 202
    key = r.json()["id"]
    assert done(client, key)["state"] == "completed"
    prefix = v + "/jobs/" + key
    ref = run_simulation(s.configuration("gaussian_bump", p))
    info = client.get(prefix + "/result").json()
    assert info["metadata"]["config"] == ref.metadata["config"]
    for a, b in zip(info["diagnostics"], ref.diagnostics, strict=True):
        for k in b.keys() - {"wall_time_s"}:
            assert a[k] == b[k]
    for name in ("East velocity", "Relative vorticity", "Height anomaly"):
        f = client.get(prefix + "/field", params={"name": name, "step": 2}).json()
        np.testing.assert_array_equal(f["values"], s.field(ref, name, 2))
        assert f["x"] == ref.x.tolist() and f["unit"] == s.LABELS[name]
    with ZipFile(io.BytesIO(client.get(prefix + "/export").content)) as z:
        np.testing.assert_array_equal(np.load(io.BytesIO(z.read("h.npy"))), ref.h)


def test_limits_and_cancel(client):
    for p in ({"nx": 4096}, {"snapshot_mib": 256}, {"filename": "elsewhere"}):
        assert (
            client.post("/api/v1/simulations", json={"parameters": p}).status_code
            == 422
        )
    assert client.get("/api/v1/jobs/missing").status_code == 404
    key = client.post("/api/v1/simulations", json={}).json()["id"]
    client.delete("/api/v1/jobs/" + key)
    assert done(client, key)["state"] == "cancelled"
    assert client.get(f"/api/v1/jobs/{key}/export").status_code == 409


def test_timeout_capacity_and_expiry(tmp_path):
    from geoflow.web.jobs import Jobs

    manager = Jobs(tmp_path, capacity=1, timeout=0.02, retention=0.1)
    try:
        key = manager.submit({"kind": "simulation", "config": {}})["id"]
        with pytest.raises(OverflowError):
            manager.submit({"kind": "simulation", "config": {}})
        deadline = time.monotonic() + 10
        while manager.status(key)["state"] != "failed":
            assert time.monotonic() < deadline
            time.sleep(0.005)
        assert manager.status(key)["error"] == "execution timeout"
        with manager.hold(key):
            time.sleep(0.25)
            assert manager.path(key).is_dir()
        while key in manager.items:
            assert time.monotonic() < deadline
            time.sleep(0.05)
    finally:
        manager.close()


def test_scientific_demo_parity(client):
    from geoflow.earth.diagnostics import fields
    from geoflow.earth.tracking import Current, track

    v = "/api/v1"
    assert client.get(v + "/benchmarks").json() == s.benchmarks()
    for kind in ("cnn", "fno"):
        import hashlib

        raw = client.get(v + f"/models/{kind}/export").content
        assert hashlib.sha256(raw).hexdigest() == s.model_row(kind)["view_sha256"]
        with np.load(io.BytesIO(raw)) as a:
            pair = client.get(v + f"/models/{kind}/comparison?step=16").json()
            np.testing.assert_array_equal(pair[1]["values"], a["prediction"][16, 0])
    ds = s.earth_data()
    f = client.get(v + "/earth/field?step=1&name=vorticity").json()
    np.testing.assert_equal(
        np.array(f["values"], float), fields(ds, 1).vorticity.values
    )
    assert f["x"] == ds.lon.values.tolist()
    tr = client.post(v + "/earth/tracks", json={}).json()
    np.testing.assert_equal(
        tr["positions"], track(Current(ds), 70.08, 10.54, 0, 86400).position
    )


def test_demo_and_registered_limits(client, monkeypatch):
    v = "/api/v1"
    assert client.get(v + "/earth?dataset=fixture").json()["validation"] is None
    assert client.get(v + "/earth?dataset=unregistered").status_code == 422
    assert client.post(v + "/earth/tracks", json={"start": 9}).status_code == 422
    assert (
        client.post(
            v + "/simulations", content="x", headers={"content-type": "text/plain"}
        ).status_code
        == 415
    )
    assert (
        client.post(v + "/simulations", json={"padding": "x" * 17000}).status_code
        == 413
    )
    for demo, lat in (("gaussian", 0), ("rotating", 45)):
        info = client.get(v + f"/demos/{demo}/result").json()
        cfg = s.Config(**info["metadata"]["config"])
        assert cfg.latitude_deg == lat
        ref = run_simulation(cfg)
        with ZipFile(io.BytesIO(client.get(v + f"/demos/{demo}/export").content)) as z:
            for k in ("h", "u", "v", "time", "x", "y"):
                np.testing.assert_equal(
                    np.load(io.BytesIO(z.read(k + ".npy"))), getattr(ref, k)
                )
    monkeypatch.setenv("GEOFLOW_READ_ONLY", "1")
    assert client.post(v + "/simulations", json={}).status_code == 403
    assert client.get(v + "/demos/rotating/field").status_code == 200


def test_regional_analysis_archive(client):
    key = client.post(
        "/api/v1/earth/analyses",
        json={"dataset": "fixture", "releases": [[61, 12], [60.9, 12]], "hours": 1},
    ).json()["id"]
    assert done(client, key)["state"] == "completed"
    base = "/api/v1/jobs/" + key
    tracks = client.get(base + "/result").json()["tracks"]
    assert len(tracks) == 2 and all(t["status"] == "completed" for t in tracks)
    with ZipFile(io.BytesIO(client.get(base + "/export").content)) as z:
        assert {"particles.csv", "analysis.json", "region.nc", "diagnostics.nc"} <= set(
            z.namelist()
        )


@pytest.mark.skipif(
    not s.live_available("fno"), reason="optional v0.5 training artifacts"
)
def test_live_inference_matches_archived_fields(client):
    for kind in s.MODELS:
        key = client.post("/api/v1/inference", json={"model": kind}).json()["id"]
        assert done(client, key)["state"] == "completed"
        with (
            np.load(s.DEMO / (kind + ".npz")) as archive,
            ZipFile(io.BytesIO(client.get(f"/api/v1/jobs/{key}/export").content)) as z,
        ):
            np.testing.assert_array_equal(
                np.load(io.BytesIO(z.read("prediction.npy"))), archive["prediction"]
            )
