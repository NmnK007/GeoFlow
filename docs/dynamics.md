# GeoFlow v0.2 Dynamics

## Numerical method

Old configurations still use the v0.1 flux and Lie rotation. Select `scheme="muscl"` and `limiter="mc"` or `"minmod"` in a config to use the higher-order path. Both schemes solve the conservative system in [the baseline derivation](numerics.md).

For each cell and each conserved component form backward and forward undivided differences b and d. Minmod takes the smaller absolute difference with their common sign, or zero if the signs differ. MC takes minmod(2b,(b+d)/2,2d). The two cell traces are Q±s/2. In each direction, pass the adjacent reconstructed traces to the Rusanov flux. At a wall mirror the interior face trace and reverse its normal momentum. Each internal flux cancels between its two neighbours. The limiter bounds reconstructed depths by neighbouring depths. Extrema and underresolved gradients can locally reduce the spatial order.

Let E(Q)=Q+Δt L(Q), where L is the sum of the two negative flux divergences. With R the exact local momentum rotation, the step in `solver.trial` is

    P = R(Δt/2) Q
    Z = E(P)
    W = ½ P + ½ E(Z)
    Q_new = R(Δt/2) W

`muscl.interfaces` builds the fluxes. `muscl.euler` checks face and stage depths and rejects reconstructed directional CFL sums above 0.5. The initial step proposal uses the configured cell-centred CFL. Either RK stage can reject the whole step. Retries halve Δt from the last accepted state. The rotation-resolution cap uses the largest |f| across the grid. Both rotation substeps are exact for the isolated source at each row. Splitting and reconstruction errors remain in the coupled solution.

## Physical parameters

The beta plane uses f(y)=f₀+β(y−Ly/2), β=2Ω cos(φ₀)/R with Earth radius 6,371 km. An override changes central f₀ while latitude still sets β. Use a zonally periodic channel with free-slip north/south walls. This linear latitude approximation is local. The Rossby preset requires a nonzero midlatitude f throughout the channel.

Optional reduced gravity g′ represents a light active layer over a deep, quiescent denser layer, with g′≈g Δρ/ρ. Set `reduced_gravity_m_s2` explicitly. All pressure fluxes, wave speeds, initial conditions, reference fields and potential energies use the resolved acceleration g*. For an active layer, η measures thickness anomaly and the restoring pressure models interface displacement. The model omits lower-layer motion and independent surface and internal modes.

With c=√(g*H), the metadata gives the central deformation radius c/|f₀|. Each diagnostic row uses U=max speed and L=min(Lx,Ly) for Fr=U/c and Ro=U/(|f₀|L). These domain-scale choices can differ from a jet-width-based Rossby number. Rotation-dependent scales are undefined at f₀=0. Absolute vorticity is ζ+f(y), potential vorticity is q=(ζ+f)/h and potential enstrophy is Σ h q² ΔA/2. The continuum material PV invariant does not imply a fixed Eulerian PV field for moving disturbances.

## Six experiments

Here k=2π/Lx, l=π/Ly and a=εH. `initial_conditions.mode_fields` sets the velocities and anomalies. `reference.height_reference` supplies analytical or asymptotic anomaly references when available. The plotted relative L2 reference error uses the anomaly norm.

| Preset | Initial-value problem and benchmark | Interpretation limits |
|---|---|---|
| rossby_wave | η=a cos(kx) sin(ly), u=−g*η_y/f₀, v=g*η_x/f₀. The leading-order balanced beta-channel mode moves west at −β/(k²+l²+1/Rd²). | Quasi-geostrophic approximation. Initial imbalance excites faster modes. Phase and amplitude both matter. |
| coastal_kelvin | Along the southern wall, η=a cos(kx) exp(−y/Rd), u=sign(f₀)cη/H, v=0. Speed is sign(f₀)c. | Linear trapped mode with free-slip walls. Cross-shore resolution controls approximation to the exponential decay. |
| inertia_gravity | Periodic y-uniform mode with η=a cos(kx), u=aω cos(kx)/(kH), v=af₀ sin(kx)/(kH), ω²=f₀²+c²k². | Small-amplitude linear reference for the nonlinear evolution. |
| balanced_jet | η=a cos(2ly), v=0, u=−g*η_y/f₀. Nonlinear advection vanishes, giving an exact steady continuum solution. | Finite-volume diffusion and time splitting introduce imbalance. |
| shear_instability | U tanh((y−Ly/2)/σ) in an unrotated channel. A localized, wall-compatible meridional seed excites a sinuous disturbance of wavelength Lx. | The inflectional jet permits instability. Measured meridional RMS velocity grew by 1.204× in this run. A single finite-time gain does not establish an eigenmode growth rate. |
| vortex_pair | Two same-signed smooth periodic Gaussian-like anomalies with analytically geostrophic initial velocities. Track core separation, orientation and energy. | Gradient-wind and advective terms induce adjustment. The 48² preset lost 51.25% of anomaly energy in one day. Merger timing is unverified at this resolution. |

Wave theory and derivations are covered in lectures 22–24 of [MIT's Fluid Dynamics of the Atmosphere and Ocean](https://ocw.mit.edu/courses/12-800-fluid-dynamics-of-the-atmosphere-and-ocean-fall-2004/pages/lecture-notes/).

## Measured evidence

The `verify` command reruns the v0.1 checks, then the v0.2 experiments in `benchmarks.py`. The report includes individual errors and pass thresholds are in the benchmark functions. For a smooth travelling wave with ε=10⁻⁶ at a quarter period, use the integrated absolute anomaly error divided by integrated absolute analytical anomaly (relative L1). The last refinement below is 128→256 cells per wavelength. The Gaussian comparison holds the original physics, grid (64²), duration (7200 s), output interval (600 s) and CFL (0.4) fixed.

| Method | Relative L1 at 256 | L1 order | Relative L2 at 256 | Gaussian energy loss |
|---|---:|---:|---:|---:|
| Baseline | 0.011690 | 1.014 | 0.011690 | 30.642% |
| MUSCL minmod | 0.000643 | 1.899 | 0.001128 | 5.174% |
| MUSCL MC | 0.000208 | 1.980 | 0.000360 | 0.881% |

The MC energy loss is 29.76 percentage points smaller here. This measures one controlled disturbance and grid. There is no energy correction in either update.

| Wave | Theory / measured speed (m/s) | Relative height L2 | Retained first-mode amplitude |
|---|---:|---:|---:|
| Rossby | −0.91477 / −0.90795 | 0.17773 | 81.72% |
| Kelvin | 3.16228 / 3.14021 | 0.02961 | 98.55% |
| Inertia–gravity | 35.36082 / 35.41144 | 0.00529 | 99.99% |

Speeds use the unwrapped phase of the first x Fourier coefficient averaged in y. Tests compare against the dispersion relation for each configuration and also check full-field anomaly error, volume and depth. The Rossby result resolves the sign and approximate speed much better than the amplitude. The integrations cover finite phase shifts, not multi-cycle dispersion curves.

Over ten inertial periods (3350 steps), the steady-jet normalized meridional force residual rose from 0.001606 to 0.002933. This is ‖g* D_y h + f₀u‖₂ / ‖f₀u_initial‖₂, including stencil error at t=0. Final PV error relative to the analytical PV anomaly norm was 2.442%. Relative potential-enstrophy change was −3.65×10⁻⁷, maximum relative volume drift 1.09×10⁻¹⁵, and minimum depth 99.9001 m. These checks probe long-duration smooth balance. Wet/dry fronts, shocks and observational fidelity remain outside the verified regime.

## Reproduction and exercises

Run `python -m geoflow.cli verify --out outputs/check-v02` from an installed checkout. Inspect `verification.json` for the individual measurements and `scheme_convergence.csv` for all three resolution series. The original five presets retain their v0.1 defaults.

1. Compute MC and minmod slopes by hand for neighbouring cell means (1,2,4) and (1,3,2). Reconstruct the two faces and identify where second-order accuracy is lost.
2. Pin the baseline Gaussian and rerun with MC. Compare energy at identical times, then double resolution for one scheme to distinguish limiter and grid effects.
3. Reverse the Kelvin latitude and predict the alongshore propagation direction before running. For Rossby waves, refine both axes and compare amplitude retention alongside phase speed.
4. In comparison mode the slider covers the union of sample times in the overlapping interval. Primitive fields are linearly interpolated in time on each native grid. Exported diagnostic traces are interpolated from saved scalar diagnostics. A same-grid RMS height-anomaly difference compares two simulations; an analytical error is available only where a reference exists.
