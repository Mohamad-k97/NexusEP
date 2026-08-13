# Airflow validation dossier

Validation category: **verification and comparative-validation status**.

## Model version and commit

Model claim `AIRFLOW-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Analytical fixtures are code-authored. Public NIST CONTAM documentation is registered; no matched CONTAM executable result is claimed.

## Scenario mapping

Supply/exhaust, reciprocal two-zone exchange, infiltration, ventilation, window state, zero wind, and contaminant transport.

## Preprocessing

Directed flow records preserve source/destination identity and reciprocal accounting.

## Calibrated parameters

None.

## Untouched validation period

Not applicable; future matched CONTAM cases must freeze configuration before execution.

## Metrics and plots

Mass residual, direction, non-negativity, reciprocity, and timestep convergence. No comparative plot exists.

## Residual analysis

Every flow is audited by source and destination at every timestep.

## Limitations

Pressure-network, buoyancy, and general wind-driven empirical claims remain blocked.

## Pass/fail decision

**Pass for prescribed-flow verification; matched CONTAM comparison is open.**

## Reproducible command

`uv run pytest -q tests/unit/test_airflow_analytical.py`
