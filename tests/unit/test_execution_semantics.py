"""Verification of foreground/background and actor-ownership semantics."""

from __future__ import annotations

import pytest

from nexusep.abbey.actions.proposal import ActionProposal
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import (
    ActionState,
    DwellingObservation,
    ExecutionState,
    PersonState,
    SystemState,
    ZoneObservation,
)
from nexusep.abbey.household.state import HouseholdState
from nexusep.abbey.simulation.execution import (
    advance_household_execution_state,
    start_selected_proposals,
)
from nexusep.abbey.systems import CooldownState
from nexusep.abbey.utils.config_loader import load_jsonc

pytestmark = pytest.mark.unit
VALIDATION_CATEGORY = "verification"


def _action(
    name: str,
    actor_id: str,
    *,
    minutes: float = 10.0,
    power_w: float = 0.0,
    blocking: bool = False,
    background: bool = False,
    continue_away: bool = True,
) -> ActionState:
    return ActionState(
        name=name,
        actor_id=actor_id,
        remaining_minutes=minutes,
        power_w=power_w,
        blocks_actor=blocking,
        background_process=background,
        can_continue_without_actor=continue_away,
    )


def test_actor_has_at_most_one_blocking_foreground_action() -> None:
    state = ExecutionState().add_foreground_action(
        _action("sleep", "resident_maria", blocking=True)
    )
    with pytest.raises(ValueError, match="already has a blocking"):
        state.add_foreground_action(
            _action("cook", "resident_maria", blocking=True)
        )
    other_actor = state.add_foreground_action(
        _action("read", "resident_zoe", blocking=True)
    )
    assert len(other_actor.foreground_actions) == 2


def test_background_processes_are_unique_and_power_is_concurrent() -> None:
    foreground = _action("cook", "resident_maria", power_w=100.0, blocking=True)
    washer = _action(
        "washing_machine",
        "resident_maria",
        power_w=600.0,
        background=True,
    )
    ventilation = _action(
        "extract_fan",
        "resident_zoe",
        power_w=40.0,
        background=True,
    )
    state = (
        ExecutionState()
        .add_foreground_action(foreground)
        .add_background_process(washer)
        .add_background_process(ventilation)
    )
    assert state.active_power_w() == 740.0
    with pytest.raises(ValueError, match="already running"):
        state.add_background_process(
            _action("washing_machine", "resident_zoe", background=True)
        )


def test_zero_duration_actions_are_not_enqueued() -> None:
    state = ExecutionState()
    assert state.add_foreground_action(_action("instant", "person", minutes=0.0)) == state
    assert state.add_background_process(
        _action("instant_bg", "person", minutes=0.0, background=True)
    ) == state


def test_background_process_pauses_away_and_advances_once_at_home() -> None:
    actor = "resident_maria"
    process = _action(
        "supervised_process",
        actor,
        minutes=20.0,
        background=True,
        continue_away=False,
    )
    execution = ExecutionState().add_background_process(process)
    people = {actor: PersonState(occupant_id=actor)}
    away = {
        actor: OccupantLocation(
            occupant_id=actor,
            is_home=False,
            current_space_id="outside",
        )
    }
    common = {
        "people": people,
        "assignments": {},
        "household": HouseholdState(occupant_ids=[actor]),
        "observation": DwellingObservation(),
        "systems": SystemState(),
        "config": {},
        "minutes": 5.0,
    }
    _, _, _, _, paused = advance_household_execution_state(
        locations=away,
        execution=execution,
        **common,
    )
    assert paused.background_processes[0].remaining_minutes == 20.0

    home = {
        actor: away[actor].copy(is_home=True, current_space_id="zone-kitchen-west")
    }
    _, _, _, _, advanced = advance_household_execution_state(
        locations=home,
        execution=paused,
        **common,
    )
    assert advanced.background_processes[0].remaining_minutes == 15.0


def test_selected_action_effects_are_actor_specific_and_keep_all_people() -> None:
    config = load_jsonc("nexusep/data/abbey/config/abbey_config.jsonc")
    people = {
        "resident_maria": PersonState(
            occupant_id="resident_maria", is_sleeping=False
        ),
        "resident_zoe": PersonState(occupant_id="resident_zoe", is_sleeping=False),
    }
    locations = {
        occupant_id: OccupantLocation(
            occupant_id=occupant_id,
            dwelling_id="home_north",
            building_id="building_alpha",
            current_space_id="zone-kitchen-west",
        )
        for occupant_id in people
    }
    assignments = {
        occupant_id: SpaceAssignment(
            occupant_id=occupant_id,
            dwelling_id="home_north",
            building_id="building_alpha",
            default_space_id="zone-kitchen-west",
            role_to_space_id={
                "idle": "zone-kitchen-west",
                "sleep": "zone-sleep-east",
            },
        )
        for occupant_id in people
    }
    observation = DwellingObservation(
        default_zone_id="zone-kitchen-west",
        zone_observations={
            zone_id: ZoneObservation(zone_id=zone_id, zone_name=zone_id)
            for zone_id in ("zone-kitchen-west", "zone-sleep-east")
        },
    )
    proposals = [
        ActionProposal(actor_id="resident_maria", action_name="sleep"),
        ActionProposal(actor_id="resident_zoe", action_name="use_laptop"),
    ]
    updated, updated_locations, _, execution, _, started = start_selected_proposals(
        selected_proposals=proposals,
        people=people,
        locations=locations,
        assignments=assignments,
        observation=observation,
        systems=SystemState(default_space_id="zone-kitchen-west"),
        execution=ExecutionState(),
        cooldowns=CooldownState(),
        config=config,
    )
    assert set(updated) == {"resident_maria", "resident_zoe"}
    assert updated["resident_maria"].is_sleeping is True
    assert updated["resident_zoe"].is_sleeping is False
    assert updated_locations["resident_maria"].current_space_id == "zone-sleep-east"
    assert {item.actor_id for item in started} == {
        "resident_maria",
        "resident_zoe",
    }
    assert {item.actor_id for item in execution.foreground_actions} == {
        "resident_maria",
        "resident_zoe",
    }
