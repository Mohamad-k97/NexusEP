# Annex 71 four-air-body production diagnostic

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

This study replaces the old one-room helper calculation with a strict canonical scenario and the production object-engine adapter. It uses the four air bodies, measured heat/internal-gain inputs, measured ventilation flow and supply temperature, official weather, published windows, and deterministic graph IDs.

> This is a post-hoc production diagnostic, not a blind or untouched validation. The open Annex 71 targets have been inspected while correcting the mapper, and the original Annex 58 Experiment 2 archive remains unavailable.

## Frozen protocol

The protocol and thresholds were frozen in `data/validation/governance/annex71_production_transfer_v1.json` before production-adapter fitting. The independently published 107 W/K HTC is distributed with the coheat phase; only effective capacity is fitted in the first User-1 period. Thresholds are diagnostic and cannot create a validation pass because the later target period is no longer sealed.

Sensitivity gate: **pass**.

## Results

Calibration pooled RMSE: 2.003 degC; bias: 1.669 degC.

Later-period diagnostic pooled RMSE: 1.685 degC; bias: 1.162 degC.

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Correlation |
|---|---:|---:|---:|---:|
| attic_airbody | 0.667 | 1.070 | 1.549 | 0.511 |
| ground_airbody | 1.106 | 1.263 | 1.475 | 0.638 |
| kitchen_airbody | 1.556 | 1.629 | 1.854 | 0.769 |
| sleeping_airbody | 1.320 | 1.443 | 1.828 | 0.257 |

Thermal conservation residual: 1.824e-10 W.

Numerical diagnostic decision: **failed**.
Scientific gate decision: **rejected as validation evidence** because the later target period is not sealed.

## Scientific limits

- The measured electric heater's documented 70/30 convective/radiative split is represented explicitly by the typed control contract.
- The ground-floor west blind is not represented because canonical v1 has no per-opening blind state; this is a structural solar-gain limitation.
- Measured supply-air temperature enters the air node through the typed mechanical-ventilation heat path; it is not approximated as an internal gain.
- The result does not close the temporal-transfer or blind-validation gates.

## Reproduce

```text
uv run python scripts/validation_data/run_annex71_production_transfer.py
```
