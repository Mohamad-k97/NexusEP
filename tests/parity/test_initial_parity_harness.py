"""Phase 2.16 regression gates for measured, classified first parity.

Provenance: newly added scenario-level parity coverage for the frozen v1
contract. Unlike ``tests/conformance``, these tests intentionally compare
backend numerical results.
"""

from __future__ import annotations

import pytest

from nexusep.parity.harness import DEFAULT_TOLERANCES, run_initial_parity

CLASSIFICATIONS = {
    "exact_match",
    "tolerance_match",
    "expected_model_difference",
    "missing_feature",
    "defect",
    "contract_violation",
}


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return run_initial_parity()


def test_every_comparison_is_measured_and_classified(report) -> None:
    comparisons = report["comparisons"]
    assert comparisons
    assert {item["classification"] for item in comparisons} <= CLASSIFICATIONS
    for item in comparisons:
        assert item["rationale"]
        if (
            item["object_value"] is not None
            and item["array_value"] is not None
            and isinstance(item["object_value"], (int, float))
            and isinstance(item["array_value"], (int, float))
        ):
            assert item["absolute_difference"] is not None
            assert item["relative_difference"] is not None


def test_quantity_tolerances_and_cumulative_drift_are_separate(report) -> None:
    assert set(report["tolerances"]) == set(DEFAULT_TOLERANCES)
    assert DEFAULT_TOLERANCES["air_temperature_c"] != DEFAULT_TOLERANCES["co2_ppm"]
    comparisons = report["comparisons"]
    assert any(item["scope"] == "step_output" for item in comparisons)
    cumulative = [
        item for item in comparisons if item["scope"] == "cumulative_drift"
    ]
    assert cumulative
    assert all(
        item["tolerance"]
        == DEFAULT_TOLERANCES["cumulative_energy_wh"].to_dict()
        for item in cumulative
    )


def test_initial_graph_inputs_occupancy_and_repeat_runs_match(report) -> None:
    assert report["engine_versions"] == {
        "object": "2.17.0",
        "array": "2.17.0",
    }
    comparisons = report["comparisons"]
    required_exact_scopes = {
        "initial_state",
        "weather_mapping",
        "occupancy_mapping",
        "control_mapping",
        "determinism",
    }
    assert not any(
        item["classification"] in {"defect", "contract_violation"}
        and item["scope"] in required_exact_scopes
        for item in comparisons
    )
    assert all(
        item["classification"] == "exact_match"
        for item in comparisons
        if item["scope"] == "determinism"
    )


def test_known_deviations_remain_explicit_and_no_defect_is_hidden(report) -> None:
    counts = report["classification_counts"]
    assert counts == {
        "exact_match": 181,
        "expected_model_difference": 23,
        "tolerance_match": 4,
    }
    comparisons = report["comparisons"]
    assert not any(item["classification"] == "defect" for item in comparisons)
    assert not any(
        item["classification"] == "contract_violation" for item in comparisons
    )
    assert {
        item["quantity"]
        for item in comparisons
        if item["classification"] == "missing_feature"
    } == set()
