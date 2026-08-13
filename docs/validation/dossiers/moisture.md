# Moisture validation dossier

Validation category: **verification and comparative-validation status**.

## Model version and commit

Model claim `MOIST-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Analytical fixtures and public Annex 41 exercise descriptions; underlying common-exercise licensing is not assumed.

## Scenario mapping

Constant/pulsed sources, removal and decay, ventilation, outdoor steps, multizone exchange, and humidity-ratio/RH conversion at fixed temperature.

## Preprocessing

Pressure, temperature, dry-air mass, humidity ratio, and RH use explicit units and fixed-condition conversions.

## Calibrated parameters

None.

## Untouched validation period

Not applicable to analytical verification.

## Metrics and plots

Dry-air/water-vapour residuals, concentration error, non-negativity, and convergence; no empirical plot exists.

## Residual analysis

Storage, source, transport, and removal reconcile per timestep.

## Limitations

No latent thermal feedback, material buffering, condensation, or non-isothermal HAM claim.

## Pass/fail decision

**Pass for fixed-temperature well-mixed moisture verification; coupled HAM validation is blocked.**

## Reproducible command

`uv run pytest -q tests/unit/test_moisture_analytical.py`
