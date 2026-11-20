# GeoFlow v0.3.1 performance and stability audit

## Results

The Gaussian snapshot update took 32% less time in Chrome and 73% less time in the Streamlit test runner. Reloading the active Arabian Sea region fell from 777 to 36 ms. First use was slower. The first Gaussian Run click took an extra 579 ms in Chrome, and the first switch to Earth took an extra 143 ms in AppTest. The comparison checkpoint is the annotated v0.3.0 tag at `5576cf9cdff993c57b85a2acc82245fc5f14cacc`.

| Wall time, ms | v0.3.0 | v0.3.1 |
|---|---:|---:|
| Fresh process, from Streamlit import to controls ready¹ | 2,503 | 2,404 |
| First Gaussian Run click through plots ready¹ | 661 | 1,064 |
| Change Gaussian snapshot¹ | 555 | 152 |
| First switch to Earth after simulation¹ | 1,018 | 1,161 |
| Load historical region and render first field¹ | 788 | 629 |
| Load unchanged active region again¹ | 777 | 36 |
| Change Earth field¹ | 374 | 166 |
| Gaussian integration only, Rusanov | 42.6 | 35.8 |
| Gaussian integration only, MUSCL | 153.3 | 135.9 |
| Build and encode one idealized heatmap with arrows at 120 dpi | 196 | 119 |
| Compute all fields on the 13 × 25 × 25 fixture at one time | 9.02 | 6.00 |
| NetCDF subset, canonicalization and first cache write | 29 | 32 |
| Standalone import from existing on-disk cache, including source hash | 369 | 370 |
| Draw and encode a 1,024 × 1,024 regional field for display | 811 | 300 |

¹ AppTest measures the Python widget event and completed rerun. Startup starts immediately before importing Streamlit and excludes Python process creation. The initial Run click includes deferred rendering imports. Opening Earth includes Xarray, metadata and widget setup. These costs and backend I/O varied across processes. The disk-cache importer itself is unchanged. A separate Windows profile of a warm cache open spent 0.895 of 0.909 s opening seven NetCDF variables with Xarray's netCDF4 backend. Reading the active session's region avoids that backend call entirely.

| Peak memory, MiB | v0.3.0 | v0.3.1 |
|---|---:|---:|
| Windows process working set during the app and standard solver/figure workload | 234.9 | 192.6 |
| MUSCL integration, traced allocations | 2.785 | 2.537 |
| Fixture diagnostics, traced allocations | 0.338 | 0.150 |
| Idealized heatmap, traced allocations | 9.267 | 7.402 |
| Large regional display, traced allocations | 108.36 | 26.61 |

Process CPU time per snapshot went from 547 to 141 ms, per field switch from 375 to 172 ms, and per repeated region load from 828 to 31 ms. First-click CPU times were 641 and 859 ms. Median Windows process read operations went from 43,830 to 24,180 and logical read transfers from 5,010 to 2,615 MiB. These counters include interpreter, packages, renderer and dataset activity. OS file caching prevents inferring physical disk throughput from them. The working-set counter was sampled before the separate disk-cache and large-map experiments. Tracemalloc measures transient allocations in separate invocations and provides only partial coverage of native memory.

## What changed in the browser

Chrome 157 used a fresh profile and a running local server for each release. Navigation to the Run button took 7.00 s on v0.3.0 and 6.34 s on v0.3.1. From clicking Run to receiving both plot images took 2.05 s and 2.63 s. The median keyboard slider step to a changed, decoded map image fell from **655 ms to 446 ms**. The three steps took 530, 667 and 655 ms on v0.3.0, and 493, 446 and 349 ms on v0.3.1. The harness polls at 20 ms. These measurements cover one session per version, including widget handling, image transfer and decoding. Compositor paint and remote network latency were outside the measurement.

The initial browser check exposed an unreadable watchdog directory on Windows. A package integrity check found other damaged installed files. The project environment was rebuilt with the same 50 pinned package versions. Dependency checks passed and all installed files with wheel checksums matched. The release measurements and both scientific runs used this clean environment and Streamlit's default file watcher. The prior environment was saved in `outputs/perf-repair/original-venv`.

To reproduce, use Node 22+ with a local Chromium binary and run `node benchmarks/browser.mjs <checkout> <python-executable> <chrome-executable> <scratch-directory> <unused-port>` with absolute paths. The tool uses a dedicated browser profile, starts a localhost server and shuts down its processes. Profiles and logs stay in the scratch directory.

## Where the time went

- The initial profile attributed 245 of 273 ms in an idealized render to PNG serialization and its draw/layout work. The application also rebuilt the unchanged conservation figure on each snapshot. Fixed margins on field maps remove the constrained-layout pass. The session retains one encoded PNG per panel. Simulation and Earth visualization run in separate Streamlit fragments. A new simulation or reference receives a fresh identifier, including repeated runs with identical parameters. The simulation button remains the sole interactive solver entry point.
- Earth previously reopened the source to inspect depth and recomputed all diagnostics, means and candidates on routine reruns. Small depth metadata now uses a bounded `st.cache_data` keyed by resolved path and file stat signature. One selected regional dataset, its paired temporal means, the last diagnostic slice and candidate set live in session state. File replacement or a changed bounding box, time range or depth invalidates selection on Load. The disk cache retains its SHA-256 identity check on import. Reusing the active file assumes its filesystem metadata reflects edits.
- The particle form batches edits until submission. Progress indicators cover simulation, regional loading, integration and matching. Export reuses the displayed diagnostic slice, candidates and completed observational match. Particle CSV rows stream from the trajectory. The PNG renderer uses a resource-cached lock around interactive Matplotlib construction and encoding. Scientific arrays are session-local.
- The Rusanov flux combines private working arrays in place. Periodic MUSCL reconstruction avoids making an extra copy of each seam. Zero rotation on an f-plane is the identity. The solver reuses the maximum speed already computed at each output. Vorticity uses the same centered differences and even tangential wall parity directly on the two velocity planes. Exact-time comparisons skip interpolation arithmetic. The CFL limit, invalid-stage retries, gravity, reconstructions, boundary equations and output schedule are unchanged.
- Earth EKE uses the mean of paired valid samples for both components. Plane-wise sums and counts avoid masked time-cube copies. Quiver coordinates are sampled before mesh construction and candidate markers share one collection. For regional grids above 640 cells on an axis, the interactive map samples a representative cell per block, preserves geographic outer edges and takes colour limits from the full field. The UI marks the sampled preview. Features smaller than a block can be missed visually. Exported maps, NetCDF variables, candidate detection, integration and validation retain full resolution.

## Scientific equivalence

The tagged release passed all 68 tests in 25.43 s. The patch passed all 71 in 18.40 s, including three new numerical and preview regressions. The Earth interaction test also checks that changing fields and reloading the active region reuse the actual dataset and derived array objects. The Gaussian solver produced identical SHA-256 digests across versions for concatenated saved `h, u, v` arrays in both schemes. All 18 scientific verification checks passed on both builds, with exactly matching reported metrics.

For the Arabian Sea study, Xarray's identical-dataset comparison passed on both exported NetCDFs, including coordinates, attributes and masks. The matched observations, candidate table, both 24-hour particle trajectories and validation JSON matched byte for byte. Both observed releases completed, giving 48 noninitial hourly pairs per method and gridded RK4 RMS separation of 5.742 km. These checks exercise the historical case and the existing scientific suite. Timings and rendered PNG pixels can change between releases.

## CPU acceleration experiment

A separate disposable install supplied Numba 0.68.1 and llvmlite 0.50.0 for the same Windows CPython and NumPy. The prototype fuses the face flux into a compiled loop with fast-math disabled. It checks every saved field from the full Gaussian simulation against NumPy at relative and absolute tolerances of 1e-12. The timings below include full integration. Cold is the first invocation of that branch. Warm is the median of the next five. These are exploratory single-process measurements on the release source, separate from the paired release benchmark.

| Method | NumPy first / warm, ms | Numba first / warm, ms |
|---|---:|---:|
| Rusanov | 35 / 35 | 1,644 / 22 |
| MUSCL | 127 / 136 | 460 / 121 |

The first compiled baseline-scheme run took 1.64 s. Its warm saving of 13 ms per run was small relative to interactive rendering. Warm MUSCL time fell by 11%. Its reconstruction and two integration stages remain in NumPy. Numba stays out of the runtime dependencies. To repeat the experiment, install Numba in a disposable environment with GeoFlow and run `python benchmarks/jit_flux.py`.

## Reproduction and deployment

On Windows 11, an AMD Ryzen 5 3500X with six logical processors ran 64-bit CPython 3.14.6, NumPy 2.5.5, Matplotlib 3.11.2, Streamlit 1.67.0, Xarray 2026.9.0 and netCDF4 1.7.5.1.post1. Both versions used the same virtual environment, working-directory layout, figures and source data. An archive of the tag supplied baseline source via `PYTHONPATH`. The identical currents file had SHA-256 `4fa25a36bb19f96c31abf2eef9b23417844000b34ef38eaa359ed697a15f7f9c`; selection produced 4 times × 48 latitudes × 72 longitudes. The Gaussian preset used 64 × 64 cells, 7,200 s and 600 s outputs. The synthetic large-map workload used the same input grid for both versions.

The table takes the median across three fresh Python processes per version. Execution order was baseline, patch, patch, baseline, baseline, patch. Within each process the harness took five integrations per scheme and three samples per repeated interaction/render. Startup, first click, mode switch, initial load and initial cache creation occur once per process. Both checkouts started with the canonical disk cache populated for UI interactions. The separate new-cache measurement creates a temporary directory. The OS page cache was allowed to stay warm. Differences of a few milliseconds are sensitive to workstation load.

Install the repository's dev, ui and earth extras, fetch the historical example, and run the following from a checkout. To remeasure the baseline, run the same harness from the v0.3.0 checkout using its `src` directory on `PYTHONPATH`, and copy the same data and canonical cache to both checkouts. Per-process measurements are preserved in [the release benchmark data](../benchmarks/results-v0.3.1.json). JSON files and cProfile files are written under the requested output directory.

```sh
python benchmarks/performance.py outputs/perf-local
python -m pytest -q
geoflow verify --out outputs/verify-local
python -m geoflow.earth.cli analyze --file data/arabian-july-2020/currents.nc --drifters data/arabian-july-2020/drifters.csv --release 65 12 --release 65.1 12 --end-index 1 --out outputs/earth-local
```

The app resolves bundled presets, default Earth inputs, canonical cache and export paths relative to its checkout. CLI paths remain relative to the caller. The core installation requires NumPy and Matplotlib. Earth and Streamlit remain optional extras. A deployment needs a writable cache/output volume and a source checkout for the app and configs. The existing Ubuntu/Python 3.11 CI workflow installs all extras and runs tests and lint. This audit exercised Windows locally. Hosted CI, remote browser latency and concurrent-user capacity remain unmeasured. The current server-side arbitrary file paths suit trusted local use. A public deployment would need scoped dataset access, job quotas and output isolation. A user retaining two simulation trajectories plus an Earth region consumes session-specific memory in addition to the worker's baseline.

A Next.js frontend with a FastAPI service could help if GeoFlow needs browser-side map interaction, shared immutable dataset tiles, or asynchronous jobs shared across clients. A migration would also introduce a second application, array transport and a job lifecycle. The measurements identify plot encoding and duplicate Python work as major costs that a new frontend alone would retain. Keep Streamlit for this release. Browser interaction and concurrent-job measurements under the intended deployment load should guide a future migration decision.
