# GeoFlow v0.7 public beta report

GeoFlow is ready for local scientific review of its archive-only public profile. The strongest evidence is the comparison with the preserved release: the entire numerical verification record reproduced byte for byte, each displayed research table was checked against its source, and a browser traversed all four labs without submitting a computation. Public hosting still requires the staging checks below.

## Scientific review

GeoFlow addresses three different questions. Its finite-volume solver integrates the conservative rotating shallow-water equations on a Cartesian grid and can be tested against analytical solutions. Its Earth module advects passive tracers in externally prescribed currents and can be compared with measured drifter positions. Its neural benchmarks ask how well a learned trajectory approximates the numerical solution. These experiments have different reference quantities and sources of error. [Equations and discretization](numerics.md) · [Wave experiments](dynamics.md) · [Earth observations](earth.md) · [Surrogate methods](hpc.md)

| Experiment | Verified result | Scope |
|---|---|---|
| Smooth wave refinement | Final L1 orders at 128→256 cells per wavelength were 1.014 for first-order Rusanov, 1.899 for MUSCL–minmod and 1.980 for MUSCL–MC. | Small-amplitude smooth wave at a quarter period. Extrema and discontinuities can reduce the order. |
| Gaussian bump | Fractional anomaly-energy losses were 30.642%, 5.174% and 0.881%, respectively. | One 64 × 64 case per scheme at the same CFL, output cadence and 7200 s end time. |
| Channel waves | Rossby speed −0.9080 m/s against −0.9148 theoretical; amplitude ratio 0.8172. Kelvin speed 3.1402 m/s against 3.1623; amplitude ratio 0.9855. | Westward is negative. Phase agreement and amplitude damping are separate diagnostics. |
| Arabian Sea | RK4 mean separation 5.108 km across 48 hourly comparisons; mean at hour 24 was 8.110 km. Stationary and constant-initial-velocity means across all hours were 5.778 and 5.403 km. | Two drifters, one already undrogued, July 2020. Repeated observations from each drifter are correlated. Geostrophic currents omit wind-driven and other unresolved motions. |
| Learned rollouts | At 64 × 64 and step 24, mean familiar relative L2 over the two fits was 14.8823 for CNN and 0.4296 for FNO. Persistence scored 0.6612, first-order Rusanov 0.3033 and the MUSCL–MC self-reference 0. | Three familiar held-out cases per fit, seeds 11 and 29, 24 training trajectories and three validation cases. CNN's individual final errors were 24.0543 and 5.7104. The short training windows did not yield stable long forecasts for this CNN. |
| Computational cost | CPU warm rollout at 64 × 64 took 34.17 ms for CNN, 37.23 ms for FNO and 944.58 ms for MUSCL–MC. In the separate matched CPU/GPU study, seed-11 CNN took 39.23/21.39 ms and FNO 38.40/48.12 ms. | Ryzen 5 3500X and GTX 1650, one trajectory with all 25 frames returned. GPU setup, fitting and scoring are excluded. |

The v0.7 Research & Verification page serves six accessible tables with units, methods, source identifiers, per-seed accuracy, intermediate error horizons and an exact JSON download. Earth and Neural display precomputed results. Visitors can compare the two latitudes, inspect the Arabian Sea tracks, switch inference model or field, and filter all 50 HPC records without downloading external datasets or loading training weights. [Verification record](../benchmarks/web-demo/verification.json) · [Observational record](../benchmarks/web-demo/validation.json) · [HPC records](../benchmarks/hpc-results.json)

## Release verification

| Gate | Evidence |
|---|---|
| Repository and recovery | Original tag v0.6.0 remains at 898ddbe. Local annotated tag v0.6.0-verified preserves 749615a, including the cross-platform CI fix. GitHub reported successful scientific checks for that commit. Git object integrity passed; five unreferenced trees were present. The separate 159-entry recovery ZIP passed CRC and its SHA-256 was beb79bd1271dae629a4936506face7ac2c45e8e2fcbf46ccc11256f9da71ab15. Historical D: corruption remains documented. These source checks do not diagnose drive hardware. |
| Python and scientific parity | All 89 v0.6 tests passed from the archived source. All 93 v0.7 tests passed with the local study installed. All 18 scientific checks passed. The new verification JSON and v0.6 archive have SHA-256 3c6eaa72b08190cb407c2bba2c37d5f94702ee92cdafdc9abf83d9d2ba4865845. Existing parity tests cover both latitude demos, field units and axes, full-resolution exports, Earth trajectories and checkpoint predictions. |
| UI and API fidelity | The five existing browser scenarios passed. Additional tests compared every research table cell to its JSON record, restored a job after reload and network interruption, traversed the read-only public journey, and checked all four labs for horizontal page overflow at 390 and 768 px. Reduced motion and animation pause/resume passed. These checks cover Chromium; screen-reader user testing and physical-device testing remain open. |
| Job reliability | Tested admission, cancellation, invalid config, worker failure, timeout, held downloads, retention expiry, restart and unknown job IDs. The five-client local trial returned four accepted jobs and one 429. Its health request took 8.2 ms while the queue was occupied. The single supervisor remains suitable for private local use. |
| Build and dependencies | Next.js production build and type checking passed. Ruff and pip check passed. npm audit returned zero advisories for the locked tree; the PyPI version records for all 30 web constraints returned zero listed advisories. This is a point-in-time package check. The full research environment, container base images and host OS need their own deployment audit. A Starlette test-client deprecation warning remains. |
| Deployment boundary | Local read-only and local writable browser profiles exercised the real API. Docker was unavailable on this machine, so v0.7 container execution is unverified. The CI workflow now checks research routes in the Compose stack and reruns scientific verification. Public DNS, TLS, target-host capacity and rollback have not been exercised. |

## Browser measurements

Medians in milliseconds from three fresh Chromium contexts per release and profile. Both releases used production Next.js, loopback FastAPI, the same benchmark script, the same 64 × 64 simulation and the same operator-registered 256 × 256 synthetic ocean map. The map is a rendering fixture. The normal viewport was 1360 × 900. The constrained profile combined a 390 × 844 viewport with Chromium's 4× CPU throttle. Both profiles rendered the landing animation. The benchmark used the private writable mode so that submission and result export could actually run.

| Browser endpoint, ms | v0.6 desktop | v0.7 desktop | v0.6 constrained | v0.7 constrained |
|---|---:|---:|---:|---:|
| Landing heading | 198.5 | 308.0 | 703.2 | 673.7 |
| Animation frame interval | 7.0 | 7.0 | 7.0 | 7.0 |
| Simulation navigation to first map | 186.9 | 175.9 | 387.3 | 448.0 |
| Submission to HTTP 202 | 294.2 | 278.4 | 113.6 | 79.7 |
| Scientific field selection | 53.2 | 53.7 | 105.9 | 132.0 |
| ZIP download to completion | 307.2 | 451.1 | 268.4 | 538.3 |
| 256 × 256 regional map | 285.7 | 286.0 | 331.8 | 210.1 |
| Switch FNO to CNN | 66.8 | 53.8 | 159.4 | 132.8 |
| HPC device filter | 16.1 | 12.0 | 52.3 | 38.1 |

Windows 11 build 26200, Ryzen 5 3500X, Python 3.14.6, Node 26.13.0 and headless Chrome 158.0.8127.38. The animation probe measures the mean interval across 30 requestAnimationFrame callbacks while the canvas is visible; it cannot establish physical display FPS, GPU utilization or sustained frame pacing. Browser interaction timings include automation scheduling. The two viewport profiles have different layouts. Three samples give limited precision and local cache and host load can affect timings. Desktop landing latency increased by 110 ms and the constrained export median nearly doubled. Repeated instrumented download trials on the target host should separate server transfer time from browser and filesystem overhead before optimizing. [All 12 trial records](../benchmarks/beta-browser.json)

## Independent review

1. Follow the local public-profile instructions. Open **Research** and download the displayed JSON. Verify the values against the three source records above. In **Simulation**, compare the 0° and 45° bumps at the same output time. In **Earth**, select a historical drifter. In **Neural**, inspect the paired reference and prediction. In **HPC**, compare devices within a paired run. [Installation and deployment checklist](beta-operations.md)
2. In a research environment, install `python -m pip install -e ".[dev,earth,ui,neural,web]"`. Run `python -m pytest -q`, `ruff check .` and `python -m geoflow.cli verify --out outputs/reviewer-verification`. Compare the JSON checks to the archived record. Other machines may differ at floating-point roundoff. Optional live-checkpoint parity needs the matching local v0.5 study. [Data and model reproduction](hpc.md)
3. Build the frontend. For browser regression, install Playwright Chromium with `npx playwright install chromium` from `web` or supply `GEOFLOW_CHROME`. With ports 3071 and 8000 free, run `npx playwright test labs.spec.ts beta.spec.ts` from `web` against private mode. Set `GEOFLOW_READ_ONLY=1` and run `npx playwright test beta.spec.ts` for the actual public profile. The harness starts and stops its own services.
4. For matched timings, first run `python benchmarks/beta_map.py` from the root. Set `GEOFLOW_EARTH_REGISTRY` to the absolute path of `outputs/beta-v07/registry.json`, clear `GEOFLOW_READ_ONLY`, and set `GEOFLOW_BENCH_OUT` to a fresh result directory. Run `npx playwright test performance.spec.ts --repeat-each=3` from `web`. To compare another checkout, set `GEOFLOW_ROOT` and `PYTHONPATH` to its root and src directory, `GEOFLOW_WEB_BUILD` to its built web directory and `GEOFLOW_PYTHON` to the matching interpreter. Keep these variables fixed within each release.

## Contributions and remaining release decisions

Scientific changes should specify the physical question, coordinates, units, reference, numerical method, sample size and failure criterion. Include a deterministic regression at the smallest meaningful scale. Preserve the original evidence and publish new results with input fingerprints, measured environment and limitations. UI or API changes should preserve full-resolution exports and exercise both execution profiles.

Before exposing a beta publicly, the owner needs to select the GeoFlow license, confirm dataset redistribution terms and attribution, review dependency notices, test the actual container images, configure TLS and edge limits, and exercise staged load and rollback. For a future shared compute service, job ownership, durable lifecycle and storage quotas are prerequisites. Scientific extensions would benefit from independent drifter cohorts, more held-out rollout seeds and long-horizon stability analysis. These remain outside this release.
