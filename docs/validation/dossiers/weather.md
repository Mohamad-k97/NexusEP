# Weather validation dossier

Validation category: **verification**.

## Model version and commit

Model claim `WEATHER-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Registered official PVGIS and NASA POWER fixtures with source terms, retrieval metadata, and checksums. Satellite/reanalysis values are not ground truth.

## Scenario mapping

Field names, units, UTC/local alignment, interval semantics, missing values, and radiation-component consistency.

## Preprocessing

Strict source adapters normalize timestamps and units; energy-preserving resampling rules are shared across domains.

## Calibrated parameters

None.

## Untouched validation period

Not applicable to ingestion verification.

## Metrics and plots

Exact field/unit/time mapping assertions and radiation consistency checks; no empirical forecast-error plot is claimed.

## Residual analysis

Mapping deviations fail by field and timestamp rather than being averaged away.

## Limitations

NSRDB authenticated acquisition and forcing accuracy against ground stations remain open.

## Pass/fail decision

**Pass for registered ingestion fixtures; weather accuracy validation is open.**

## Reproducible command

`uv run pytest -q tests/contracts/test_official_weather_ingestion.py tests/contracts/test_validation_tooling.py`
