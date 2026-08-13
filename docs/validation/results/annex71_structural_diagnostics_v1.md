# Annex 71 structural diagnostics

Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: iea-ebc-annex71-twin-houses-2020

Result role: post-hoc structural diagnosis without fitting

## Outcome

- Source timing shift supported: **False**.
- Alternative heater split materially supported: **False**.
- Initial mass-state uncertainty material: **False**.
- Floor-area capacity allocation supported: **False**.
- Counterfactual production mutation authorized: **false**.
- Source-determined 30-degree roof tilt applied: **true**.
- Validation status changed: **false**.

## Structural evidence

The official specification distinguishes walls, roof, floor, ceiling, windows, thermal bridges, cellar coupling, blinds, and a roof window. The current mapping preserves an allocated whole-building conductance but collapses opaque exterior components to one U-value. The dimensioned-plan 30-degree roof tilt is now mapped explicitly.

The internal heat sources use the same electric convectors as heating; the baseline 70/30 convective/radiative split is therefore source-supported.

## Diagnostic classifications

Source-timing supported candidates: `[]`.
Heater-split material candidates: `[]`.
Mass-state maximum relative span: `0.033`.
Floor-area allocation minimum required improvement: `0.100`; observed minimum: `-0.037`.

## Interpretation

Only findings that satisfy the predeclared cross-period 10% rule are called material. Negative candidates remain in the artifact. No candidate is a calibrated correction or validation pass.

## Reproduce

```text
uv run python scripts/validation_data/run_annex71_structural_diagnostics.py
```
