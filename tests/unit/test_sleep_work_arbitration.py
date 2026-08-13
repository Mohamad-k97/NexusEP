"""Verification of continuous sleep scoring and schedule arbitration."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexusep.abbey.actions.action import Action
from nexusep.abbey.agents.decision import choose_action, score_action
from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.agents.states import (
    DwellingObservation,
    ExecutionState,
    PersonState,
    SimulationClock,
    SystemState,
)
from nexusep.abbey.utils.config_loader import load_jsonc

pytestmark = pytest.mark.unit
VALIDATION_CATEGORY = "verification"
ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_jsonc(
    ROOT / "nexusep/data/abbey/config/abbey_config.jsonc"
)


def _action(name: str) -> Action:
    return Action(name=name)


def _score(name: str, person: PersonState, hour: float = 2.0) -> float:
    return score_action(
        action=_action(name),
        person=person,
        observation=DwellingObservation(),
        systems=SystemState(),
        execution=ExecutionState(),
        location=OccupantLocation(
            occupant_id=person.occupant_id,
            is_home=True,
            current_space_id="main_room",
        ),
        clock=SimulationClock(hour=hour),
        config=CONFIG,
    )


def test_sleep_scores_are_continuous_at_minimum_duration() -> None:
    before = PersonState(
        is_sleeping=True,
        minutes_asleep=300.0 - 1.0e-6,
        fatigue=0.4,
        sleep_pressure=0.4,
    )
    after = before.copy(minutes_asleep=300.0 + 1.0e-6)

    assert _score("sleep", after) == pytest.approx(
        _score("sleep", before), abs=1.0e-6
    )
    assert _score("wake_up", after) == pytest.approx(
        _score("wake_up", before), abs=1.0e-6
    )


def test_sleep_protection_tapers_to_target_instead_of_ending_at_minimum() -> None:
    at_minimum = PersonState(
        is_sleeping=True,
        minutes_asleep=300.0,
        fatigue=0.4,
        sleep_pressure=0.4,
    )
    midway = at_minimum.copy(minutes_asleep=375.0)
    at_target = at_minimum.copy(minutes_asleep=450.0)

    continuation_bonus = float(
        CONFIG["decision"]["sleep_continuation_before_min_bonus"]
    )
    wake_penalty = float(
        CONFIG["decision"].get("wake_before_target_penalty", 20.0)
    )
    assert _score("sleep", at_minimum) - _score(
        "sleep", at_target
    ) == pytest.approx(continuation_bonus)
    assert _score("sleep", midway) - _score(
        "sleep", at_target
    ) == pytest.approx(continuation_bonus / 2.0)
    assert _score("wake_up", at_target) - _score(
        "wake_up", at_minimum
    ) == pytest.approx(wake_penalty)


def test_work_obligation_wakes_sleeping_occupant_before_departure() -> None:
    person = PersonState(
        has_job=True,
        is_sleeping=True,
        minutes_asleep=420.0,
    )
    selected = choose_action(
        available_actions=[_action("sleep"), _action("wake_up"), _action("go_to_work")],
        person=person,
        observation=DwellingObservation(),
        systems=SystemState(),
        execution=ExecutionState(),
        location=OccupantLocation(
            occupant_id=person.occupant_id,
            is_home=True,
            current_space_id="main_room",
        ),
        clock=SimulationClock(hour=9.0),
        config=CONFIG,
    )

    assert selected.name == "wake_up"


def test_new_sleep_is_suppressed_immediately_before_work() -> None:
    worker = PersonState(
        has_job=True,
        is_sleeping=False,
        fatigue=0.95,
        sleep_pressure=0.95,
    )
    same_person_without_job = worker.copy(has_job=False)

    assert _score("sleep", worker, hour=8.0) < _score(
        "sleep", same_person_without_job, hour=8.0
    ) - 10.0


def test_maximum_sleep_duration_forces_wake() -> None:
    person = PersonState(
        is_sleeping=True,
        minutes_asleep=540.0,
        fatigue=0.9,
        sleep_pressure=0.9,
    )

    assert _score("wake_up", person) > _score("sleep", person)
