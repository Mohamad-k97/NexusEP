"""
ABBEY execution engine.

Handles:
- multiple action chunks inside one timestep
- foreground actions
- background processes
- immediate system/person/location effects
- action-level power and energy accounting
"""

from typing import Any, Callable, Mapping, Tuple

from nexusep.abbey.actions.action import Action
from nexusep.abbey.actions.library import get_available_actions
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ActionState,
    ExecutionState,
    SimulationClock,
)


AbbeyConfig = Mapping[str, Any]

ChooseActionFn = Callable[
    [
        list[Action],
        PersonState,
        DwellingObservation,
        SystemState,
        ExecutionState,
        OccupantLocation,
        SimulationClock,
        AbbeyConfig,
    ],
    Action,
]


def apply_system_effects(
    systems: SystemState,
    effects: Mapping[str, Any],
    target_space_id: str,
) -> SystemState:
    if not effects:
        return systems

    return systems.set_space_controls(
        target_space_id,
        **dict(effects),
    )


def apply_person_effects(
    person: PersonState,
    effects: Mapping[str, Any],
) -> PersonState:
    updates = {}

    for field_name, value in effects.items():
        if hasattr(person, field_name):
            updates[field_name] = value

    return person.copy(**updates)


def apply_location_effects(
    location: OccupantLocation,
    effects: Mapping[str, Any],
) -> OccupantLocation:
    updates = {}

    # Mirror shared location-related effects.
    for field_name in ["is_home", "away_reason"]:
        if field_name in effects and hasattr(location, field_name):
            updates[field_name] = effects[field_name]

    return location.copy(**updates)


def resolve_action_space(
    action: Action,
    location: OccupantLocation,
    assignment: SpaceAssignment,
    observation: DwellingObservation,
) -> Tuple[str, str]:
    """
    Resolve action target role to actual space ID.

    Returns:
        target_space_role
        target_space_id
    """

    role = action.target_zone_role

    if role == "current":
        return location.current_space_role, location.current_space_id

    if role == "door":
        role = "entrance"

    available_space_ids = observation.available_space_ids()

    target_space_id = assignment.resolve(
        role=role,
        available_space_ids=available_space_ids,
    )

    return role, target_space_id

def should_turn_lights_off_on_exit(
    old_space_id: str,
    new_space_id: str,
    actor_id: str,
    location: OccupantLocation,
    other_locations: list = None,
) -> bool:
    """
    Returns True if the actor leaves a space and no other occupant remains there.

    For v0.2, other_locations is optional.
    If not provided, we assume single-occupant simulation.
    """

    if old_space_id == new_space_id:
        return False

    if not old_space_id or old_space_id == "outside":
        return False

    other_locations = other_locations or []

    for other in other_locations:
        if other.occupant_id == actor_id:
            continue

        if (
            other.is_home
            and other.current_space_id == old_space_id
        ):
            return False

    return True
def apply_space_exit_rules(
    systems: SystemState,
    old_space_id: str,
    new_space_id: str,
    actor_id: str,
    location: OccupantLocation,
    config: AbbeyConfig,
    other_locations: list = None,
) -> SystemState:
    """
    Apply automatic room-exit controls.

    Currently:
        - if the actor leaves a room and nobody else is there,
          turn off the lights in the old room.
    """

    rules = config.get("space_exit_rules", {})

    if not bool(rules.get("auto_turn_lights_off_when_empty", True)):
        return systems

    if should_turn_lights_off_on_exit(
        old_space_id=old_space_id,
        new_space_id=new_space_id,
        actor_id=actor_id,
        location=location,
        other_locations=other_locations,
    ):
        systems = systems.set_space_controls(
            old_space_id,
            lights_on=False,
        )

    return systems

def start_action(
    action: Action,
    person: PersonState,
    location: OccupantLocation,
    assignment: SpaceAssignment,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    config: AbbeyConfig,
    actor_id: str = "person_1",
    other_locations: list = None,
) -> tuple[PersonState, OccupantLocation, SystemState, ExecutionState, ActionState]:
    """
    Start an action.

    Immediate effects are applied at action start.
    Background processes go to background_processes.
    Everything else goes to foreground_actions.
    """

    action_state = action.to_state(actor_id=actor_id)

    old_space_id = location.current_space_id
    
    target_role, target_space_id = resolve_action_space(
        action=action,
        location=location,
        assignment=assignment,
        observation=observation,
    )
    
    systems = apply_space_exit_rules(
        systems=systems,
        old_space_id=old_space_id,
        new_space_id=target_space_id,
        actor_id=actor_id,
        location=location,
        config=config,
        other_locations=other_locations,
    )
    
    location = location.copy(
        current_space_id=target_space_id,
        current_space_role=target_role,
        minutes_since_last_space_change=0.0,
    )

    systems = apply_system_effects(
        systems=systems,
        effects=action.system_effects,
        target_space_id=target_space_id,
    )

    person = apply_person_effects(
        person=person,
        effects=action.person_effects,
    )

    location = apply_location_effects(
        location=location,
        effects=action.person_effects,
    )

    if action.name == "go_to_work":
        systems = apply_space_exit_rules(
            systems=systems,
            old_space_id=location.current_space_id,
            new_space_id="outside",
            actor_id=actor_id,
            location=location,
            config=config,
            other_locations=other_locations,
        )
        location = location.copy(
            is_home=False,
            current_space_id="outside",
            current_space_role="outside",
            away_reason="work",
        )
        person = person.copy(is_home=False, away_reason="work")

    if action.name == "return_home":
        idle_space_id = assignment.resolve(
            role="idle",
            available_space_ids=observation.available_space_ids(),
        )
        location = location.copy(
            is_home=True,
            current_space_id=idle_space_id,
            current_space_role="idle",
            away_reason="none",
        )
        person = person.copy(is_home=True, away_reason="none")

    if action.action_cooldowns_on_start:
        new_cooldowns = dict(execution.action_cooldowns)

        for action_name, cooldown_minutes in action.action_cooldowns_on_start.items():
            new_cooldowns[action_name] = max(
                new_cooldowns.get(action_name, 0.0),
                float(cooldown_minutes),
            )

        execution = execution.copy(action_cooldowns=new_cooldowns)

    if action.background_process:
        execution = execution.add_background_process(action_state)
        location = move_location_to_role(
            location=location,
            assignment=assignment,
            observation=observation,
            role=action.post_action_zone_role,
        )
        if action.name == "go_to_work":
            location = location.copy(
                is_home=False,
                current_space_id="outside",
                current_space_role="outside",
                away_reason="work",
            )
            person = person.copy(
                is_home=False,
                away_reason="work",
                is_sleeping=False,
            )
    else:
        execution = execution.add_foreground_action(action_state)

    execution = clean_execution_state(execution, person)

    return person, location, systems, execution, action_state


def advance_action_state(
    action_state: ActionState,
    minutes: float,
) -> ActionState:
    return action_state.advance(minutes)


def clean_execution_state(
    execution: ExecutionState,
    person: PersonState,
) -> ExecutionState:
    foreground = [
        action
        for action in execution.foreground_actions
        if action.is_active()
    ]

    background = []

    for process in execution.background_processes:
        if not process.is_active():
            continue

        if not person.is_home and not process.can_continue_without_actor:
            continue

        background.append(process)

    return execution.copy(
        foreground_actions=foreground,
        background_processes=background,
    )


def advance_execution_state(
    execution: ExecutionState,
    person: PersonState,
    location: OccupantLocation,
    assignment: SpaceAssignment,
    observation: DwellingObservation,
    systems: SystemState,
    config: AbbeyConfig,
    minutes: float,
) -> tuple[ExecutionState, OccupantLocation, SystemState]:
    if minutes < 0:
        raise ValueError("minutes must be non-negative.")

    new_foreground = []

    for action in execution.foreground_actions:
        advanced = action.advance(minutes)

        if advanced.is_active():
            new_foreground.append(advanced)
        else:
            old_space_id = location.current_space_id

            location = move_location_to_role(
                location=location,
                assignment=assignment,
                observation=observation,
                role=action.post_action_zone_role,
            )

            systems = apply_space_exit_rules(
                systems=systems,
                old_space_id=old_space_id,
                new_space_id=location.current_space_id,
                actor_id=action.actor_id,
                location=location,
                config=config,
            )

    new_background = []

    for process in execution.background_processes:
        advanced = process.advance(minutes)

        if advanced.is_active():
            new_background.append(advanced)

    new_cooldowns = {
    action_name: max(0.0, remaining_minutes - minutes)
    for action_name, remaining_minutes in execution.action_cooldowns.items()
    if max(0.0, remaining_minutes - minutes) > 0.0
    }
    
    new_execution = execution.copy(
        foreground_actions=new_foreground,
        background_processes=new_background,
        action_cooldowns=new_cooldowns,
    )

    new_execution = clean_execution_state(new_execution, person)

    return new_execution, location, systems

def next_actor_blocking_minutes(
    execution: ExecutionState,
    actor_id: str = "person_1",
) -> float:
    blocking = [
        action.remaining_minutes
        for action in execution.foreground_actions
        if action.actor_id == actor_id
        and action.blocks_actor
        and action.is_active()
    ]

    if not blocking:
        return 0.0

    return min(blocking)


def power_breakdown(
    execution: ExecutionState,
    minutes: float,
) -> list[dict[str, Any]]:
    rows = []

    for action in execution.foreground_actions:
        if action.is_active():
            rows.append(
                {
                    "name": action.name,
                    "category": action.category,
                    "execution_type": action.execution_type,
                    "actor_id": action.actor_id,
                    "minutes": minutes,
                    "power_w": action.power_w,
                    "energy_wh": action.power_w * minutes / 60.0,
                }
            )

    for process in execution.background_processes:
        if process.is_active():
            rows.append(
                {
                    "name": process.name,
                    "category": process.category,
                    "execution_type": process.execution_type,
                    "actor_id": process.actor_id,
                    "minutes": minutes,
                    "power_w": process.power_w,
                    "energy_wh": process.power_w * minutes / 60.0,
                }
            )

    return rows


def make_chunk_record(
    clock: SimulationClock,
    minutes: float,
    execution: ExecutionState,
    label: str,
) -> dict[str, Any]:
    breakdown = power_breakdown(
        execution=execution,
        minutes=minutes,
    )

    return {
        "step": clock.step,
        "day": clock.day,
        "hour": clock.hour,
        "chunk_label": label,
        "chunk_minutes": minutes,
        "total_power_w": sum(row["power_w"] for row in breakdown),
        "total_energy_wh": sum(row["energy_wh"] for row in breakdown),
        "power_breakdown": breakdown,
    }

def move_location_to_role(
    location: OccupantLocation,
    assignment: SpaceAssignment,
    observation: DwellingObservation,
    role: str,
) -> OccupantLocation:
    if role == "current":
        return location

    if role == "outside":
        return location.copy(
            is_home=False,
            current_space_id="outside",
            current_space_role="outside",
            away_reason=location.away_reason,
            minutes_since_last_space_change=0.0,
        )

    if role == "door":
        role = "entrance"

    available_space_ids = observation.available_space_ids()

    target_space_id = assignment.resolve(
        role=role,
        available_space_ids=available_space_ids,
    )

    return location.copy(
        is_home=True,
        current_space_id=target_space_id,
        current_space_role=role,
        away_reason="none" if role != "outside" else location.away_reason,
        minutes_since_last_space_change=0.0,
    )

def execute_timestep(
    person: PersonState,
    location: OccupantLocation,
    assignment: SpaceAssignment,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    clock: SimulationClock,
    config: AbbeyConfig,
    choose_action: ChooseActionFn,
    actor_id: str = "person_1",
) -> tuple[PersonState, OccupantLocation, SystemState, ExecutionState, list[dict[str, Any]]]:
    remaining_minutes = clock.dt_hours * 60.0
    chunk_records = []

    max_iterations = 100
    iteration = 0

    execution = clean_execution_state(execution, person)

    while remaining_minutes > 1e-9:
        iteration += 1

        if iteration > max_iterations:
            raise RuntimeError(
                "Execution loop exceeded max_iterations. "
                "Possible zero-duration or repeated background action loop."
            )

        blocking_minutes = next_actor_blocking_minutes(
            execution=execution,
            actor_id=actor_id,
        )

        if blocking_minutes > 0.0:
            chunk_minutes = min(remaining_minutes, blocking_minutes)

            chunk_records.append(
                make_chunk_record(
                    clock=clock,
                    minutes=chunk_minutes,
                    execution=execution,
                    label="continue_blocking_action",
                )
            )

            execution, location, systems = advance_execution_state(
                execution=execution,
                person=person,
                location=location,
                assignment=assignment,
                observation=observation,
                systems=systems,
                config=config,
                minutes=chunk_minutes,
            )

            remaining_minutes -= chunk_minutes
            continue

        available_actions = get_available_actions(
            person=person,
            systems=systems,
            execution=execution,
            location=location,
            clock=clock,
            config=config,
        )

        action = choose_action(
            available_actions,
            person,
            observation,
            systems,
            execution,
            location,
            clock,
            config,
        )

        person, location, systems, execution, started_action = start_action(
            action=action,
            person=person,
            location=location,
            assignment=assignment,
            observation=observation,
            systems=systems,
            execution=execution,
            config=config,
            actor_id=actor_id,
        )

        if started_action.background_process:
            continue

        chunk_minutes = min(
            remaining_minutes,
            max(1e-9, started_action.remaining_minutes),
        )

        chunk_records.append(
            make_chunk_record(
                clock=clock,
                minutes=chunk_minutes,
                execution=execution,
                label=started_action.name,
            )
        )

        execution, location, systems = advance_execution_state(
            execution=execution,
            person=person,
            location=location,
            assignment=assignment,
            observation=observation,
            systems=systems,
            config=config,
            minutes=chunk_minutes,
        )

        remaining_minutes -= chunk_minutes

    return person, location, systems, execution, chunk_records