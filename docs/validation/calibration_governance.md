# Calibration, holdout, acceptance, and uncertainty governance

Validation category: **calibration and blind-validation planning; no fitted
or holdout result claimed**.

Phases covered: **4.28--4.30**.

## Frozen splits

The machine-validated split manifest is
[`calibration_splits_v1.json`](../../data/validation/governance/calibration_splits_v1.json).
Twin Houses Experiment 1 and NZERTF Year 1 are calibration segments. Twin
Houses Experiment 2 is sealed blind validation. NZERTF Year 2 is sealed
validation and its documented dehumidifier, ventilation, and thermostat
changes must be represented as known inputs rather than fitted away. ATUS
development groups fit population priors; different years or demographic
groups remain sealed holdouts and must be named before microdata are opened.

Final-period values may not influence model selection, parameter bounds,
preprocessing, objective weights, stopping rules, or acceptance thresholds.

## Acceptance before fitting

[`acceptance_criteria_v1.json`](../../data/validation/governance/acceptance_criteria_v1.json)
freezes metric, resolution, warm-up, uncertainty treatment, threshold,
severity, and whether bias, dynamics, or distributions control each decision.
It records `optimization_started: false`. If source uncertainty later makes a
criterion inappropriate, a replacement protocol must be published before
fitting; this version may not be edited after holdout performance is seen.

The criteria are pre-fit research decisions, not evidence that the thresholds
have been achieved. Dataset acquisition, variable mapping, and measurement
uncertainty remain blocking prerequisites.

## Uncertainty budget

[`uncertainty_budget_v1.json`](../../data/validation/governance/uncertainty_budget_v1.json)
requires measurement, weather/input, parameter, structural-model, numerical,
and stochastic-occupant uncertainty to be reported separately. The Phase 4.27
fixture quantifies only parameter and timestep uncertainty. Reports must call
such an interval a partial or parameter-only interval; a total prediction
interval requires joint propagation of every applicable component.

## Enforcement

Strict Pydantic models reject unknown fields, overlapping dated segments,
unsealed holdouts, duplicate criteria, and incomplete uncertainty budgets.

```powershell
uv run pytest -q tests/contracts/test_calibration_governance.py
```
