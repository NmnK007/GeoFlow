# GeoFlow v0.3.1 — final release checkpoint

M7 complete. The clean comparison against annotated tag `v0.3.0` (`5576cf9`) is recorded in [the performance report](docs/performance.md) and [the raw measurements](benchmarks/results-v0.3.1.json). These final measurements supersede the provisional numbers in the milestone history.

- The Streamlit fragments, per-session plot and dataset reuse, diagnostic and flux changes, and labelled large-grid preview are complete. Scientific exports retain full resolution.
- Clean Windows runs passed all 68 baseline tests and 71 patch tests. Both builds passed all 18 scientific checks with identical reported metrics. Gaussian field hashes and historical Earth results matched.
- Chrome snapshot latency fell from 655 to 446 ms. Repeated region loading fell from 777 to 36 ms in AppTest. Peak process working set fell from 234.9 to 192.6 MiB. The first Run click in Chrome rose from 2.05 to 2.63 s. Remote latency, hosted CI and multi-user capacity were outside the measurement.
- The project venv was rebuilt at the same dependency versions after damaged installed files were detected. The final wheel integrity audit reported zero differences. Numba was benchmarked separately. Streamlit and NumPy remain the release implementations.
- Pending v0.3.1 work is complete. To reproduce, follow the commands in the performance report using a fresh output directory. Local profiles, both scientific reports and historical exports are in `outputs/perf-clean`. Development stopped at v0.3.1.

# GeoFlow v0.3 Earth — release checkpoint

M9 complete. Resumed after the Earth interface gate and finalized the existing implementation, documentation and evidence. GeoFlow 0.3.0 is installed in the project virtual environment. The requested v0.2 baseline is preserved at local tag v0.2.0 (9e26a5e). v0.3 files are saved in the working tree.

- Final Windows regression: 68 tests passed in 37.93 s, including the existing 56 tests and 12 new Earth tests. Ruff and git diff whitespace checks passed. All 18 idealized scientific checks passed.
- Historical validation: outputs/earth-v03 contains region.nc, diagnostics.nc, matched.csv, validation.json, candidates.csv, particles.csv, the regional map, horizon plot and analysis settings. RMS values were independently recomputed from all 48 noninitial pairs per method in the exported CSV. Two additional ensemble particles completed 24 h. docs/earth.md records sources, licensing, physics, sensitivity and limitations.
- Source scope: real observations and historical satellite-derived currents were retrieved and exercised. Authenticated Copernicus Toolbox acquisition, a live GLORYS download, hosted CI and browser-based visual testing remain unverified. Streamlit interaction tests ran locally. GLORYS-style local level selection and velocity units were tested with CF fixtures.
- Known limits: a two-drifter case, mixed drogue status, surface geostrophic forcing, no subgrid coastline, and threshold-sensitive eddy candidates.
- Next reproduction step: follow README.md to run the Earth comparison in a fresh output directory. No v0.3 implementation tasks remain. A future release requires explicit approval.

# GeoFlow v0.2 — release checkpoint

All seven v0.2 milestones are complete. Local annotated tag `v0.1.0` points to fa61624. The v0.2 implementation is saved in the working tree. No remote changes were made.

M7 final gate: GeoFlow 0.2.0 installed in the project venv; 56 tests passed in 18.69 s with both UI interaction tests; Ruff and diff whitespace checks passed. The installed CLI passed all 18 scientific checks and exported a 60-step Kelvin run. Evidence: outputs/release-v02/verification.json, scheme_convergence.csv and outputs/kelvin-v02/. docs/dynamics.md records equations, measurements, experimental limitations and exercises. Browser visual inspection and hosted CI were not run.

Pending development tasks: none for v0.2. Next reproduction step: run the installed verify command in a fresh directory or launch app.py and compare the two Gaussian methods. Numerical limitations include Rossby amplitude damping, unresolved shear growth-rate and vortex-merger benchmarks, and loss of balance over long integrations. Further development requires a new release decision.

# v0.1 archived checkpoint

## Release status
GeoFlow 0.1.0 is complete. All four stages are saved locally. No v0.1 implementation tasks remain. The release boundary is closed pending explicit approval of any subsequent version.

- Completed the CPU solver, five presets, CLI, portable exports, scientific tests, verification command, UI, numerical notes, installation guide and CI workflow.
- Final local gate on Windows with Python 3.14.6: editable installation with dev and ui extras succeeded, 37 tests passed in 8.24 s, Ruff passed. The optional Streamlit AppTest exercised running, field/time/arrows, stale settings, rerunning and reset. The sandbox blocked Windows asyncio loopback sockets, so the final UI-inclusive suite ran with approved local socket access. A browser visual inspection and remote CI execution were not performed.
- CLI evidence: outputs/verification/verification.json (12 passing cases), convergence.csv and convergence.png; outputs/demo contains the computed fields, diagnostics, metadata and final plot. Gaussian demonstration: 13 snapshots through 7200 s, 84 steps, no rejections, zero measured volume drift, final minimum depth 99.80997 m, energy change −30.64196%.
- Known limitations: diffusive first-order transport, approximate rotational adjustment, strictly positive depths, and idealized physics. No unresolved failing tests. The working-memory budget is an estimate. See docs/limitations.md.
- Next step for reproduction: use a fresh output directory with the verify command in README.md. First manual exercise: rederive the 3×2 mass update in docs/numerics.md, then compare the same Gaussian at 0° and 45°. No later-release work is scheduled.

## Milestone history

Both briefs read. The starting directory contains only the two briefs. Milestones are saved as working files.
1. Implement physical flux, state conversion and exact rotation. Run unit tests.
2. Integrate grid, boundary states, stepping, diagnostics and analytic verification. Test before interface work.
3. Exercise presets, CLI and exported evidence. Write numerical notes and CI.
4. Exercise the local Streamlit interface and rerun release checks. Stop at v0.1.
Current stage: core implementation. Decisions: float64, cell-centred SI fields, shared Rusanov flux and first-order Lie splitting. No tests run yet.

M1 complete: package scaffold, conserved state, physical/Rusanov fluxes and exact source rotation saved. Core pytest gate: 3 passed. Next: independent boundaries, validated configuration, solver and analytic gates. Editable install requested after sandbox DNS failure.

M2 complete: validated configuration, grid, boundaries, adaptive solver, bounded retries, diagnostics and verification. Editable install with dev and ui succeeded. 28 tests passed. Analytical stencil test uses absolute roundoff tolerance for exact zeros. Wave L2 errors 0.098019, 0.047966, 0.023607; orders 1.031 and 1.023. Both inertial errors 8.57e-15. Worst bump volume drift 4.27e-16. No outstanding solver test failures. Next: CLI, export roundtrips, preset runs, numerical notes, CI, then local UI.

M3 integration: five JSON presets, CLI, bounded output, plots, exports, CI and roundtrip tests saved. All 36 tests passed. Both requested CLI commands succeeded. Gaussian demo used 84 accepted steps, zero retries, final relative energy change -0.30642. Lint fixes applied. Next: mathematical documentation, Streamlit controls and interaction testing, final suite.

## v0.2 Dynamics
M1 complete. Initial tree clean on main at fa61624. Local annotated tag v0.1.0 preserves baseline. Full suite 37 passed; verification regenerated in outputs/baseline-v01. Next: MUSCL, SSP-RK2 and split rotation, then convergence and matched Gaussian comparison.
M2 complete. Piecewise-linear conserved states, MC/minmod, reflected face traces, two guarded Euler stages and Strang rotation. Four limiter/boundary tests passed. Next: matched diffusion and refinement investigations.

M3 complete: matched Gaussian losses 30.642%, 5.174%, 0.881% (baseline/minmod/MC); L1 orders 1.014, 1.899, 1.980. Next: beta plane, reduced gravity, scales and PV.
M4 complete. Beta channel, reduced gravity and consistent rotational/PV/energy diagnostics implemented. Reduced-gravity beta-channel smoke run succeeded. Next: six analytic/idealized presets and quantitative physical gates.
M5 complete. Six presets saved. Physical gates passed: Rossby -0.9080 m/s vs -0.9148 with 18.3% amplitude loss; Kelvin 3.1402 vs 3.1623; Poincare 35.4114 vs 35.3608. Ten-period balanced jet PV anomaly error 2.44%, mass drift 1.09e-15. Next: synchronized comparison, export, UI tests, release documentation.
M6 complete: pin A, run B, synchronized overlapping times, shared field scale, diagnostic comparisons and independent trajectory/CSV export. Full suite including comparison AppTest passed (56 tests). Next: release documentation, packaging, final checks.

## v0.3 Earth
M1. Baseline 56 tests and 18 verification checks passed. Reviewed local v0.2 changes; committed and tagged v0.2.0 at 9e26a5e. Next: regional CF import, cache and spherical coordinates.
M2 complete. Regional CF ingestion, antimeridian coordinates, provenance and SHA-256 keyed cache verified by NetCDF roundtrip and distance tests.
M3 complete. Spherical velocity-gradient tensor, KE/EKE, vorticity, strain, OW and geostrophic diagnostics implemented. Synthetic vortex center gives positive rotation and negative OW. Next: conservative interpolation footprints and passive tracking.
M4 complete. Forward/backward Euler and RK4, multiple releases, strict trilinear footprints and cell-crossing checks implemented. Next: analytic convergence, masking and diagnostics tests.
M5 complete. Six offline Earth tests passed. Rotating analytic field final refinement Euler order 1.0083 and RK4 order 3.99998; uniform/backward/time-dependent and land crossing verified. Next: eddy sensitivity and observed drifter comparison.
M6 complete. Four-connected hemisphere-aware OW/vorticity/SLA candidates. Fixture radius 40.38, 31.45, 23.69 km for OW thresholds 0, -1e-10, -2e-10. Eddy/metric tests passed. Next: Arabian Sea validation at first eligible hourly release per drifter.
M7 complete. Three-day historical NOAA mirror DUACS + GDP retrieval succeeded. All two eligible drifters tracked 24 h, 48 scored hourly horizons, no terminations. RK4 mean/RMS/final separation 5.108/5.742/8.110 km. Stationary 5.778/7.024/10.233 km; constant observed velocity 5.403/6.590/10.344 km. One drogue lost before release. Outputs in outputs/earth-arabian. Next: separate Earth UI, offline CI, documentation.
M8 complete. Separate Earth laboratory supports local/synthetic import, selected level and time, geographic fields, releases/ensembles, eddy candidates, GDP comparison and exports. Earth AppTest loaded fixture, integrated and returned to simulation. All 67 tests passed at gate. Next: finalize provenance, case documentation and release checks.

## v0.3.1 performance audit
M1: clean v0.3.0 annotated checkpoint 5576cf9, baseline profiles and timings saved to outputs/perf030. Snapshot 548 ms, Earth field 333 ms, Gaussian baseline solver 37 ms. Next: remove repeated rendering and I/O, optimize scientific kernels, repeat identical workloads and verification.
M2: lazy simulation rendering, fragments, form, per-session PNG/data reuse, metadata cache, streaming temporal means, vectorized face buffers implemented. JIT prototype tested separately on compatible wheels. Next: paired release benchmarks and regression gates.

M3. Six matched release benchmark processes completed. Peak working set 233.7 to 193.9 MiB. Snapshot 518 to 163 ms. First Run click and first Earth switch were slower. All 18 scientific check dictionaries and the historical Earth numerical exports match v0.3. Initial pytest discovery also collected the archived release and disposable Numba dependency tests under outputs. Restricted discovery to the project tests directory. Next: rerun the full suite, finalize installed package and report.

M4. Full project suite passed (71). Editable package metadata is 0.3.1. A true Chromium launch found an unreadable watchdog directory in the local venv (Windows error 1392), which AppTest did not exercise. Restored the identical watchdog 7.1.0 wheel, retained original directories in outputs/perf-repair, checked dependencies and repeated both browser sessions. Median keyboard-to-updated-map time 629 to 297 ms. Next: finalize paired numbers from the repaired environment and document limitations.

M5. The final-source run passed 71 tests, and all 18 scientific checks matched v0.3 again. A separate wheel RECORD audit found damaged dependency files beyond the watcher, including AnyIO and pandas. Preserving the local environment and staging the pinned wheels for a clean reproducibility run. Next: repeat benchmarks, unit/scientific checks, historical outputs and browser response with the clean environment, then freeze the release report.

M6. Rebuilt .venv at its original path using the exact 50 package versions. pip check passed and all installed wheel RECORD hashes matched (zero differences). The previous environment is retained under outputs/perf-repair/original-venv. Clean final measurements and both scientific gates run from outputs/perf-release/clean_gate.ps1 and verify_clean.ps1; evidence goes to outputs/perf-clean.
