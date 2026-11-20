"""Run from the checkout root with the Earth and UI extras installed."""

import cProfile
import gc
import hashlib
import io
import json
import sys
import time
import tracemalloc
from pathlib import Path
from statistics import median

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
results = {}
cpu_ms = {}


def windows_counters():
    import ctypes
    from ctypes import wintypes

    class Memory(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (n, ctypes.c_size_t)
            for n in ("peak", "working", "a", "b", "c", "d", "e", "f")
        ]

    handle = wintypes.HANDLE(-1)
    memory = Memory()
    memory.cb = ctypes.sizeof(memory)
    io_counts = (ctypes.c_ulonglong * 6)()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        handle, ctypes.byref(memory), memory.cb
    ) or not ctypes.windll.kernel32.GetProcessIoCounters(
        handle, ctypes.byref(io_counts)
    ):
        raise ctypes.WinError()
    return {
        "peak_working_set_mib": memory.peak / 2**20,
        "read_ops": io_counts[0],
        "read_transfer_mib": io_counts[3] / 2**20,
    }


def measure(name, fn, n=3):
    times = []
    cpu = []
    for _ in range(n):
        cpu_start = time.process_time()
        start = time.perf_counter()
        value = fn()
        times.append(1000 * (time.perf_counter() - start))
        cpu.append(1000 * (time.process_time() - cpu_start))
    cpu_ms[name] = median(cpu)
    results[name] = median(times)
    return value


start = time.perf_counter()
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(Path("app.py").resolve(), default_timeout=60).run()
results["startup_ms"] = 1000 * (time.perf_counter() - start)


def ui(name, fn, n=1):
    measure(name, fn, n)
    assert not app.exception and not app.error, (app.exception, app.error)


ui("run_widget_ms", lambda: app.button(key="run_lab").click().run())
frames = iter([2, 4, 6])
ui("snapshot_ms", lambda: app.slider[0].set_value(next(frames)).run(), 3)
ui("earth_open_ms", lambda: app.radio(key="lab_mode").set_value("Earth").run())


def load():
    next(b for b in app.button if b.label == "Load region").click().run()


ui("load_ms", load)
ui("repeat_load_ms", load, 3)
names = iter(["ke", "eke", "speed"])
ui(
    "earth_field_ms",
    lambda: (
        next(w for w in app.selectbox if w.label == "Ocean field")
        .select(next(names))
        .run()
    ),
    3,
)
from dataclasses import replace

from geoflow import __version__
from geoflow.config import load_config
from geoflow.earth.diagnostics import fields
from geoflow.earth.fixture import fixture
from geoflow.plotting import heatmap
from geoflow.solver import run_simulation

results["geoflow_version"] = __version__
c = load_config(Path("configs/gaussian_bump.json"))
for scheme in ("rusanov", "muscl"):
    cfg = replace(c, scheme=scheme)
    r = measure(scheme + "_ms", lambda cfg=cfg: run_simulation(cfg), 5)
    results[scheme + "_sha256"] = hashlib.sha256(
        b"".join(a.tobytes() for a in (r.h, r.u, r.v))
    ).hexdigest()


def render():
    heatmap(r, "Height anomaly", 2, True).savefig(io.BytesIO(), format="png", dpi=120)


measure("render_ms", render)
prof = cProfile.Profile()
prof.runcall(render)
prof.dump_stats(str(out / "render.prof"))
prof.runcall(run_simulation, c)
prof.dump_stats(str(out / "combined.prof"))
ds = fixture()
measure("fields_ms", lambda: fields(ds, 1))
for name, fn in (
    ("muscl", lambda: run_simulation(cfg)),
    ("fields", lambda: fields(ds, 1)),
    ("render", render),
):
    gc.collect()
    tracemalloc.start()
    fn()
    results[name + "_peak_mib"] = tracemalloc.get_traced_memory()[1] / 2**20
    tracemalloc.stop()
results["cpu_ms"] = cpu_ms
if sys.platform == "win32":
    results.update(windows_counters())
# Isolate NetCDF import from the Streamlit load-and-render interaction.
import inspect
from tempfile import TemporaryDirectory

import numpy as np
import xarray as xr

from geoflow.earth.data import import_region
from geoflow.earth.plots import regional_map

source = Path("data/arabian-july-2020/currents.nc")
with TemporaryDirectory() as cache:

    def read_region():
        return import_region(
            source, [55, 73, 8, 20], "2020-07-01", "2020-07-04", cache=cache
        )

    region = measure("import_empty_cache_ms", read_region, 1)
    measure("import_disk_cache_ms", read_region)
results["region_sizes"] = dict(region.sizes)
results["input_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()

axis = np.linspace(10, 20, 1024)
wave = np.sin(axis[:, None] + axis)
large = xr.Dataset(
    {
        "u": (("time", "lat", "lon"), wave[None]),
        "v": (("time", "lat", "lon"), wave[None]),
    },
    coords={"time": [np.datetime64("2020-07-01")], "lat": axis, "lon": axis},
)
field = large.isel(time=0)
field.u.attrs["units"] = "m/s"
preview = (
    {"display_limit": 640}
    if "display_limit" in inspect.signature(regional_map).parameters
    else {}
)


def large_plot():
    regional_map(large, field, "u", 0, **preview).savefig(
        io.BytesIO(), format="png", dpi=120
    )


measure("large_map_ms", large_plot)
gc.collect()
tracemalloc.start()
large_plot()
results["large_map_peak_mib"] = tracemalloc.get_traced_memory()[1] / 2**20
tracemalloc.stop()
print(json.dumps(results, indent=2))
(out / "metrics.json").write_text(json.dumps(results, indent=2))
