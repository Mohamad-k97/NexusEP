# Annex 71 physical-model runtime and error report v4

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with documented post-unsealing source-schedule, time, and RC-mapping corrections for the Extended Experiment. This is not pristine blind-validation evidence.

## Decision

Strict gate: **rejected**.
The original Phase 4.9 row remains **blocked and rejected with alternative**. The temperature criteria fail and four missing outdoor-CO2 input rows independently violate the predeclared no-missing-input rule.

## Runtime

| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |
|---|---:|---:|---:|---:|---:|
| Main hourly | 1056 | 18.325 | 57.626 | 0.017353 | 355.3 |
| Extended 10-minute | 4896 | 98.088 | 49.914 | 0.020034 | 355.3 |

The 72-hour 10-minute sample was run twice after warm-up: median 9.651 s, range 9.535-9.768 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.268 | 1.375 | 1.706 | 7.892 |
| Extended primary | 2.316 | 2.358 | 2.663 | 8.565 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.100 | 1.265 | 1.514 | 3.773 | 0.689 |
| ground_airbody | 2.555 | 2.555 | 2.688 | 4.342 | 0.789 |
| kitchen_airbody | 3.589 | 3.589 | 3.737 | 8.565 | 0.751 |
| sleeping_airbody | 2.022 | 2.024 | 2.208 | 4.259 | 0.545 |

### Error structure

Day pooled RMSE: 2.709 degC; night pooled RMSE: 2.615 degC. First scored week RMSE: 1.563 degC; last scored week RMSE: 3.491 degC.

Maximum absolute thermal-balance residual: 1.471e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The canonical adapter now couples the mass node through the full graph-derived opaque surface area instead of the incomplete floor-plus-interzone estimate. The coefficient itself remains the declared model constant; no residual-derived value was introduced.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) the single air-to-mass coefficient cannot represent layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest prior kitchen errors coincided with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, exposing items (1)-(3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocol 1.1 preserves the original protocol and documents this target-independent correction.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_physical_runtime_error.py
```

Implementation commit: `2947e1f816c366118970c7a2d0d7eb5af62ed457`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc, ?? data/validation/fixtures/annex71-twin-houses/physical-runtime-error-v2.json, ?? data/validation/fixtures/annex71-twin-houses/physical-runtime-error-v3.json, ?? docs/validation/results/annex71_physical_runtime_error_v2.md, ?? docs/validation/results/annex71_physical_runtime_error_v3.md`.
