# Annex 71 large-opening runtime and error report v5

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with documented post-unsealing source-schedule, time, RC-mapping, and large-opening corrections for the Extended Experiment. This is not pristine blind-validation evidence.

## Decision

Strict gate: **rejected**.
The original Phase 4.9 row remains **blocked and rejected with alternative**. Failed frozen checks: pooled_rmse, pooled_bias, per_zone_rmse, no_missing_scored_inputs.

## Runtime

| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |
|---|---:|---:|---:|---:|---:|
| Main hourly | 1056 | 10.015 | 105.438 | 0.009484 | 355.4 |
| Extended 10-minute | 4896 | 70.014 | 69.929 | 0.014300 | 355.4 |

The 72-hour 10-minute sample was run twice after warm-up: median 4.140 s, range 3.998-4.283 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.250 | 1.357 | 1.671 | 7.896 |
| Extended primary | 2.295 | 2.337 | 2.626 | 7.783 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.104 | 1.268 | 1.517 | 3.774 | 0.689 |
| ground_airbody | 2.562 | 2.562 | 2.695 | 4.437 | 0.789 |
| kitchen_airbody | 3.489 | 3.489 | 3.623 | 7.783 | 0.765 |
| sleeping_airbody | 2.026 | 2.027 | 2.212 | 4.261 | 0.545 |

### Error structure

Day pooled RMSE: 2.671 degC; night pooled RMSE: 2.580 degC. First scored week RMSE: 1.525 degC; last scored week RMSE: 3.466 degC.

Maximum absolute thermal-balance residual: 1.537e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The canonical adapter now couples the mass node through the full graph-derived opaque surface area instead of the incomplete floor-plus-interzone estimate. The coefficient itself remains the declared model constant; no residual-derived value was introduced.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) the single air-to-mass coefficient cannot represent layer-resolved surface transfer; (3) vertical-door exchange now uses the NIST two-opening buoyancy equation, while the horizontal attic hatch still uses an explicit prescribed 0.10 m/s compatibility path and no whole-building pressure solve exists; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest prior kitchen errors coincided with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, exposing items (1)-(3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocols 1.1 through 1.4 preserve every post-unsealing correction; protocol 1.4 freezes the target-independent large-opening and attic-state mapping change.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_large_opening_runtime_error.py
```

Implementation commit: `971397bb802b442f3c9f8e4d3439121261995716`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc`.
