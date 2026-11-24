"""Public demo boundaries, archival projections, and supervisor recovery."""

import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from geoflow.web import service
from geoflow.web.api import app
from geoflow.web.jobs import Jobs
from geoflow.web.public import PublicAdmission


def test_public_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("GEOFLOW_READ_ONLY", "1")
    monkeypatch.setenv("GEOFLOW_ARTIFACTS", str(tmp_path))
    with TestClient(app) as c:
        assert app.state.jobs is None
        assert c.get("/api/v1/mode").json() == {"read_only": True}
        for path in ("simulations", "earth/tracks", "earth/analyses", "inference"):
            assert c.post("/api/v1/" + path, json={}).status_code == 403
        for path in ("jobs/demo", "jobs/demo/export", "jobs/demo/result"):
            assert c.get("/api/v1/" + path).status_code == 404
        assert c.get("/api/v1/earth").json()["sources"] == ["arabian", "fixture"]
        for path in ("earth", "earth/field", "earth/eddies"):
            assert (
                c.get("/api/v1/" + path, params={"dataset": "operator"}).status_code
                == 422
            )
        assert all(not v["live"] for v in c.get("/api/v1/models").json().values())
        assert c.get("/api/v1/benchmarks/64-muscl-cpu-1/comparison").status_code == 404
        assert c.get("/api/v1/demos/rotating/export").status_code == 200
    assert not list(tmp_path.iterdir())


def test_read_budget(monkeypatch):
    import asyncio

    monkeypatch.setenv("GEOFLOW_READ_ONLY", "1")

    async def scenario():
        entered = asyncio.Event()
        finish = asyncio.Event()

        async def app(scope, receive, send):
            entered.set()
            await finish.wait()

        gate = PublicAdmission(app)
        scope = {"type": "http", "method": "GET", "path": "/api/v1/research"}
        messages = []

        async def send(message):
            messages.append(message)

        requests = [asyncio.create_task(gate(scope, None, send)) for _ in range(8)]
        await entered.wait()
        await gate(scope, None, send)
        assert messages[0]["status"] == 429
        finish.set()
        await asyncio.gather(*requests)
        assert gate.active == 0
        gate.tokens = 0
        messages.clear()
        await gate(scope, None, send)
        assert messages[0]["status"] == 429

    asyncio.run(scenario())


def test_archive_projections():
    with TestClient(app) as c:
        tables = c.get("/api/v1/research").json()
    checks = service.read(service.DEMO / "verification.json")["checks"]
    assert len(checks) == 18 and all(c["passed"] for c in checks.values())
    for scheme, nx, l1, order in tables[0]["rows"]:
        row = next(r for r in checks["refinement"][scheme] if r["nx"] == nx)
        assert [l1, order] == [row["relative_l1"], row["order"]]
    for scheme, loss in tables[1]["rows"]:
        assert loss == checks["gaussian_diffusion"][scheme]
    for wave, speed, theory, amplitude in tables[2]["rows"]:
        record = checks[wave]
        assert [speed, theory, amplitude] == [
            record[k] for k in ("measured_m_s", "theory_m_s", "amplitude_ratio")
        ]
    methods = service.read(service.DEMO / "validation.json")["methods"]
    for k, count, mean, rms, end in tables[3]["rows"]:
        row = methods[k]
        assert [count, mean, rms, end] == [
            row["count"],
            row["mean_m"],
            row["rms_m"],
            row["by_horizon"]["24"]["mean_m"],
        ]
    runs = {r["run"]: r for r in service.benchmarks()["runs"]}
    assert len(tables[4]["rows"]) == 7 and len(tables[5]["rows"]) == 12
    for key, *errors, warm in tables[4]["rows"]:
        r = runs[key]
        assert warm == r["median_ms"]
        assert errors == [
            r["groups"]["id"]["horizons"][str(i)]["relative_l2"] for i in (1, 4, 16, 24)
        ]
    for key, grid, device, warm in tables[5]["rows"]:
        assert [grid, device, warm] == [
            runs[key][k] for k in ("grid", "device", "median_ms")
        ]


def test_worker_failure_and_restart(tmp_path):
    first = Jobs(tmp_path)
    try:
        key = first.submit({"kind": "simulation", "config": {"unknown": True}})["id"]
        deadline = time.monotonic() + 20
        while first.status(key)["state"] in {"queued", "running"}:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        assert first.status(key)["error"] == "scientific worker failed"
    finally:
        first.close()
    second = Jobs(tmp_path)
    try:
        with pytest.raises(KeyError):
            second.status(key)
    finally:
        second.close()
    assert not list(tmp_path.iterdir())
