# Thermal validation dossier

Validation category: **verification and empirical-validation status**.

## Model version and commit

Model claim `THERMAL-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Closed-form RC cases are code-authored verification fixtures. The open IEA EBC Annex 71 Main Experiment archive is checksum-registered under CC BY-SA 4.0. Both the rejected historical helper and its four-air-body production replacement are retained. Neither is blind validation.

## Scenario mapping

One-/two-zone analytical cases plus the four official N2 air bodies, published topology and windows, measured heat/internal gains, mechanical ventilation flow/supply temperature, site weather, deterministic graph, and the object production adapter.

## Preprocessing

The Annex 71 hourly workbooks are joined exactly by Excel timestamp. A lag audit and the published experiment start support mapping each row to the preceding hour before conversion to canonical interval-start timestamps; this is a documented preprocessing choice rather than a claim that the workbook convention was independently proven. The published 107 W/K whole-house HTC is distributed across air bodies using low-solar near-steady coheat observations. Canonical `other` gains now reach the thermal bridge instead of being dropped.

## Calibrated parameters

Only whole-house effective capacity is fitted in the production diagnostic. It reaches 1.4955e8 J/K, only 0.31% below the frozen upper bound; the optimizer exhausts its evaluation budget. The published whole-house HTC remains 107 W/K.

## Untouched validation period

No untouched period is claimed. The later User-1 period was inspected while the mapper was repaired, so it is explicitly unsealed. The original Annex 58 Experiment 2 acquisition remains blocked.

## Metrics and plots

Analytical temperature error, energy residual, timestep convergence, sensitivity rank, and production-adapter temperature metrics are reported. Production calibration RMSE is 2.172 degC with +1.841 degC bias; the later-period diagnostic RMSE is 1.858 degC with +1.310 degC bias.

## Residual analysis

Closed-system residuals are checked near numerical precision. The production diagnostic conserves heat to 1.83e-10 W and uses no fallback, so the remaining temperature error is not a balance leak. Bound-seeking capacity and positive bias indicate structural/parameterization error.

## Limitations

The canonical contract still lacks the measured heater's 70/30 convective/radiative split, per-opening blind physics, supply-air temperature, detailed construction layers/bridges, cellar boundaries, and measurement uncertainty. Static effective interzone exchange is reduced-order and is not a pressure-network airflow claim.

## Pass/fail decision

**Pass for elementary RC verification and production mapping/conservation. The Annex 71 empirical alternative is rejected numerically and procedurally; blind and comparative fabric validation remain open.**

## Reproducible command

`uv run python scripts/validation_data/run_annex71_production_transfer.py` followed by `uv run pytest -q tests/unit/test_thermal_rc_analytical.py tests/integration/test_annex71_production_mapping.py tests/integration/test_phase4_blocked_alternatives.py`
