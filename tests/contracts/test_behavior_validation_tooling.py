"""Verification tests for distribution-aware occupant-action metrics."""

import math

import pytest

from nexusep.validation_data.behavior import (
    conditional_event_rates,
    extract_binary_events,
    score_binary_probabilities,
    summarize_between_person_event_rates,
    summarize_binary_transitions,
    summarize_distribution,
)

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"


def test_event_frequency_start_time_and_duration_are_explicit() -> None:
    events = extract_binary_events(
        [0, 1, 1, 0, 1, 1, 1, 0], interval_minutes=10.0
    )
    assert [(event.start_time_minutes, event.duration_minutes) for event in events] == [
        (10.0, 20.0),
        (40.0, 30.0),
    ]


def test_probability_scores_use_pre_decision_probabilities() -> None:
    result = score_binary_probabilities([0.1, 0.8, 0.3, 0.9], [0, 1, 0, 1])
    assert result.brier_score == pytest.approx(0.0375)
    expected_log_loss = -sum(
        math.log(value) for value in (0.9, 0.8, 0.7, 0.9)
    ) / 4.0
    assert result.log_loss == pytest.approx(expected_log_loss)


def test_invalid_or_post_hoc_probability_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="equal length"):
        score_binary_probabilities([0.5], [0, 1])
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        score_binary_probabilities([1.1], [1])


def test_transition_probabilities_preserve_state_direction() -> None:
    result = summarize_binary_transitions([0, 0, 1, 1, 0])
    assert (result.off_to_off, result.off_to_on) == (1, 1)
    assert (result.on_to_on, result.on_to_off) == (1, 1)
    assert result.probability_on_given_off == 0.5
    assert result.probability_off_given_on == 0.5


def test_environmental_response_is_reported_by_named_condition() -> None:
    rates = conditional_event_rates(
        [0, 1, 1, 1], ["cool", "cool", "warm", "warm"]
    )
    assert [(item.condition, item.count, item.event_rate) for item in rates] == [
        ("cool", 2, 0.5),
        ("warm", 2, 1.0),
    ]


def test_between_person_variability_is_not_reduced_to_household_mean() -> None:
    result = summarize_between_person_event_rates(
        {"person-a": [0, 0, 0, 0], "person-b": [1, 1, 1, 1]}
    )
    assert result.count == 2
    assert result.mean == 0.5
    assert result.population_stddev == 0.5


def test_empty_distribution_has_explicit_missing_statistics() -> None:
    result = summarize_distribution([])
    assert result.count == 0
    assert result.mean is None
