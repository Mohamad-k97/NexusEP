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

Calibration pooled RMSE: 2.045 degC; bias: 1.736 degC.

Later-period diagnostic pooled RMSE: 1.710 degC; bias: 1.254 degC.

| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Correlation |
|---|---:|---:|---:|---:|
| attic_airbody | 0.743 | 1.103 | 1.571 | 0.459 |
| ground_airbody | 1.201 | 1.313 | 1.494 | 0.607 |
| kitchen_airbody | 1.658 | 1.699 | 1.870 | 0.704 |
| sleeping_airbody | 1.413 | 1.523 | 1.869 | 0.199 |

Thermal conservation residual: 1.807e-10 W.

Numerical diagnostic decision: **failed**.
Scientific gate decision: **rejected as validation evidence** because the later target period is not sealed.

## Scientific limits

- The measured electric heater's documented 70/30 convective/radiative split is represented explicitly by the typed control contract.
- The source-determined 30-degree attic roof-window tilt is represented explicitly.
- This historical legacy-effective diagnostic does not use the canonical per-opening blind controls; the component-resolved diagnostic does.
- This historical legacy-effective diagnostic still uses the common outdoor boundary instead of the supported measured cellar boundary; that substitution is not treated as valid.
- Its opaque fabric remains a conductance-preserving reduction rather than component-resolved wall, roof, ceiling, floor, and thermal-bridge topology.
- Measured supply-air temperature enters the air node through the typed mechanical-ventilation heat path; it is not approximated as an internal gain.
- The result does not close the temporal-transfer or blind-validation gates.

## Reproduce

```text
uv run python scripts/validation_data/run_annex71_production_transfer.py
```
