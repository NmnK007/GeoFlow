# GeoFlow v0.1

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
