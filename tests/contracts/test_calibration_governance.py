"""Contract tests for Phase 4.27--4.31 calibration governance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nexusep.validation_data.governance import (
    AcceptanceCriteriaDocument,
    BlockedAlternativesDocument,
    CalibrationSplitDocument,
    UncertaintyBudgetDocument,
    load_governance_document,
)

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"
ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE = ROOT / "data" / "validation" / "governance"


def _load(name: str, model_type: type):
    return load_governance_document(GOVERNANCE / name, model_type)


def test_calibration_splits_keep_final_periods_sealed_and_disjoint() -> None:
    document = _load("calibration_splits_v1.json", CalibrationSplitDocument)
    segments = {(item.dataset_id, item.segment_id): item for item in document.segments}

    assert segments[("twin-houses", "experiment-1")].role == "calibration"
    assert segments[("twin-houses", "experiment-2")].role == "blind_validation"
    assert segments[("twin-houses", "experiment-2")].sealed is True
    assert segments[("nist-nzertf", "year-1")].role == "calibration"
    assert segments[("nist-nzertf", "year-2")].role == "validation"
    assert segments[("nist-nzertf", "year-2")].sealed is True
    assert segments[("atus", "held-out-years-or-demographics")].sealed is True


def test_unsealed_holdout_is_rejected() -> None:
    payload = json.loads((GOVERNANCE / "calibration_splits_v1.json").read_text())
    payload["segments"][1]["sealed"] = False
    with pytest.raises(ValidationError, match="must remain sealed"):
        CalibrationSplitDocument.model_validate(payload)


def test_acceptance_criteria_are_frozen_before_optimization() -> None:
    document = _load("acceptance_criteria_v1.json", AcceptanceCriteriaDocument)
    assert document.freeze_status == "frozen_before_fitting"
    assert document.optimization_started is False
    assert len(document.criteria) >= 8
    assert all(item.acceptable_error >= 0.0 for item in document.criteria)
    assert {item.decision_priority for item in document.criteria} >= {
        "bias",
        "dynamics",
        "distribution",
    }


def test_uncertainty_budget_names_every_required_component_once() -> None:
    document = _load("uncertainty_budget_v1.json", UncertaintyBudgetDocument)
    assert {item.name for item in document.components} == {
        "measurement",
        "weather_input",
        "parameter",
        "structural_model",
        "numerical",
        "stochastic_occupant",
    }


def test_every_blocked_phase4_gate_has_an_exact_alternative_outcome() -> None:
    document = _load("blocked_alternatives_v1.json", BlockedAlternativesDocument)
    assert {item.gate_id for item in document.evaluations} == {
        "controlled-thermal-blind",
        "nzertf-integrated",
        "occupant-distributions",
        "unseen-calibrated-parameters",
    }
    assert all(item.original_status == "blocked" for item in document.evaluations)
    assert {item.alternative_classification for item in document.evaluations} == {
        "blocked but passed with alternative",
        "blocked and rejected with alternative",
    }

    gate_report = (
        ROOT / "docs" / "validation" / "phase4_completion_gate.md"
    ).read_text(encoding="utf-8")
    blocked_rows = [
        line
        for line in gate_report.splitlines()
        if line.startswith("|") and "| **blocked** |" in line
    ]
    assert len(blocked_rows) == len(document.evaluations)
    classifications = {item.alternative_classification for item in document.evaluations}
    assert all(
        any(f"**{value}**" in row for value in classifications) for row in blocked_rows
    )


def test_executed_sensitivity_study_accepts_only_observable_parameters() -> None:
    artifact = json.loads(
        (
            ROOT
            / "artifacts"
            / "baseline"
            / "validation"
            / "thermal-rc-sensitivity-v1.json"
        ).read_text()
    )
    analysis = artifact["analysis"]
    decision = artifact["decision"]
    assert decision["calibration_problem_accepted"] is True
    assert analysis["identifiable"] is True
    assert analysis["effective_rank"] == len(analysis["parameter_order"])
    assert set(decision["calibrated_parameters"]) == set(
        analysis["observable_parameters"]
    )
    assert not decision["frozen_parameters"]
    assert not analysis["correlated_pairs"]
    assert set(artifact["uncertainty"]) == {
        "measurement",
        "weather_input",
        "parameter",
        "structural_model",
        "numerical",
        "stochastic_occupant",
    }


def test_each_domain_dossier_declares_category_and_required_sections() -> None:
    dossier_directory = ROOT / "docs" / "validation" / "dossiers"
    expected_domains = {
        "solar",
        "weather",
        "thermal",
        "airflow",
        "co2",
        "moisture",
        "hvac",
        "daylight",
        "occupants",
        "acoustics",
    }
    required_sections = {
        "## Model version and commit",
        "## Dataset and license",
        "## Scenario mapping",
        "## Preprocessing",
        "## Calibrated parameters",
        "## Untouched validation period",
        "## Metrics and plots",
        "## Residual analysis",
        "## Limitations",
        "## Pass/fail decision",
        "## Reproducible command",
    }
    reports = {
        path.stem: path.read_text(encoding="utf-8")
        for path in dossier_directory.glob("*.md")
        if path.name != "README.md"
    }
    assert set(reports) == expected_domains
    for domain, text in reports.items():
        assert "Validation category:" in text, domain
        assert required_sections <= {
            line.strip() for line in text.splitlines() if line.startswith("## ")
        }, domain
