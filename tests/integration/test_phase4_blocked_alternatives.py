"""Executable evidence checks for rejected Phase 4 blocked-gate alternatives."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
VALIDATION_CATEGORY = "empirical validation alternatives"
ROOT = Path(__file__).resolve().parents[2]


def _json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_annex71_chronological_holdout_is_rejected_without_retuning() -> None:
    result = _json(
        "data/validation/fixtures/annex71-twin-houses/thermal-transfer-result-v1.json"
    )
    study = result["study"]

    assert result["blocked_gate_classification"] == (
        "blocked and rejected with alternative"
    )
    assert study["fit_success"] is True
    assert study["predeclared_acceptance"] == {
        "rmse_c_less_than_or_equal_1_0": False,
        "absolute_bias_c_less_than_or_equal_0_5": False,
        "passed": False,
    }
    assert study["untouched_holdout"]["rmse_c"] > 1.0
    assert abs(study["untouched_holdout"]["bias_c"]) > 0.5
    assert study["parameter_bounds_gate_passed"] is False
    assert study["scientific_validation_gate_passed"] is False
    assert study["protocol_audit"]["classification"] == ("mapping_diagnostic_rejected")
    assert study["protocol_audit"]["production_object_adapter_exercised"] is False
    assert study["protocol_audit"]["official_blind_open_protocol_followed"] is False
    assert study["protocol_audit"]["unmapped_operated_openings_present"] is True
    assert study["forcing_shift_audit"]["holdout_to_calibration_solar_ratio"] > 3.0
    assert (
        study["forcing_shift_audit"]["holdout_operated_opening_hours"]
        > study["forcing_shift_audit"]["calibration_operated_opening_hours"]
    )
    assert study["calibration"]["count"] == 1197
    assert study["untouched_holdout"]["count"] == 800
    assert datetime.fromisoformat(
        study["calibration"]["end_timestamp_inclusive"]
    ) < datetime.fromisoformat(study["untouched_holdout"]["start_timestamp"])


def test_annex71_fixture_freezes_disjoint_split_roles() -> None:
    path = (
        ROOT / "data/validation/fixtures/annex71-twin-houses/"
        "n2-living-main-experiment-hourly.csv"
    )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    roles = [row["split_role"] for row in rows]
    first_holdout = roles.index("untouched_holdout")
    assert len(rows) == 1998
    assert set(roles[:first_holdout]) == {"calibration"}
    assert set(roles[first_holdout:]) == {"untouched_holdout"}
    assert first_holdout == int(len(rows) * 0.60)
    assert datetime.fromisoformat(rows[first_holdout - 1]["timestamp"]) < (
        datetime.fromisoformat(rows[first_holdout]["timestamp"])
    )
    assert {row["experimental_regime"] for row in rows} == {
        "fixed_openings_observed",
        "operated_openings_observed",
    }


def test_annex71_production_replacement_fixes_mapping_but_remains_rejected() -> None:
    result = _json(
        "data/validation/fixtures/annex71-twin-houses/"
        "production-transfer-result-v1.json"
    )
    study = result["study"]
    diagnostic = study["later_period_diagnostic"]
    decision = study["predeclared_acceptance"]

    assert study["engine"] == "object production adapter"
    assert set(study["coheat_envelope_allocation_w_k"]) == {
        "attic_airbody",
        "ground_airbody",
        "kitchen_airbody",
        "sleeping_airbody",
    }
    assert sum(study["coheat_envelope_allocation_w_k"].values()) == pytest.approx(107.0)
    assert study["sensitivity"]["identifiable"] is True
    assert diagnostic["fallback_used"] is False
    assert diagnostic["maximum_abs_thermal_balance_residual_w"] <= 1.0e-7
    assert diagnostic["metrics"]["pooled"]["rmse_c"] > 1.0
    assert abs(diagnostic["metrics"]["pooled"]["bias_c"]) > 0.5
    assert decision["numerical_criteria_passed"] is False
    assert decision["later_period_remained_sealed"] is False
    assert decision["passed"] is False


def test_annex71_energy_path_audit_does_not_authorize_post_hoc_tuning() -> None:
    result = _json(
        "data/validation/fixtures/annex71-twin-houses/energy-path-audit-v1.json"
    )
    later = result["audit"]["later_period"]["summary"]
    decision = result["decision"]

    assert decision["explicit_supply_air_path_verified"] is True
    assert decision["explicit_heater_split_verified"] is True
    assert decision["single_constant_missing_conductance_supported"] is False
    assert decision["additional_calibration_authorized"] is False
    assert decision["validation_status_changed"] is False
    assert later["whole_building"]["one_step_temperature_rmse_c"] < 1.0
    assert later["whole_building"]["unexplained_gain_mae_w"] > 0.0
    assert later["by_zone"]["attic_airbody"]["unexplained_air_node_gain"][
        "mae_w"
    ] > later["by_zone"]["sleeping_airbody"]["unexplained_air_node_gain"][
        "mae_w"
    ]


def test_atus_aggregate_alternative_fails_duration_and_distribution_gates() -> None:
    result = _json(
        "data/validation/fixtures/atus-aggregate/sleep-alternative-result-v1.json"
    )
    comparison = result["comparison"]

    assert result["blocked_gate_classification"] == (
        "blocked and rejected with alternative"
    )
    assert result["series"]["untouched_holdout_year"] == 2023
    assert result["series"]["holdout_average_sleep_hours_per_day"] == 9.07
    assert comparison["reference_minutes_per_day"] == pytest.approx(544.2)
    assert comparison["simulated_minutes_per_day"] == pytest.approx(450.0)
    assert comparison["absolute_duration_error_minutes"] == pytest.approx(94.2)
    assert comparison["predeclared_maximum_error_minutes"] == 30.0
    assert comparison["duration_gate_passed"] is False
    assert comparison["individual_distribution_available"] is False
    assert comparison["distribution_gate_passed"] is False
    assert comparison["passed"] is False
    model_output = result["nexusep"]["model_output"]
    assert result["nexusep"]["decision_target_sleep_minutes"] == 450.0
    assert model_output["engine"] == "object"
    assert model_output["median_complete_episode_minutes"] == 450.0
    assert model_output["episodes_ending_at_old_300_minute_discontinuity"] == 0


def test_atus_respondent_level_replacement_passes_frozen_distribution_gates() -> None:
    result = _json(
        "data/validation/fixtures/atus-2023-microdata/population-holdout-result-v1.json"
    )
    study = result["study"]
    metrics = study["metrics"]

    assert metrics["development_template_count"] == 6823
    assert metrics["holdout_respondent_count"] == 1725
    assert metrics["generated_population_size"] == 20_000
    assert metrics["daily_sleep_fraction"]["quantile_mae"] <= 0.05
    assert metrics["observed_location_home_fraction"]["quantile_mae"] <= 0.05
    assert metrics["sleep_episode_duration"]["quantile_mae_minutes"] <= 30.0
    assert metrics["determinism_check"] is True
    assert study["predeclared_acceptance"]["passed"] is True

    governance = _json("data/validation/governance/blocked_alternatives_v1.json")
    row = next(
        item
        for item in governance["evaluations"]
        if item["gate_id"] == "occupant-distributions"
    )
    assert row["alternative_classification"] == "blocked but passed with alternative"


def test_integrated_candidates_are_rejected_as_non_equivalent_evidence() -> None:
    governance = _json("data/validation/governance/blocked_alternatives_v1.json")
    row = next(
        item
        for item in governance["evaluations"]
        if item["gate_id"] == "nzertf-integrated"
    )
    assert row["original_status"] == "blocked"
    assert row["equivalent_claim"] is False
    assert row["execution_status"] == "rejected"
    assert row["alternative_classification"] == (
        "blocked and rejected with alternative"
    )

    energyplus = _json(
        "data/validation/fixtures/energyplus-ideal-loads-25.1.0/comparison.json"
    )
    annex71 = _json(
        "data/validation/fixtures/annex71-twin-houses/thermal-transfer-result-v1.json"
    )
    assert energyplus["passed"] is True
    assert annex71["study"]["predeclared_acceptance"]["passed"] is False
