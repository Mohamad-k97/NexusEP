# Annex 71 measured-plane runtime and error report v8

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with documented post-unsealing source-schedule, time, RC-mapping, airflow, topology, and radiative-boundary corrections for the Extended Experiment. This is not pristine blind-validation evidence.

## Decision

Strict gate: **rejected**.
The original Phase 4.9 row remains **blocked and rejected with alternative**. Failed frozen checks: pooled_rmse, pooled_bias, per_zone_rmse, no_missing_scored_inputs.

## Runtime

| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |
|---|---:|---:|---:|---:|---:|
| Main hourly | 1056 | 30.090 | 35.095 | 0.028494 | 358.9 |
| Extended 10-minute | 4896 | 160.939 | 30.421 | 0.032872 | 358.9 |

The 72-hour 10-minute sample was run twice after warm-up: median 12.630 s, range 12.366-12.894 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

Post-run performance diagnosis found that each physical timestamp's immutable
NREL-SPA result was calculated once while compiling canonical weather and again
inside the object adapter. A subsequent UTC-instant-keyed cache leaves outputs
identical and reduces the 72-hour measured repetitions from the v8 median
12.630 s to 11.091 s on the first cache-filling repetition and 5.465 s at
steady state. The 160.939 s full-run value above remains the immutable v8
measurement; no unmeasured full-run replacement is claimed.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.379 | 1.469 | 1.819 | 6.589 |
| Extended primary | 2.128 | 2.175 | 2.489 | 7.474 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.039 | 1.218 | 1.454 | 3.591 | 0.694 |
| ground_airbody | 2.578 | 2.578 | 2.701 | 4.395 | 0.811 |
| kitchen_airbody | 3.410 | 3.410 | 3.541 | 7.474 | 0.762 |
| sleeping_airbody | 1.486 | 1.495 | 1.681 | 3.344 | 0.572 |

### Error structure

Day pooled RMSE: 2.528 degC; night pooled RMSE: 2.449 degC. First scored week RMSE: 1.472 degC; last scored week RMSE: 3.276 degC.

Maximum absolute thermal-balance residual: 1.969e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The canonical adapter now couples the mass node through the full graph-derived opaque surface area instead of the incomplete floor-plus-interzone estimate. The coefficient itself remains the declared model constant; no residual-derived value was introduced.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) the single air-to-mass coefficient cannot represent layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest prior kitchen errors coincided with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, exposing items (1)-(3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocols 1.1 through 1.6 preserve every post-unsealing correction; protocol 1.6 freezes measured cardinal vertical-plane forcing.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_measured_plane_runtime_error.py
```

Implementation commit: `3d15372457fe25b30a68db6ca5ef890abef79adc`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc, ?? tmp/`.
