# GeoFlow v0.5 — Scaling & HPC

Select **HPC** in the local laboratory to explore the measured 16², 32² and 64² runs, compare prediction errors and export results. See the [scaling study and reproduction commands](docs/hpc.md).

The optional Neural Laboratory compares persistence, a periodic CNN and a Fourier Neural Operator against solver-generated MUSCL–MC trajectories. See the [held-out results, methods and reproduction commands](docs/neural.md).

The performance update speeds up snapshot changes and repeated Earth analysis. See the [measured performance and scientific verification report](docs/performance.md).

GeoFlow integrates nonlinear rotating shallow water on a rectangular, flat-bottom domain. The CLI and local laboratory use the same NumPy solver. Eleven JSON presets specify initial-value problems in SI units. Existing configs default to the v0.1 method. Select MUSCL and a limiter for higher-order runs. See [Dynamics and measured verification](docs/dynamics.md).

## Earth laboratory

Select **Earth** in the Streamlit sidebar to inspect imported ocean currents, release passive particles and compare their trajectories with NOAA drifters. Earth uses external fields. The **Idealized simulation** mode retains both shallow-water solvers.

Install the optional packages with `python -m pip install -e ".[dev,ui,earth]"`. For the historical Arabian Sea study, run the following from this checkout with the environment active.

```sh
python -m geoflow.earth.cli fetch
python -m geoflow.earth.cli analyze --file data/arabian-july-2020/currents.nc --drifters data/arabian-july-2020/drifters.csv --out outputs/my-earth-study
python -m streamlit run app.py
```

The default Earth input paths match those downloads. **Load region**, then **Compare observed tracks** inside the drifter panel. For offline exploration choose **Synthetic verification fixture**. See [Earth methods, acquisition, results and exercises](docs/earth.md).

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

## Compare two runs

In the laboratory, run the Gaussian bump and select **Pin current run as A**. Choose MUSCL with MC, leave the physical parameters and grid fixed, and run again. Inspect the two height maps at the same time and select the energy diagnostic. **Save comparison artifacts** writes both complete runs, a synchronized CSV and metadata under outputs. You can also change preset, resolution, latitude or duration between runs.

## Read and extend

1. Read [the numerical notes](docs/numerics.md). Trace one interface through `physics.py`, `boundaries.py` and `solver.py`.
2. Reproduce [the experiments](docs/experiments.md). Inspect the independent wave and inertial references in `verification.py`.
3. See [model limits](docs/limitations.md) before interpreting results. The original research brief contains the scientific references. Development checkpoints and release evidence are in [PROGRESS.md](PROGRESS.md).

The Python entry point is `geoflow.solver.run_simulation(Config(...))`, where `Config` is imported from `geoflow.config`. It returns independent sampled fields indexed by time, northing and easting, diagnostic rows and normalized metadata. Choose a code license before publishing.
