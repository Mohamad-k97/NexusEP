# Annex 71 physical-model runtime and error report v2

Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with a post-unsealing, target-independent time correction for the Extended Experiment. This is not pristine blind-validation evidence.

## Decision

Strict gate: **rejected**. 
The original Phase 4.9 row remains **blocked and rejected with alternative**. A thermal-only score is reported, but four missing outdoor-CO2 input rows violate the predeclared no-missing-input rule.

## Runtime

| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |
|---|---:|---:|---:|---:|---:|
| Main hourly | 1056 | 47.438 | 22.260 | 0.044923 | 355.8 |
| Extended 10-minute | 4896 | 188.809 | 25.931 | 0.038564 | 355.8 |

The 72-hour 10-minute sample was run twice after warm-up: median 18.907 s, range 18.854-18.959 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.244 | 1.371 | 1.763 | 10.578 |
| Extended primary | 2.391 | 2.448 | 2.793 | 9.725 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.173 | 1.392 | 1.654 | 3.929 | 0.684 |
| ground_airbody | 2.708 | 2.709 | 2.873 | 4.923 | 0.790 |
| kitchen_airbody | 3.641 | 3.641 | 3.875 | 9.725 | 0.740 |
| sleeping_airbody | 2.043 | 2.050 | 2.282 | 6.054 | 0.560 |

### Error structure

Day pooled RMSE: 2.938 degC; night pooled RMSE: 2.641 degC. First scored week RMSE: 1.509 degC; last scored week RMSE: 3.730 degC.

Maximum absolute thermal-balance residual: 1.413e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and phase-specific blinds are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) air-to-mass coupling uses a reduced effective-area coefficient rather than layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocol 1.1 preserves the original protocol and documents this target-independent correction.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_physical_runtime_error.py
```

Implementation commit: `1f7fa5d83726dbf1aa987132034692154162b697`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc`.
