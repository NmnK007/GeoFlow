"""GeoFlow v1 HTTP contract. Run one ASGI process per local job supervisor."""

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, create_model

from . import service as s
from .jobs import Jobs
from .public import PublicAdmission, public_mode
from .research import evidence


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


_SERVER_FIELDS = {
    "experiment",
    "max_steps",
    "max_frames",
    "snapshot_mib",
    "working_mib",
    "max_retries",
}
Overrides = create_model(
    "SolverParameters",
    __base__=Strict,
    **{
        name: (item.type, item.default)
        for name, item in s.Config.__dataclass_fields__.items()
        if name not in _SERVER_FIELDS
    },
)


class Simulation(Strict):
    preset: str = "gaussian_bump"
    parameters: Overrides = Field(default_factory=Overrides)


class Inference(Strict):
    model: Literal["cnn", "fno"]
    group: Literal["id", "amplitude", "position", "rotation"] = "id"
    member: int = Field(0, ge=0, le=2)


class Release(Strict):
    dataset: str = "arabian"
    longitude: float = Field(70.08, ge=-180, le=180)
    latitude: float = Field(10.54, ge=-89, le=89)
    start: int = Field(0, ge=0, le=1023)
    hours: float = Field(24, ge=-72, le=72)
    dt_s: float = Field(900, ge=300, le=3600)
    method: Literal["rk4", "euler"] = "rk4"


class Status(BaseModel):
    id: str
    kind: Literal["simulation", "inference", "earth"]
    state: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float
    error: str | None


class Grid(BaseModel):
    name: str
    unit: str
    axes: list[str]
    x: list[float]
    y: list[float]
    values: list[list[float | None]]
    vectors: list[list[float]] | None = None


@asynccontextmanager
async def lifespan(app):
    if os.getenv("GEOFLOW_READ_ONLY", "0") not in {"0", "1"}:
        raise ValueError("GEOFLOW_READ_ONLY requires 0 or 1")
    limits = {
        key: int(os.environ["GEOFLOW_" + key.upper()])
        for key in ("workers", "capacity", "timeout", "retention", "records")
        if "GEOFLOW_" + key.upper() in os.environ
    }
    app.state.jobs = (
        None
        if public_mode()
        else Jobs(os.getenv("GEOFLOW_ARTIFACTS", s.ROOT / "outputs/web-jobs"), **limits)
    )
    yield
    if app.state.jobs is not None:
        app.state.jobs.close()


app = FastAPI(title="GeoFlow Scientific API", version="1.0", lifespan=lifespan)


@app.middleware("http")
async def admission(request: Request, call_next):
    from fastapi.responses import JSONResponse

    if request.method == "POST":
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "expected a JSON request"}, 415)
        # Require bounded, known-size bodies before parsing; no uploads.
        length = request.headers.get("content-length", "")
        if not length.isdecimal() or len(length) > 5 or int(length) > 16384:
            return JSONResponse(
                {"detail": "request exceeds 16 KiB or lacks length"}, 413
            )
    return await call_next(request)


app.add_middleware(PublicAdmission)

V = "/api/v1"
Demo = Literal["gaussian", "rotating"]
Model = Literal["cnn", "fno"]


@app.exception_handler(ValueError)
async def invalid(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {"detail": "invalid demo parameters" if public_mode() else str(exc)},
        status_code=422,
    )


@app.exception_handler(KeyError)
async def missing(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": "unknown job"}, status_code=404)


@app.get(V + "/health")
def health():
    return {"status": "ok"}


@app.get(V + "/mode")
def mode():
    return {"read_only": public_mode()}


@app.get(V + "/research")
def research():
    return evidence()


@app.get(V + "/experiments")
def experiments():
    return {key: asdict(s.load_config(path)) for key, path in sorted(s.PRESETS.items())}


def submit(req, body):
    try:
        return req.app.state.jobs.submit(body)
    except OverflowError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "5"}) from exc


@app.post(V + "/simulations", status_code=202, response_model=Status)
def simulate(body: Simulation, request: Request):
    c = s.configuration(body.preset, body.parameters.model_dump(exclude_unset=True))
    return submit(request, {"kind": "simulation", "config": asdict(c)})


@app.post(V + "/inference", status_code=202, response_model=Status)
def infer(body: Inference, request: Request):
    if not s.live_available(body.model):
        raise HTTPException(
            409, "Install the local v0.5 study to enable fresh inference"
        )
    return submit(request, {"kind": "inference", **body.model_dump()})


@app.get(V + "/jobs/{key}", response_model=Status)
def status(key: str, request: Request):
    return request.app.state.jobs.status(key)


@app.delete(V + "/jobs/{key}", response_model=Status)
def cancel(key: str, request: Request):
    return request.app.state.jobs.cancel(key)


def hold_result(key: str, request: Request):
    with request.app.state.jobs.hold(key):
        yield


def result_dir(request, key, kind=None):
    jobs = request.app.state.jobs
    status = jobs.status(key)
    if status["state"] != "completed" or (kind and status["kind"] != kind):
        raise HTTPException(409, "result unavailable for this job")
    return jobs.path(key)


@app.get(V + "/jobs/{key}/result", dependencies=[Depends(hold_result)])
def result(key: str, request: Request):
    return s.read(result_dir(request, key) / "result.json")


@app.get(
    V + "/jobs/{key}/field", dependencies=[Depends(hold_result)], response_model=Grid
)
def field(
    key: str,
    request: Request,
    step: int = 0,
    name: str = "Height anomaly",
    at_s: float | None = None,
    vectors: bool = False,
):
    return s.frame(result_dir(request, key, "simulation"), step, name, at_s, vectors)


@app.get(
    V + "/jobs/{key}/comparison",
    dependencies=[Depends(hold_result)],
    response_model=list[Grid],
)
def prediction(
    key: str, request: Request, step: int = 0, channel: int = Query(0, ge=0, le=2)
):
    return s.comparison(step, channel, out=result_dir(request, key, "inference"))


@app.get(V + "/jobs/{key}/export", dependencies=[Depends(hold_result)])
def export(key: str, request: Request):
    return FileResponse(
        result_dir(request, key) / "export.zip", filename=f"geoflow-{key}.zip"
    )


@app.get(V + "/demos/{demo}/result")
def demo_info(demo: Demo):
    return s.read(s.DEMO / demo / "result.json")


@app.get(V + "/demos/{demo}/field", response_model=Grid)
def demo_field(
    demo: Demo,
    step: int = 0,
    name: str = "Height anomaly",
    at_s: float | None = None,
    vectors: bool = False,
):
    return s.frame(s.DEMO / demo, step, name, at_s, vectors)


@app.get(V + "/demos/{demo}/export")
def demo_export(demo: Demo):
    return FileResponse(s.DEMO / demo / "export.zip", filename=f"{demo}.zip")


@app.get(V + "/earth")
def earth(dataset: str = "arabian"):
    if public_mode() and dataset not in {"arabian", "fixture"}:
        raise ValueError("unknown Earth dataset")
    return s.earth_catalog(dataset)


@app.get(V + "/earth/field", response_model=Grid)
def ocean_field(step: int = 0, name: str = "speed", dataset: str = "arabian"):
    if public_mode() and dataset not in {"arabian", "fixture"}:
        raise ValueError("unknown Earth dataset")
    return s.earth_frame(step, name, dataset)


@app.get(V + "/earth/eddies")
def eddies(
    step: int = 0,
    ow: float = Query(0, le=0, ge=-1),
    sla: float = Query(0.02, ge=0, le=10),
    cells: int = Query(4, ge=1, le=1000),
    dataset: str = "arabian",
):
    from geoflow.earth.eddies import candidates

    if public_mode() and dataset not in {"arabian", "fixture"}:
        raise ValueError("unknown Earth dataset")
    d = s.earth_fields(step, dataset)
    return candidates(d, ow, sla, cells) if "sla" in d else []


@app.post(V + "/earth/tracks")
def tracks(body: Release):
    from geoflow.earth.tracking import Current, track

    current = Current(s.earth_data(body.dataset))
    if body.start >= len(current.axes[0]):
        raise ValueError("unknown release time")
    start = current.axes[0][body.start]
    t = track(
        current,
        body.longitude,
        body.latitude,
        start,
        start + body.hours * 3600,
        body.dt_s,
        body.method,
    )
    return {
        "time_s": t.time.tolist(),
        "positions": t.position.tolist(),
        "status": t.status,
    }


class EarthAnalysis(Release):
    releases: list[tuple[float, float]] = Field(default_factory=list, max_length=16)
    ow: float = Field(0, ge=-1, le=0)
    sla: float = Field(0.02, ge=0, le=10)
    cells: int = Field(4, ge=1, le=1000)


@app.post(V + "/earth/analyses", response_model=Status, status_code=202)
def ocean_analysis(body: EarthAnalysis, request: Request):
    ds = s.earth_data(body.dataset)
    if body.start >= len(ds.time) or any(
        abs(x) > 180 or abs(y) > 89 for x, y in body.releases
    ):
        raise ValueError("invalid release coordinates or start time")
    return submit(request, {"kind": "earth", **body.model_dump()})


@app.get(V + "/earth/export")
def ocean_export():
    return FileResponse(s.DEMO / "region.nc", filename="arabian-sea.nc")


@app.get(V + "/models")
def models():
    return {
        k: {"run": s.model_row(k), "live": not public_mode() and s.live_available(k)}
        for k in s.MODELS
    }


@app.get(V + "/models/{kind}/comparison", response_model=list[Grid])
def compare(kind: Model, step: int = 0, channel: int = Query(0, ge=0, le=2)):
    return s.comparison(step, channel, kind=kind)


@app.get(V + "/models/{kind}/result")
def model_result(kind: Model):
    return s.read(s.DEMO / "models.json")[kind]


@app.get(V + "/benchmarks/{run}/comparison", response_model=list[Grid])
def benchmark_comparison(
    run: str, step: int = Query(24, ge=0, le=24), channel: int = Query(0, ge=0, le=2)
):
    import hashlib

    row = next((r for r in s.benchmarks()["runs"] if r["run"] == run), None)
    if not row:
        raise HTTPException(404, "unknown benchmark")
    path = s.STUDY / "views" / (row["run"] + ".npz")
    if public_mode() or not path.is_file():
        if run in [s.model_row(k)["run"] for k in s.MODELS]:
            return s.comparison(step, channel, kind=row["method"])
        raise HTTPException(
            404, "Generate the v0.5 study locally to view this trajectory"
        )
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != row.get("view_sha256"):
            raise HTTPException(409, "trajectory fingerprint mismatch")
    return s.comparison(step, channel, archive_path=path)


@app.get(V + "/models/{kind}/export")
def model_export(kind: Model):
    return FileResponse(s.DEMO / (kind + ".npz"), filename=f"{kind}.npz")


@app.get(V + "/benchmarks")
def hpc():
    return FileResponse(
        s.ROOT / "benchmarks/hpc-results.json", media_type="application/json"
    )
