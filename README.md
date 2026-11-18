# GeoFlow v0.1

GeoFlow integrates nonlinear rotating shallow water on a rectangular, flat-bottom domain. The CLI and local laboratory use the same NumPy solver. Five JSON presets specify reproducible initial-value problems in SI units.

## Run locally

From this directory with Python 3.11 or newer, create an environment with `python -m venv .venv`. Activate it with `.\.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on macOS/Linux. On Windows you can substitute `.\.venv\Scripts\python.exe` for every `python` below and skip activation.

```sh
python -m pip install -e ".[dev,ui]"
python -m pytest -q
python -m ruff check .
python -m geoflow.cli run --config configs/gaussian_bump.json --out outputs/demo
python -m geoflow.cli verify --out outputs/verification
python -m streamlit run app.py
```

Use `-e ".[dev]"` for CLI development or `-e .` for simulations alone. Choose a fresh output directory for each run. Explicit `--overwrite` permits replacing named artifacts. Check metadata status before reading any fields from a reused directory. A simultaneous writer is refused. After a hard interruption use a fresh output directory.

## Read and extend

1. Read [the numerical notes](docs/numerics.md). Trace one interface through `physics.py`, `boundaries.py` and `solver.py`.
2. Reproduce [the experiments](docs/experiments.md). Inspect the independent wave and inertial references in `verification.py`.
3. See [model limits](docs/limitations.md) before interpreting results. The original research brief contains the scientific references. Development checkpoints and release evidence are in [PROGRESS.md](PROGRESS.md).

The Python entry point is `geoflow.solver.run_simulation(Config(...))`, where `Config` is imported from `geoflow.config`. It returns independent sampled fields indexed by time, northing and easting, diagnostic rows and normalized metadata. Choose a code license before publishing.
