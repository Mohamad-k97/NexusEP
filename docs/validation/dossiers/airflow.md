# Airflow validation dossier

Validation category: **verification and comparative-validation status**.

## Model version and commit

Model claim `AIRFLOW-1`; exact source commit is recorded with each result.

## Dataset and license

Analytical fixtures are code-authored. Public NIST CONTAM documentation is registered; no matched CONTAM executable result is claimed.

## Scenario mapping

Supply/exhaust, reciprocal two-zone exchange, infiltration, ventilation,
window state, zero wind, contaminant transport, and vertical large-opening
buoyancy exchange.

## Preprocessing

Directed flow records preserve source/destination identity and reciprocal
accounting. Vertical large openings consume explicit area, height, discharge
coefficient, zone temperatures, and atmospheric pressure. They return equal
opposing mass flow using NIST TN 1887r1 equation 69.

## Calibrated parameters

None.

## Untouched validation period

Not applicable; future matched CONTAM cases must freeze configuration before execution.

## Metrics and plots

Mass residual, direction, non-negativity, reciprocity, and timestep convergence. No comparative plot exists.

## Residual analysis

Every flow is audited by source and destination at every timestep.

## Limitations

Whole-building pressure-network, pressure-driven infiltration, shifted neutral
planes, horizontal-opening correlations, and general wind-driven empirical
claims remain blocked. The Annex attic hatch therefore retains a visibly named
prescribed-velocity compatibility model rather than being mislabeled as a
verified vertical-opening calculation.

## Pass/fail decision

**Pass for prescribed-flow and two-opening analytical verification; matched
CONTAM pressure-network comparison is open.**

## Reproducible command

`uv run pytest -q tests/unit/test_airflow_analytical.py`
