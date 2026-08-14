# Annex 71 sky-boundary runtime and error report v7

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
| Main hourly | 1056 | 30.667 | 34.435 | 0.029040 | 357.3 |
| Extended 10-minute | 4896 | 135.636 | 36.097 | 0.027703 | 357.3 |

The 72-hour 10-minute sample was run twice after warm-up: median 11.293 s, range 11.282-11.305 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.092 | 1.229 | 1.535 | 6.144 |
| Extended primary | 2.131 | 2.181 | 2.483 | 7.431 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.013 | 1.206 | 1.447 | 3.569 | 0.680 |
| ground_airbody | 2.530 | 2.531 | 2.663 | 4.382 | 0.799 |
| kitchen_airbody | 3.333 | 3.333 | 3.471 | 7.431 | 0.751 |
| sleeping_airbody | 1.648 | 1.656 | 1.853 | 3.538 | 0.523 |

### Error structure

Day pooled RMSE: 2.529 degC; night pooled RMSE: 2.437 degC. First scored week RMSE: 1.431 degC; last scored week RMSE: 3.294 degC.

Maximum absolute thermal-balance residual: 1.606e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The canonical adapter now couples the mass node through the full graph-derived opaque surface area instead of the incomplete floor-plus-interzone estimate. The coefficient itself remains the declared model constant; no residual-derived value was introduced.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) the single air-to-mass coefficient cannot represent layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest prior kitchen errors coincided with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, exposing items (1)-(3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocols 1.1 through 1.5 preserve every post-unsealing correction; protocol 1.5.1 freezes the missing canonical-to-object sky-temperature handoff.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_sky_boundary_runtime_error.py
```

Implementation commit: `8a65c939103e331d100a8797b27a49b4ae42d57a`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc, ?? tmp/`.
