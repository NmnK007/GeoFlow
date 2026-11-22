# GeoFlow v0.4 — Neural operator pilot

## Results

On a 16 × 16 periodic grid, both learned models beat persistence on held-out initial conditions and returned 16 saved predictions faster than the float64 MUSCL–MC solver. The supervised FNO had the lowest mean in-distribution error of the two learned models. The CNN took less than half the FNO's inference time and had lower final error on both shifted test sets. These are comparisons to a discretized reference solution.

| Method | ID step 1 | ID step 4 | ID step 16 | Step 16, held-out bump | Step 16, held-out rotation | Warm rollout, ms |
|---|---:|---:|---:|---:|---:|---:|
| MUSCL–MC reference | 0 | 0 | 0 | 0 | 0 | 39.80 |
| Persistence | 0.208 ± 0.038 | 0.839 ± 0.231 | 1.134 ± 0.216 | 1.256 ± 0.128 | 1.058 ± 0.182 | 0.01 |
| CNN | 0.048 ± 0.017 | 0.163 ± 0.070 | 0.347 ± 0.130 | 0.431 ± 0.044 | 0.293 ± 0.098 | 5.14 |
| FNO | 0.041 ± 0.014 | 0.124 ± 0.046 | 0.308 ± 0.098 | 0.463 ± 0.110 | 0.309 ± 0.093 | 11.29 |

ID means new trajectories drawn from the training parameter ranges. Entries are means and population standard deviations of per-trajectory relative L2 errors. Each test group contains four independent initial states. Learned-model statistics pool the same four states evaluated with two independently initialized fits. The spreads describe variation in this pilot. The repeated fits share their test trajectories. No statistical significance or population-wide ranking was established.

At step 16 the ID mean per-trajectory RMSE for height, east velocity and north velocity was **0.0599 m, 0.0109 m/s, 0.0128 m/s** for CNN and **0.0539 m, 0.0112 m/s, 0.0121 m/s** for FNO. Persistence gave 0.1646 m, 0.0542 m/s and 0.0584 m/s. The choice of field matters even where the combined metric favours the FNO.

| ID final diagnostic | MUSCL–MC | Persistence | CNN | FNO |
|---|---:|---:|---:|---:|
| Mean absolute fractional volume drift | 3.55 × 10⁻¹⁷ | 0 | 2.07 × 10⁻⁴ | 1.19 × 10⁻⁴ |
| Mean absolute fractional energy change | 0.1154 | 0 | 0.0543 | 0.0679 |

All evaluated frames were finite and had positive depth. The minimum depth across the three test groups for both main learned models was 98.44 m. The shallow-water integrator's numerical diffusion contributes to its energy change. A surrogate with less energy drift can still be wrong about the wave. Persistence illustrates the point by keeping its initial energy exactly while accumulating the largest field errors. Both learned models passed the predeclared pilot gates recorded in PROGRESS.md. Their roughly 31–35% mean ID relative error after 64 simulated minutes limits their use as substitutes for reference trajectories.

## Data and reference integration

The state is (total depth h, east velocity u, north velocity v), in metres and metres per second. Domain sides are 200 km, H = 100 m and g = 9.81 m/s². Each trajectory saves 17 frames spaced 240 s apart, from t = 0 to 3,840 s. Generation uses the same adaptive periodic MUSCL reconstruction with MC limiter, SSP-RK2 and split Coriolis rotation as the production solver. The neural dataset calls `solver.evolve_to_outputs` with its own conserved initial state. The CLI and ordinary simulation laboratory keep their existing presets.

The 32 trajectories comprise 16 training, four validation and 12 test trajectories. Dataset seeds 1200–1231 are unique across splits. A signed periodic bump uses a Gaussian-like profile in squared sine distance, giving a smooth periodic seam. Random phases vary the east and north velocity fields. Training bump magnitudes are 0.4–1.2 m, with centres in [0.15, 0.65] of each domain axis and rotation f in {−1, 0, +1} × 10⁻⁴ s⁻¹. One separate test group simultaneously shifts magnitudes to 1.4–1.8 m and both centre coordinates to [0.76, 0.96]. That group tests a joint shift. A third group uses rotations ±0.5 × 10⁻⁴ s⁻¹ strictly inside the training range and absent from training. See `neural.data.parameters`.

Channel means and standard deviations are computed from training seeds only, frames 0–6. Every model uses the same 80 training starts (five per trajectory) and 20 validation starts. The first target is one interval after each start. A two-step objective can reach frame 6. Validation selects the checkpoint with minimum one-step normalized state MSE. Evaluation starts once from held-out frame zero and feeds predictions back without further teacher inputs. Step 16 is longer than any training window. It is the longest horizon examined here.

The reference array is float64. File SHA-256 and a manifest fingerprint bind the solver configuration, seeds, initial conditions, grid, times, channel scales and array contents. Generation took **1.36 s** and peaked at **38.0 MiB** process memory. The pilot fingerprint is `c293ed775352f0d2a7dd46281da64e6acdd2b8c4b9373d87718369e29fa3c853`. Library versions are recorded for reproduction.

## Models, losses and evaluation

For each cell, normalize channel j as zⱼ = (sⱼ − μⱼ)/σⱼ. Append the constant input f / (10⁻⁴ s⁻¹). Both networks lift these four channels to width 12, apply two hidden blocks with GELU activation and project to three outputs. Both predict an increment to z. In the CNN, each hidden block uses a periodic 3 × 3 spatial convolution. It has **2,715 trainable scalar parameters**.

The FNO learns a truncated periodic integral operator. For hidden field v, its block computes GELU(Wv + inverseFFT(R(k) FFT(v)(k))). W is a pointwise channel map. R(k) is a learned complex matrix coupling channels at spatial frequency k. Multiplication at each frequency corresponds to a convolution in physical space and gives the block a domain-wide receptive field. The implementation uses a real-input 2D FFT, four nonnegative x-frequency bins and two bands of four y bins. Unused bins contribute zero to the spectral branch. The inverse real FFT returns the original shape. Real and imaginary weights are stored as pairs. The FNO has **18,843 trainable scalar parameters**. This pilot fixes grid size, periodic boundaries and f-plane forcing. The minimal PyTorch implementation keeps the spectral operation visible in `neural.models.Spectral`. [Fourier Neural Operator paper](https://arxiv.org/abs/2010.08895) · [NeuralOperator documentation](https://neuraloperator.github.io/stable/)

Training uses float32, Adam, learning rate 0.003, batch size 16, up to 24 epochs and patience eight. Each architecture and loss variant was trained with seeds 11 and 29. Checkpoints store the best and last weights, optimizer, history, seed, settings and dataset fingerprint. Resumption continues from the last completed epoch. Reported predictions use the validation-selected weights. Neither the CNN nor FNO enforces flux-form conservation.

The supervised objective is the mean squared normalized one-step error. The optional terms in `neural.train.physical_loss` and `train` are dimensionless:

- Mass uses [mean(h_pred − h_previous) / σₕ]². Constant cell area cancels. This penalizes net volume changes.
- Positivity uses the spatial mean of [max(−h, 0)/H]². It supplies a loss signal only at negative depth.
- Mechanical energy uses e = mean([h(u²+v²) + g(h−H)²]/2). Penalize [(e(pred)−e(target))/e*]² with e* = [H(σᵤ²+σᵥ²)+gσₕ²]/2. The target includes the reference solver’s numerical dissipation.
- The multi-step term adds normalized MSE after a second autoregressive step. Predictions and diagnostics use the unconstrained network output.

At each output time, the combined relative L2 metric divides the norm of the channel-scaled error by the norm of the channel-scaled reference anomaly (h−H,u,v). Training standard deviations supply the channel scales. Removing the resting depth prevents it from hiding wave error. Per-channel RMSE retains physical units. Relative metrics with zero denominators are undefined. Volume and energy drift are measured against the physical initial state.

| FNO training objective | ID step-16 error | Shifted bump | Unseen rotation |
|---|---:|---:|---:|
| Supervised | 0.308 | 0.463 | 0.309 |
| + mass (0.1) | 0.316 | 0.475 | 0.319 |
| + energy (0.05) | 0.308 | 0.462 | 0.308 |
| + positivity (1) | 0.308 | 0.463 | 0.309 |
| + two-step (0.25) | 0.296 | 0.443 | 0.297 |
| All four terms | 0.300 | 0.450 | 0.302 |

The two-step objective gave the lowest observed final mean in all three FNO groups. The mass-only penalty modestly reduced ID volume drift while worsening field error. The positivity penalty had no measurable effect here. These are paired comparisons at individual fixed weights. They do not establish optimal weights or stability for shallow or near-dry flows.

## Performance and reproduction

The CPU benchmark uses batch one and one PyTorch thread. Each method starts from identical physical fields and returns all 17 physical snapshots. Numerical timing includes conserved-state conversion, integration and sampled primitive states. Learned timing includes input scaling, prediction, output assembly and inverse scaling. The table reports the median of per-case medians over three timed runs after warmup. The numerical reference has zero forecast discrepancy by construction. It remains subject to spatial and temporal discretization error.

On this machine CNN and FNO gave **7.7× and 3.5× warm rollout speedups** over MUSCL–MC. Mean checkpoint load and first rollout were respectively 8.00 and 5.92 ms for CNN and 6.52 and 11.27 ms for FNO, excluding Python/PyTorch startup. CNN epoch work took 0.73–0.79 s per fit, FNO 1.16–1.27 s, and combined-loss FNO 2.21–2.22 s. These times exclude process startup, dataset preparation and checkpoint writes. Peak training process memory was approximately 307–308 MiB for CNN and 311 MiB for FNO. The shared evaluation process peaked at 216.9 MiB. Those process peaks include Python and native libraries. Windows PyTorch 2.15.0+cpu was used. GPU speed and memory, larger grids, nonperiodic boundaries, long-term climate statistics and observational forecast skill remain unmeasured. [Complete per-group summary](../benchmarks/neural-results-v0.4.json)

From a checkout with its virtual environment active:

```sh
python -m pip install -e ".[dev,ui,earth,neural]"
python benchmarks/neural_pilot.py outputs/my-neural-pilot
python benchmarks/neural_summary.py outputs/my-neural-pilot
python -m streamlit run app.py
```

The driver generates the dataset, trains all 14 fits and evaluates all baselines. Choose **Neural**, enter the pilot directory and select a checkpoint and held-out trajectory. **Compare rollout on CPU** computes the displayed fields. The slider then uses the saved prediction. The app has no training side effects. The existing local results are in `outputs/neural-pilot`.

Individual commands for a fresh experiment:

```sh
geoflow-neural generate outputs/my-data --grid 16 --steps 16 --train 16 --validation 4 --test 4
geoflow-neural train outputs/my-data outputs/my-fno.pt --kind fno --seed 11
geoflow-neural evaluate outputs/my-data outputs/my-scores.json --checkpoint outputs/my-fno.pt
geoflow-neural infer outputs/my-data outputs/my-prediction.npz --checkpoint outputs/my-fno.pt --index 20
```

To resume, repeat the training command with identical settings, a larger epoch limit and `--resume`. Checkpoint and dataset identifiers must match for inference. Run `python -m pytest -q` and `geoflow verify --out outputs/my-verification` for regression and solver verification. PDEBench informed the separation of rollout horizons, numerical references and baseline comparisons. This experiment uses its own trajectories and scoring definition. [PDEBench methodology](https://arxiv.org/abs/2210.07182)

## Verification

The full Windows regression suite passed 78 tests, including the 71 previous cases. All 18 numerical verification checks returned exactly the same metrics as v0.3.1. Replaying the 14 saved checkpoints reproduced every recorded per-frame metric on all 12 held-out trajectories. The CLI exported a finite 16-step prediction, and the Streamlit interaction test exercised a trained checkpoint, synchronized slider and cached prediction. A damaged local mpmath directory was restored from the same 1.3.0 wheel before the passing run. Dependency and lint checks passed. Hosted CI and CUDA were not exercised locally.

The next scientific comparison would use more independent trajectories and training seeds, separate amplitude and position shifts, and match the CNN and FNO parameter counts. A longer rollout would test whether the FNO’s early accuracy advantage persists as mass errors accumulate.
