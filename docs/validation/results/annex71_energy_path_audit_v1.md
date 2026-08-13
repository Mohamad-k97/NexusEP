# Annex 71 thermal energy-path audit

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

Result role: diagnostic verification and empirical residual analysis

This audit runs the production object adapter but constrains each interval with the measured air temperature. The unmeasured mass node is advanced conditionally. The reported residual is therefore a diagnostic net heat flow, not a fitted correction or a validation score.

Positive unexplained gain means the model is missing heat; negative means the represented paths supply too much heat for the measured response.

## Results

Calibration one-step RMSE: 0.707 degC; unexplained-gain bias: -107.7 W.

Later-period one-step RMSE: 0.835 degC; unexplained-gain bias: -105.5 W; MAE: 302.7 W.

| Air body | One-step RMSE (degC) | Residual bias (W) | Residual MAE (W) | P05 (W) | P95 (W) |
|---|---:|---:|---:|---:|---:|
| attic_airbody | 0.992 | -164.8 | 541.1 | -1515.9 | 613.3 |
| ground_airbody | 0.658 | -94.8 | 440.6 | -1013.0 | 943.6 |
| kitchen_airbody | 0.858 | -122.2 | 142.9 | -395.9 | 84.5 |
| sleeping_airbody | 0.798 | -40.2 | 86.0 | -181.5 | 94.7 |

## Diagnosis

- Explicit ventilation supply temperature and heater radiant split improve the free-running later-period RMSE, but do not remove the rejection.
- The source-determined 30-degree roof tilt is now mapped. It changes the residual only slightly and does not remove the rejection.
- Frozen cross-period tests reject one-hour heating, internal-gain, and solar shifts; alternate heater splits; +/-2 degC initial mass states; and floor-area capacity allocation as material explanations.
- The remaining structural gaps are component-resolved fabric topology, the ground-floor cellar boundary, and per-opening blind state. A single fitted conductance or another aggregate correction is not justified.

No empirical correction factor is applied to production physics.

## Reproduce

```text
uv run python scripts/validation_data/run_annex71_energy_path_audit.py
```
