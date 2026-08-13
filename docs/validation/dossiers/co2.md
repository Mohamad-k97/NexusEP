# CO2 validation dossier

Validation category: **verification and comparative-validation status**.

## Model version and commit

Model claim `CO2-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

NIST QICO2 equations/documentation and CONTAM documentation are registered references; no measurement series is used.

## Scenario mapping

Constant occupancy/ventilation, source and ventilation steps, decay, zero generation, and two-/three-zone exchange.

## Preprocessing

Concentration and dry-air volume inputs are normalized before coupled backward-Euler balance calculations.

## Calibrated parameters

None.

## Untouched validation period

Not applicable to analytical verification.

## Metrics and plots

Analytical concentration error and per-step generation/removal/exchange/storage residual; no empirical plot exists.

## Residual analysis

Whole-building and source-attribution residuals are retained per timestep.

## Limitations

Well-mixed zones omit stratification, sorption, reaction, and duct delay; matched CONTAM execution is pending.

## Pass/fail decision

**Pass for analytical well-mixed balances; executable comparative validation is open.**

## Reproducible command

`uv run pytest -q tests/unit/test_co2_single_zone_analytical.py`
