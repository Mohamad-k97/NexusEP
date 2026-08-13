# Thermal validation dossier

Validation category: **verification and empirical-validation status**.

## Model version and commit

Model claim `THERMAL-1`; component-resolved runtime/error implementation commit `2947e1f816c366118970c7a2d0d7eb5af62ed457`.

## Dataset and license

Closed-form RC cases are code-authored verification fixtures. The open IEA EBC Annex 71 Main, Extended, and supplementary-document archives are checksum-registered under CC BY-SA 4.0. The rejected historical helper, legacy four-air-body diagnostic, and current component-resolved diagnostic are retained. None is pristine blind validation.

## Scenario mapping

One-/two-zone analytical cases plus the four official N2 air bodies, published component U-values/capacities and thermal bridges, windows and 30-degree roof-window tilt, measured cellar/weather boundaries, heat/internal gains, opening/door schedules, mechanical ventilation flow/supply temperature, deterministic graph, and the object production adapter.

## Preprocessing

The Main hourly and Extended 10-minute workbooks are joined by source timestamp and interpreted as fixed CET (UTC+1), because the source retains the complete 02:00 hour at the spring civil-time transition. The current path uses plan/component properties rather than the historical fitted whole-house HTC. Canonical `other` gains reach the thermal bridge; measured mechanical supply temperature enters the air node; the documented heater split sends 70% to air and 30% to the mass node; and graph-derived opaque area couples the surface capacity represented by each zone mass node.

## Calibrated parameters

The current component-resolved v4 run fits no parameter. The historical legacy-effective diagnostic fits whole-house capacity and still reaches 1.4955e8 J/K near its frozen upper bound, so that calibration remains non-identifiable evidence rather than a solution.

## Untouched validation period

No untouched period is claimed. Extended targets were unsealed only after protocol v1 was frozen, but fixed-CET, blind-schedule, and RC-mapping repairs were required afterward. Protocols 1.1--1.3 preserve those amendments and prohibit a pristine blind claim.

## Metrics and plots

Analytical temperature error, energy residual, timestep convergence, sensitivity rank, production-adapter temperature metrics, runtime, repeatability, and profiler evidence are reported. The v4 Extended result has pooled RMSE 2.663 degC, bias +2.316 degC, MAE 2.358 degC, and maximum absolute error 8.565 degC. Its 4,896 modeled steps take 98.088 s (49.914 steps/s) on the recorded machine. The older observation-constrained path audit is diagnostic and is not an acceptance score.

## Residual analysis

Closed-system residuals are checked near numerical precision. V4 conserves heat to 1.471e-9 W, uses no fallback, and repeats with identical output hashes, so the remaining temperature error is not balance leakage or stochastic noise. The largest errors remain in the kitchen during roughly 1.8 kW heat pulses with the internal door open. Correcting the mass-coupling area reduces the maximum excursion but slightly worsens pooled RMSE, which points to the one-mass-node construction form and prescribed symmetric large-opening mixing rather than another defensible scalar adjustment.

## Limitations

The canonical object path represents heater split, supply-air temperature, per-opening state, component properties, thermal bridges, and the time-varying cellar boundary. It still collapses all construction layers in each air body into one mass state, uses a single air-to-mass transfer coefficient, uses generic closed-blind optics, applies the source whole-house infiltration estimate uniformly by zone, and models the large door with prescribed symmetric mixing rather than pressure/buoyancy exchange. Source uncertainty is registered but not propagated into weighted scores; mean radiant/mass temperature is unmeasured.

## Pass/fail decision

**Pass for elementary RC verification and production mapping/conservation. The Annex 71 empirical alternative is rejected numerically and procedurally; blind and comparative fabric validation remain open.**

## Reproducible command

`uv run python scripts/validation_data/run_annex71_physical_runtime_error.py`, followed by `uv run pytest -q tests/unit/test_thermal_rc_analytical.py tests/unit/test_thermal_energy_paths.py tests/integration/test_annex71_production_mapping.py tests/integration/test_phase4_blocked_alternatives.py`
