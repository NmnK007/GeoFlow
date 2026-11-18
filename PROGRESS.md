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
