# v0.1 experiments and evidence

The six additional presets and their benchmarks are in [Dynamics](dynamics.md).

All presets use g=9.81 m/s², H=100 m and periodic boundaries. JSON lengths and times are in metres and seconds. Unspecified keys use the defaults in `config.Config`. The normalized configuration in metadata includes those defaults.

| Preset | Initial state | Interpretation |
|---|---|---|
| lake_rest | Constant H, zero momentum | Tests cancellation of uniform pressure flux |
| gravity_wave | η=10⁻⁴ H sin(2πx/Lx), u=√(gH)η/H, v=0 | Right-going, small-amplitude wave |
| gaussian_bump | Resting 1 m Gaussian, σ=80 km, 1000 km square | Two hours of free spreading |
| geostrophic_adjustment | Resting 1 m Gaussian, σ=150 km, 2000 km square, 45° N | Approximate rotational adjustment over one day, with periodic returns possible |
| inertial_oscillation | Uniform u=1 m/s, v=0, 45° N | Clockwise motion over one inertial period |

Run `python -m geoflow.cli verify --out outputs/check1` to generate the measured JSON checks, CSV and convergence plot. The verification configuration uses Lx=34 km and four y cells for the wave test. At one quarter period, compare the final η with 10⁻⁴ H sin(k(x−ct)), c=√(gH), k=2π/Lx. Normalize the L2 difference by the L2 norm of the exact anomaly. Taking the negative argument of the ratio of final to initial first Fourier coefficients and dividing by kt gives phase speed. A quarter period avoids phase wrapping. Order is log₂(error at N / error at 2N).

| Cells per wavelength | Relative L2 error | Phase speed (m/s) | Observed order |
|---:|---:|---:|---:|
| 32 | 0.0980191 | 31.2755 | — |
| 64 | 0.0479664 | 31.3121 | 1.031 |
| 128 | 0.0236075 | 31.3191 | 1.023 |

The analytical speed is 31.32092 m/s. The reference solves the linearized equations while the code evolves the nonlinear equations. The decreasing error and nearly first-order rate hold over these tested resolutions. Uniform inertial flow has an independent exact solution (cos(ft),−sin(ft)) m/s. The suite checks quarter periods as well as the full period, including negative f. Unit tests separately exercise face signs, non-square orientations, failure paths and IO.

## First exercise

Trace a single mass face through `physics.rusanov` and `solver.trial`. Re-derive the 3×2 example in the numerical notes and predict the sign of the depth change before running it. In the laboratory select gaussian_bump, run at 0°, then change only latitude to 45° and run again. Save each run to its own directory. Compare height, velocity direction, relative vorticity and energy at the same simulated times and colour scale. Keeping domain, width and sampling identical isolates the rotation change. The two showcase Gaussian presets also differ in scale and duration.

Each successful CLI run produces `fields.npz` with time, x, y and (nt,ny,nx) h,u,v, a final height-anomaly PNG, diagnostics CSV and metadata JSON. Load arrays with `np.load(path, allow_pickle=False)`. The metadata records the signed resolved f and the exact configuration used.
