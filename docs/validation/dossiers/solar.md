# Solar validation dossier

Validation category: **verification**.

## Model version and commit

Model claim `SOLAR-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Official NREL SPA equations/reference vectors; provenance is indexed in the validation-data registry. No measured solar dataset is claimed.

## Scenario mapping

Solstices/equinoxes, leap day, both hemispheres, UTC offsets, DST, azimuth convention, sunrise/sunset, and night behavior.

## Preprocessing

Timezone-aware timestamps are normalized before reference comparison; no interpolation is used.

## Calibrated parameters

None.

## Untouched validation period

Not applicable to analytical verification.

## Metrics and plots

Azimuth and zenith absolute angular error against declared NREL reference cases. No plot is required for the pointwise analytical gate.

## Residual analysis

Reference residuals are checked by case and convention, not pooled into an energy metric.

## Limitations

This verifies solar position, not satellite irradiance or surface-gain accuracy.

## Pass/fail decision

**Pass for analytical solar-position verification; empirical solar validation remains outside this decision.**

## Reproducible command

`uv run pytest -q tests/contracts/test_solar_spa_reference.py`
