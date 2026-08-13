# Daylight validation dossier

Validation category: **verification and comparative-validation status**.

## Model version and commit

Model claim `DAYLIGHT-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Analytical fixtures only. CIE 171 and BRE-IDMP are candidate sources whose reusable case data/license must be confirmed before ingestion.

## Scenario mapping

No window, transmittance limits, overcast symmetry, direct shading, orientation, and lighting threshold/hysteresis.

## Preprocessing

Explicit irradiance/illuminance fields, orientation, opening area, transmittance, and shading are normalized before calculation.

## Calibrated parameters

None.

## Untouched validation period

Not applicable until measured daylight is registered.

## Metrics and plots

Algebraic equality, monotonic direction, transition timing, and lighting-energy effects; no empirical bias/RMSE plot exists.

## Residual analysis

Case-by-case deviations are retained rather than combined across unlike sky conditions.

## Limitations

No radiosity, glare, detailed sky vault, sensor optics, or ray tracing.

## Pass/fail decision

**Pass for elementary response verification; published and measured benchmark gates are open.**

## Reproducible command

`uv run pytest -q tests/unit/test_daylight_elementary_verification.py`
