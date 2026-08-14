# Annex 71 boundary-contract runtime and error report v6

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with documented post-unsealing source-schedule, time, RC-mapping, airflow, topology, and radiative-boundary corrections for the Extended Experiment. This is not pristine blind-validation evidence.

## Decision

Strict gate: **rejected**.
The original Phase 4.9 row remains **blocked and rejected with alternative**. Failed frozen checks: pooled_rmse, pooled_bias, per_zone_rmse, no_missing_scored_inputs.

Post-run implementation finding: v6 did not fully execute protocol 1.5. The
canonical weather record contained the derived sky temperature, but the object
adapter's native `WeatherState` omitted that field. Consequently v6 applied
opaque shortwave absorption without the specified longwave sky exchange. This
report is retained as rejected evidence; the corrected handoff is frozen and
rerun separately rather than overwriting these results.

## Runtime

| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |
|---|---:|---:|---:|---:|---:|
| Main hourly | 1056 | 9.254 | 114.113 | 0.008763 | 357.8 |
| Extended 10-minute | 4896 | 33.927 | 144.312 | 0.006929 | 357.8 |

The 72-hour 10-minute sample was run twice after warm-up: median 4.239 s, range 3.925-4.552 s. Output hashes were identical.

Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.

## Temperature error

| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |
|---|---:|---:|---:|---:|
| Main post-hoc | 1.235 | 1.320 | 1.638 | 6.301 |
| Extended primary | 2.401 | 2.433 | 2.729 | 7.793 |

### Extended primary holdout by air body

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 1.393 | 1.515 | 1.787 | 4.191 | 0.682 |
| ground_airbody | 2.758 | 2.758 | 2.901 | 4.739 | 0.782 |
| kitchen_airbody | 3.565 | 3.565 | 3.712 | 7.793 | 0.741 |
| sleeping_airbody | 1.888 | 1.893 | 2.099 | 3.926 | 0.514 |

### Error structure

Day pooled RMSE: 2.778 degC; night pooled RMSE: 2.679 degC. First scored week RMSE: 1.510 degC; last scored week RMSE: 3.661 degC.

Maximum absolute thermal-balance residual: 1.826e-09 W. Fallback used: false.

## Model-error interpretation

The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.

The canonical adapter now couples the mass node through the full graph-derived opaque surface area instead of the incomplete floor-plus-interzone estimate. The coefficient itself remains the declared model constant; no residual-derived value was introduced.

The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) the single air-to-mass coefficient cannot represent layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest prior kitchen errors coincided with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, exposing items (1)-(3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.

## Source and data-quality findings

Extended archive SHA-256: `73183bda3bed2caa0e6099d6aa1c40edfed29e0e81678c29ab3ebea9722355e9` (53674589 bytes). The official source contains one conflicting duplicate row before the scored period and 4 primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.

The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocols 1.1 through 1.5 preserve every post-unsealing correction; protocol 1.5 freezes the target-independent topology, ventilation, and radiative-boundary corrections.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_boundary_runtime_error.py
```

Implementation commit: `f6ba15cc29aa5ed80cb40fd7b3475585a88dbbd3`; dirty paths at execution: `M nexusep/data/abbey/config/abbey_config.jsonc, ?? tmp/`.
