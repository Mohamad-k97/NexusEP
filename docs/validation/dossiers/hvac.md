# HVAC validation dossier

Validation category: **verification and comparative validation**.

## Model version and commit

Model claim `HVAC-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Code-authored analytical cases plus open EnergyPlus 25.1 software/input evidence, checksum-backed in the registry. No ASHRAE content or Standard 140 pass is claimed.

## Scenario mapping

Heating/cooling/deadband, availability, capacity, delay, mutual exclusion, Wh integration, and an original three-zone ideal-load comparison.

## Preprocessing

EnergyPlus CSV outputs are normalized to delivered power and hourly energy with explicit sign conventions.

## Calibrated parameters

None. NexusEP capacities are set to independently imposed steady reference loads for the narrow comparison.

## Untouched validation period

NZERTF Year 2 remains sealed for later integrated validation. Annex 71,
BOPTEST, and the narrow EnergyPlus fixture were assessed as alternatives but
rejected as non-equivalent integrated empirical evidence.

## Metrics and plots

Exact controller transitions and energy accounting; EnergyPlus delivered-power and Wh absolute differences under 0.001. No trace plot is needed for the constant-load fixture.

## Residual analysis

Opposite-mode and deadband loads are checked explicitly; part-load residuals are unsupported.

## Limitations

No COP curve, fan, duct, latent control, cycling, overload, or equipment-performance validation.

## Pass/fail decision

**Pass for ideal-control verification and the registered open ideal-load comparison. BESTEST equipment remains open; the integrated empirical gate is blocked and rejected with the assessed alternatives.**

## Reproducible command

`uv run pytest -q tests/unit/test_ideal_hvac_control.py tests/integration/test_energyplus_ideal_loads_comparison.py`
