# Annex 71 physical-model runtime and error report v3

Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with a post-unsealing, target-independent time correction for the Extended Experiment. This is not pristine blind-validation evidence.

## Decision

Strict gate: **rejected**. 
The original Phase 4.9 row remains **blocked and rejected with alternative**. The temperature criteria fail and four missing outdoor-CO2 input rows independently violate the predeclared no-missing-input rule.

## Runtime

| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |
|---|---:|---:|---:|---:|---:|
| Main hourly | 1056 | 14.233 | 74.191 | 0.013479 | 356.1 |
| Extended 10-minute | 4896 | 64.857 | 75.489 | 0.013247 | 356.1 |

The 72-hour 10-minute sample was run twice after warm-up: median 6.075 s, range 5.953-6.197 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.198 | 1.332 | 1.714 | 10.549 |
| Extended primary | 2.236 | 2.298 | 2.630 | 9.419 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.063 | 1.302 | 1.551 | 3.744 | 0.689 |
| ground_airbody | 2.487 | 2.487 | 2.642 | 4.578 | 0.803 |
| kitchen_airbody | 3.455 | 3.455 | 3.683 | 9.419 | 0.745 |
| sleeping_airbody | 1.940 | 1.948 | 2.172 | 5.883 | 0.568 |

### Error structure

Day pooled RMSE: 2.771 degC; night pooled RMSE: 2.482 degC. First scored week RMSE: 1.449 degC; last scored week RMSE: 3.495 degC.

Maximum absolute thermal-balance residual: 1.394e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) air-to-mass coupling uses a reduced effective-area coefficient rather than layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest kitchen errors coincide with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, directly exposing item (3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocol 1.1 preserves the original protocol and documents this target-independent correction.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_physical_runtime_error.py
```

Implementation commit: `50e48bc39f20fbb0e963726ed84251ec26672082`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc, ?? data/validation/fixtures/annex71-twin-houses/physical-runtime-error-v2.json, ?? docs/validation/results/annex71_physical_runtime_error_v2.md`.
