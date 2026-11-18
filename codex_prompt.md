# GeoFlow — Codex implementation prompt

Copy the text below into Codex while it is opened in the GeoFlow repository root. Place `research.md` in the same repository root first.

---

Act as a scientific software engineer specializing in computational fluid dynamics, numerical PDEs and geophysical fluid dynamics. You are helping a first-year Engineering Physics student build **GeoFlow**, an open-source, transparent computational laboratory for rotating shallow-water flows. Build a real, testable initial release (v0.1), not a mock UI or a production weather forecast system.

## 1. Workflow and scope

Read `research.md` before writing code. Treat its v0.1 equations, physical assumptions, conventions and numerical method as the implementation contract. Inspect existing repository files and preserve unrelated user content. If the repository is empty, initialize the package structure. Briefly write an actionable implementation plan, then execute it in this session; do not stop after giving a plan. Work in stages: (1) core flux/physics and unit tests; (2) solver, boundaries and numerical verification; (3) presets, CLI, exports and docs; (4) a lightweight local UI only after meaningful solver verification. Run tests at each gate. If a gate fails, investigate it and report remaining limitations rather than building fake outputs around it. Do not train ML models, fetch large datasets, implement 3D, add a database, deploy to cloud, or build a global ocean model in v0.1. Don't modify unrelated files, commit/push without request, download unrelated resources or ask for credentials. Use CPU-only tools and a normal Windows/macOS/Linux development workflow.

## 2. Physics implementation (non-negotiable)

Use SI units and a flat-bottom, single-layer, inviscid hydrostatic shallow-water model. The local Cartesian axes are east x and north y. The conserved state Q = (h, mx, my), with positive total depth h = H + eta, mx = h*u and my = h*v. Store float64 arrays with shape (3, ny, nx). Cell axes are [y, x].

Implement dQ/dt + dF/dx + dG/dy = S:

- F(Q) = (mx, mx*mx/h + 0.5*g*h*h, mx*my/h)
- G(Q) = (my, mx*my/h, my*my/h + 0.5*g*h*h)
- S(Q) = (0, f*my, -f*mx)
- f = 2*Omega*sin(latitude in radians), Omega = 7.292115e-5 rad/s; support latitude in [-90,90] and explicit signed f override, with unambiguous precedence, units and resolved metadata.

Use a first-order conservative finite-volume Rusanov flux. At an x face use 0.5*(F_L + F_R) - 0.5*a*(Q_R - Q_L), where a=max(abs(u_L)+sqrt(g*h_L), abs(u_R)+sqrt(g*h_R)); analogously use G and v at y faces. Build each shared interface flux once, and apply flux differences along the correct axes. Implement periodic and reflecting free-slip ghost cells independently in x/y. For a solid wall, reflect normal momentum only. Handle non-square grids correctly.

Time integration: flux-only forward Euler followed by exact isolated Coriolis rotation (first-order Lie splitting), using old momentum components simultaneously: mx'=mx*cos(f*dt)+my*sin(f*dt), my'=my*cos(f*dt)-mx*sin(f*dt). Do not use forward Euler for the source. Do not describe the full update as exact, high-order, energy-preserving or well-balanced.

Use adaptive unsplit dt = CFL/(max(abs(u)+sqrt(g*h))/dx + max(abs(v)+sqrt(g*h))/dy), default CFL=0.4 and allowed (0,0.5]. Also cap dt at 0.1/abs(f) for nonzero f to resolve rotation, plus next output time and final time. This rotational bound is an accuracy heuristic. Guard rounding at output times and avoid infinite loops. Validate positive h, finite values, positive physical/grid parameters, valid boundary settings and sensible limits. Reject invalid trial steps, halve dt and retry up to a documented limit; fail clearly if unable to advance. Never silently clip depth, replace NaNs or break conservation to get a demo to run. Wet/dry interfaces are explicitly unsupported.

## 3. Package and interfaces

Use Python >=3.11, NumPy and Matplotlib for the core; pytest and Ruff in dev extras; Streamlit in optional `ui` extras. Use stdlib argparse, dataclasses, JSON and CSV. No unnecessary frameworks or runtime external network calls. Use a `src` layout with an editable installation. Keep public APIs typed and concise; document array shapes, sign conventions and units. Do not write giant monolithic files or duplicate the solver in the UI.

Suggested tree (adapt only with a clear reason):

```text
research.md
README.md
pyproject.toml
.gitignore
src/geoflow/
  __init__.py
  config.py
  grid.py
  state.py
  boundaries.py
  physics.py
  solver.py
  initial_conditions.py
  diagnostics.py
  io.py
  plotting.py
  cli.py
app.py
configs/
  lake_rest.json
  gravity_wave.json
  gaussian_bump.json
  geostrophic_adjustment.json
  inertial_oscillation.json
tests/
  test_physics.py
  test_boundaries.py
  test_solver.py
  test_verification.py
  test_io.py
docs/
  numerics.md
  experiments.md
  limitations.md
.github/workflows/ci.yml
```

Use config dataclasses with validation and a JSON loader. Include physical domain size, cells in each direction, mean depth, gravity, latitude/override, initial condition parameters, boundary types, CFL, duration, sample interval, step limit and resource limits. Make units explicit in config keys or schema. No hidden global mutable state. API concept: `run_simulation(config, progress_callback=None) -> SimulationResult`, with time, positions, snapshots, diagnostics, metadata. The CLI and UI must use that same API. Avoid mutation of caller inputs and ensure completed snapshots are copies, not views of the final state. Cap grids, frames, projected memory (e.g. 256 MiB for fields plus a separate working-memory estimate), retries and steps; use safer UI defaults. Never accidentally allocate a huge array before config validation.

## 4. Presets, diagnostics and output

Implement reusable lake-at-rest, small-amplitude periodic sinusoidal gravity wave, Gaussian bump without rotation, rotating Gaussian geostrophic-adjustment experiment and uniform inertial oscillation. Use the example scales from `research.md` with light defaults and explicit units; label geostrophic adjustment as approximate rather than exact balance. Seed any randomness deterministically. For the sinusoidal wave use h=H+eta, eta=epsilon*H*sin(k*x), u=sqrt(g*H)*eta/H, v=0 and small epsilon. For uniform inertial oscillation use constant H and initial u=1 m/s, v=0.

Compute volume sum(h)*dx*dy and relative volume drift; mechanical energy per unit density relative to H as sum(0.5*h*(u*u+v*v)+0.5*g*(h-H)**2)*dx*dy; relative energy change only if initial energy is nonzero. Report min/max h, max speed, step dt, CFL, rejected steps, wall time. Compute relative vorticity = dv/dx-du/dy and PV=(vorticity+f)/h with boundary-aware discrete gradients; document diagnostic stencil and limitations. Do not imply energy/PV are exactly conserved by Rusanov.

Write `metadata.json`, `fields.npz` (time, x, y, h, u, v; each 3D physical field shaped nt,ny,nx), `diagnostics.csv`, and a real computed plot per successful run. Include exact normalized config, resolved f, units, scheme, boundary conditions, version, actual runtime, completed/failed status and errors when applicable. Use standard JSON-compatible finite values or null for undefined diagnostics. Use `np.load(..., allow_pickle=False)` for reading test outputs. Avoid overwriting a nonempty output directory without explicit opt-in. Keep generated outputs gitignored.

## 5. Scientific acceptance tests (write and run)

Use independent analytical expressions, not outputs from another copy of the same implementation. Do not weaken thresholds simply to make tests green.

1. Fluxes agree with physical flux when left and right states are identical. Source rotation preserves h and momentum magnitude; signs correct for both hemispheres. Validate boundary ghost values and no normal wall mass flux.
2. Constant rest state on periodic and reflecting grids, with and without f, stays unchanged (absolute state tolerance ~1e-10 on small test grids). Uniform periodic translation at f=0 stays unchanged.
3. Uniform periodic inertial flow follows u=U*cos(f*t), v=-U*sin(f*t) at intermediate times and a full inertial period, for both signs of f; relative velocity L2 tolerance ~1e-10 for small float64 tests.
4. Small-amplitude nonrotating sinusoidal wave: periodic wavelength Lx, epsilon=1e-4, evaluate at Lx/(4*sqrt(g*H)). For x refinements 32,64,128 (ny can remain small with y-uniform state), compute height-anomaly relative L2 error against eta_exact=epsilon*H*sin(k*(x-c*t)); error should decrease with refinement. Recover wave speed from Fourier phase and expect within 10% on finest grid. Report measured error, speed and empirical convergence; account for approximation to linear dynamics. Do not compute relative error using the mean depth as the denominator.
5. For representative periodic Gaussian bump and reflecting wall runs, relative volume drift <=1e-10 on float64, all states finite and positive. Test non-square grids and x/y directionality.
6. Invalid dimensions, duration, CFL, initial depths, NaNs, resource limits and impossible advancement fail meaningfully. Verify exact output timestamps (within roundoff), final time, export metadata and roundtrip shapes. Test default configurations and step-retry path where practical.

Expose a `verify` CLI that runs a quick numerical verification suite and saves a real JSON report plus convergence CSV/plot. The same verification routines may be used from tests; they must compute results, not contain hardcoded passes. On any failed check return nonzero exit status and retain diagnostic output. A test is not a real-ocean validation. Clearly document remaining limitations, particularly first-order dissipation, no exact geostrophic balance and lack of real observations.

## 6. Local visualization (only once core works)

Create a compact scientific laboratory in Streamlit with a parameter sidebar, preset selector, domain/grid/depth/latitude/duration controls, explicit Run Simulation action, field selector, time slider and reset action. Cache or store computed results only as appropriate; changing a plot selector must not rerun the PDE. If simulation settings change, clearly show that the existing result is from the previous configuration until rerun. Display a physical x/y heatmap with units and colour bar and correct aspect ratio, fixed color limits across snapshots by default, optional sparse velocity arrows, and plots of conservation errors and energy. Include metadata, actual runtime, min depth and clear failure messages. Show a progress indicator or step status based on actual progress, not fake animation. Use restrained scientific styling (dark navy or neutral backgrounds and perceptually appropriate colormaps, accessible labels), not a generic SaaS dashboard. Provide download or output directory access to generated artifacts if straightforward. Don't add decorative maps, fabricated metrics or claimed real-time weather. The user must be able to run without the UI dependency using the CLI.

## 7. Installation and documentation

Document quickstart for Windows PowerShell (including an option to use `.venv/Scripts/python.exe` without changing execution policy), macOS and Linux. Make these commands work with the actual repository:

```bash
python -m venv .venv
# activate environment (see README)
python -m pip install -e ".[dev,ui]"
python -m geoflow.cli run --config configs/gaussian_bump.json --out outputs/demo
python -m geoflow.cli verify --out outputs/verification
python -m pytest -q
python -m streamlit run app.py
```

Add `.gitignore` for env, caches and generated outputs. CI should install `[dev]`, run tests and lint, avoiding heavy simulations or GUI dependencies. For mathematical notes, include the original PDE, the derivation of the conservative state, face flux and update, time step reasoning, Coriolis sign convention and conservation metrics. Explain one time step with a small grid and map the math to actual function names. Include a concise reading order for this student to understand and extend the project independently. Document limitations and reserve beta-plane, topography, real-data ingestion, ML and GPU work for later releases. Do not add an arbitrary license if the existing repository has none; mention that a license should be chosen before publishing.

## 8. Execution and final report

Actually implement the scoped changes and run tests and at least one quick CLI simulation/verification in the available environment. Prefer minimal dependencies. If environment restrictions prevent installation, testing, or the UI launch, explicitly distinguish completed code from unexecuted checks. Do not invent measurements, screenshots, tests passed, speedups or features. If verification fails, fix root causes where possible; mark any remaining failure and do not describe it as production-ready.

At the end, provide:

- A concise summary of implemented features, assumptions and main design decisions.
- The actual files created or changed and the commands to run locally.
- Actual test results and sample diagnostics (or explicitly state that they could not be measured).
- Known issues, verification limits and improvements needed before v0.2.
- A recommended first manual exercise for me: inspect the Rusanov face flux and re-derive the conservation update, then compare the same Gaussian disturbance at f=0 and f corresponding to 45° latitude.

Your objective is a scientifically credible, understandable first implementation, not the biggest possible feature list. Prioritize numerical correctness and reproducibility over a polished dashboard. Start by inspecting `research.md` and the existing repo; proceed to implementation now.
