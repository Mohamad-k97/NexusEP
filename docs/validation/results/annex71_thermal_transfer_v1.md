# Annex 71 thermal-mapping diagnostic

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

## Result

The open IEA EBC Annex 71 main-experiment archive was checksum-verified and
reduced to 1,998 contiguous hourly N2 living-room records. The earlier
one-node 60/40 transfer has been retained as a forensic mapping diagnostic,
not as a validation of either production engine. Four helper-model parameters
were fitted using the first 60% and transferred to the final 40%.

| Segment | RMSE (degC) | Bias (degC) | MAE (degC) | Correlation |
|---|---:|---:|---:|---:|
| Calibration | 0.840 | -0.098 | 0.647 | 0.249 |
| Untouched chronological holdout | 3.601 | +2.816 | 2.943 | 0.275 |

The frozen holdout criteria were RMSE <= 1.0 degC and absolute bias <= 0.5
degC. Both fail. Effective capacity reached its upper bound and envelope
conductance reached its lower bound, also failing the one-percent parameter
margin gate.

The protocol audit also fails independently of those numerical results:

- the code under test is the single-node thermal-update helper, not either
  production adapter;
- the split is an arbitrary chronological 60/40 boundary, not the official
  blind/open workflow or official experimental periods;
- mean south solar forcing rises from 56.30 to 183.06 W/m2 across the split,
  a factor of 3.25;
- operated-opening observations rise from 22 hourly records in fitting to 489
  in holdout, but those openings are not mapped into the helper model;
- the full multizone topology, mass nodes and interzone exchange are absent.

Classification: **blocked and rejected with alternative**.

## Interpretation

The result rejects the mapping and protocol, not the production thermal
engine. It cannot be converted into a pass by changing tolerances. A new run
requires the official periods, the production object adapter, the complete N2
multizone topology, and explicit opening, solar, boundary and gain mappings.
User-2 remains unsupported until operated-window and interzone-airflow inputs
are represented.

## Scope and limitations

Only selected living-room temperature, heating/internal power, south solar,
outdoor temperature, ventilation, and opening-state audit channels are used.
Measurement uncertainty is not available in the scoring contract. This is
not an Annex 58 result, a production-engine result, or a validated
whole-building model.

## Reproduction

```powershell
uv run python scripts/validation_data/run_annex71_thermal_transfer.py
```
