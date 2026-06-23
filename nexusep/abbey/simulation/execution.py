"""
ABBEY execution engine.

Handles:
- multiple action chunks inside one timestep
- foreground actions
- background processes
- immediate system/person/location effects
- action-level power and energy accounting
"""

from typing import Any, Callable, Mapping, Tuple, Optional
from nexusep.abbey.systems import CooldownState
from nexusep.abbey.actions.action import Action
from nexusep.abbey.actions.proposal import ActionProposal
from nexusep.abbey.actions.library import get_available_actions, build_action
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ActionState,
    ExecutionState,
    SimulationClock,
)
from nexusep.abbey.household import apply_family_meal_effect
from nexusep.abbey.household.state import HouseholdState
from nexusep.abbey.household.care import apply_dependent_care_effect


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

def action_from_proposal(
    proposal: ActionProposal,
    config: AbbeyConfig,
) -> Action:
    """
    Build an Action object from an ActionProposal.
    """

    return build_action(
        name=proposal.action_name,
        config=config,
    )

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

def apply_v03_cooldowns_on_start(
    cooldowns: Optional[CooldownState],
    action: Action,
    actor_id: str,
    target_space_id: str,
) -> Optional[CooldownState]:
    """
    Apply v0.3 cooldowns when an action starts.

    For now:
        - action_cooldowns_on_start -> person-level cooldowns
        - cook/run_washing_machine -> household-level cooldowns
        - window/light/heating/curtain controls -> space-level cooldowns
    """

    if cooldowns is None:
        cooldowns = CooldownState()

    # Person-level action cooldowns.
    for action_name, cooldown_minutes in action.action_cooldowns_on_start.items():
        cooldowns = cooldowns.set_person_action_cooldown(
            occupant_id=actor_id,
            action_name=action_name,
            cooldown_minutes=float(cooldown_minutes),
        )

    # Household-level cooldowns.
    if action.name in {"cook", "run_washing_machine", "care_for_infant"}:
        for action_name, cooldown_minutes in action.action_cooldowns_on_start.items():
            cooldowns = cooldowns.set_household_action_cooldown(
                action_name=action_name,
                cooldown_minutes=float(cooldown_minutes),
            )
            
    # Space-control cooldowns.
    control_name = ""

    if action.name in {"open_window", "close_window"}:
        control_name = "window"

    if action.name in {"turn_lights_on", "turn_lights_off"}:
        control_name = "lights"

    if action.name in {"turn_heating_on", "turn_heating_off"}:
        control_name = "heating"

    if action.name in {"open_curtain", "close_curtain"}:
        control_name = "curtain"

    if control_name:
        control_cooldown_minutes = 20.0

        cooldowns = cooldowns.set_space_control_cooldown(
            space_id=target_space_id,
            control_name=control_name,
            cooldown_minutes=control_cooldown_minutes,
        )

    return cooldowns

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
    cooldowns: Optional[CooldownState] = None,
    other_locations: list = None,
) -> tuple[PersonState, OccupantLocation, SystemState, ExecutionState, Optional[CooldownState], ActionState]:
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
    action_state = action_state.copy(
        target_zone_role=target_role,
        target_space_id=target_space_id,
    )
    cooldowns = apply_v03_cooldowns_on_start(
        cooldowns=cooldowns,
        action=action,
        actor_id=actor_id,
        target_space_id=target_space_id,
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

    location = location.copy(
        current_space_id=target_space_id,
        current_space_role=target_role,
        current_activity=action.name,
        minutes_since_last_space_change=0.0,
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

    return person, location, systems, execution, cooldowns, action_state

def start_selected_proposals(
    selected_proposals: list[ActionProposal],
    people: dict[str, PersonState],
    locations: dict[str, OccupantLocation],
    assignments: dict[str, SpaceAssignment],
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    cooldowns: CooldownState,
    config: AbbeyConfig,
) -> tuple[
    dict[str, PersonState],
    dict[str, OccupantLocation],
    SystemState,
    ExecutionState,
    CooldownState,
    list[ActionState],
]:
    """
    Start selected household action proposals.

    This is the v0.3 multi-agent entry point.

    It does not yet solve all conflicts itself.
    It assumes household arbitration has already selected compatible proposals.
    """

    started_actions = []

    for proposal in selected_proposals:
        actor_id = proposal.actor_id

        if actor_id not in people:
            raise KeyError(f"Unknown actor_id in proposal: {actor_id}")

        if actor_id not in locations:
            raise KeyError(f"No location found for actor_id: {actor_id}")

        if actor_id not in assignments:
            raise KeyError(f"No space assignment found for actor_id: {actor_id}")
        
        if proposal.action_name in {"go_to_work", "go_to_school"}:
            
            def _interrupt_sleep_for_actor(
                execution: ExecutionState,
                actor_id: str,
            ) -> ExecutionState:
                """
                Remove active sleep action for one actor so scheduled external duties
                can force wake-up.
                """
            
                new_foreground = []
            
                for action in execution.foreground_actions:
                    if action.actor_id == actor_id and action.name == "sleep":
                        continue
            
                    new_foreground.append(action)
            
                return execution.copy(
                    foreground_actions=new_foreground,
                )
            
            execution = _interrupt_sleep_for_actor(
                execution=execution,
                actor_id=proposal.actor_id,
            )
        
            person = people[proposal.actor_id]
            people[proposal.actor_id] = person.copy(
                is_sleeping=False,
            )
        
            location = locations[proposal.actor_id]
            locations[proposal.actor_id] = location.copy(
                current_activity="idle",
            )
        action = action_from_proposal(
            proposal=proposal,
            config=config,
        )

        person = people[actor_id]
        location = locations[actor_id]
        assignment = assignments[actor_id]

        (
            person,
            location,
            systems,
            execution,
            cooldowns,
            action_state,
        ) = start_action(
            action=action,
            person=person,
            location=location,
            assignment=assignment,
            observation=observation,
            systems=systems,
            execution=execution,
            config=config,
            actor_id=actor_id,
            cooldowns=cooldowns,
            other_locations=[
                loc
                for oid, loc in locations.items()
                if oid != actor_id
            ],
        )

        people[actor_id] = person
        locations[actor_id] = location
        started_actions.append(action_state)

    return people, locations, systems, execution, cooldowns, started_actions

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

def advance_household_execution_state(
    people: dict[str, PersonState],
    locations: dict[str, OccupantLocation],
    assignments: dict[str, SpaceAssignment],
    household: HouseholdState,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    config: AbbeyConfig,
    minutes: float,
) -> tuple[
    dict[str, PersonState],
    dict[str, OccupantLocation],
    HouseholdState,
    SystemState,
    ExecutionState,
]:
    """
    Advance all active foreground/background actions in a multi-agent household.

    This is the v0.3 multi-agent version of advance_execution_state().
    It updates the location of the actor when their foreground action finishes.
    """

    if minutes < 0:
        raise ValueError("minutes must be non-negative.")

    new_foreground = []

    for action in execution.foreground_actions:
        advanced = action.advance(minutes)

        if advanced.is_active():
            new_foreground.append(advanced)
            continue

        actor_id = action.actor_id

        if actor_id not in locations:
            continue

        if actor_id not in assignments:
            continue

        old_location = locations[actor_id]
        old_space_id = old_location.current_space_id

        new_location = move_location_to_role(
            location=old_location,
            assignment=assignments[actor_id],
            observation=observation,
            role=action.post_action_zone_role,
        )
        post_role = action.post_action_zone_role
        
        if post_role == "current":
            post_activity = "idle"
        elif post_role == "idle":
            post_activity = "idle"
        elif post_role == "sleep":
            post_activity = "sleep"
        elif post_role == "outside":
            post_activity = "away"
        else:
            post_activity = post_role
        
        new_location = new_location.copy(
            current_activity=post_activity,
        )
        other_locations = [
            loc
            for oid, loc in locations.items()
            if oid != actor_id
        ]

        systems = apply_space_exit_rules(
            systems=systems,
            old_space_id=old_space_id,
            new_space_id=new_location.current_space_id,
            actor_id=actor_id,
            location=old_location,
            config=config,
            other_locations=other_locations,
        )
        
        if action.name == "cook":
            people, household = apply_family_meal_effect(
                people=people,
                locations=locations,
                household=household,
                cook_id=actor_id,
                config=config,
            )

        if action.name == "care_for_infant":
            people, household = apply_dependent_care_effect(
                people=people,
                locations=locations,
                household=household,
                caregiver_id=actor_id,
                config=config,
            )
            
    
        if action.name in {"go_to_work", "go_to_school"}:
            away_reason = "work"
        
            if action.name == "go_to_school":
                away_reason = "school"
        
            new_location = new_location.copy(
                is_home=False,
                current_space_id="outside",
                current_space_role="outside",
                current_activity=away_reason,
                away_reason=away_reason,
            )
        
            people[actor_id] = people[actor_id].copy(
                is_home=False,
                away_reason=away_reason,
                is_sleeping=False,
            )

        elif action.name == "return_home":
            idle_space_id = assignments[actor_id].resolve(
                role="idle",
                available_space_ids=observation.available_space_ids(),
            )

            new_location = new_location.copy(
                is_home=True,
                current_space_id=idle_space_id,
                current_space_role="idle",
                current_activity="idle",
                away_reason="none",
            )

            people[actor_id] = people[actor_id].copy(
                is_home=True,
                away_reason="none",
                is_sleeping=False,
            )

        locations[actor_id] = new_location

    new_background = []

    for process in execution.background_processes:
        advanced = process.advance(minutes)

        if not advanced.is_active():
            continue

        actor_location = locations.get(process.actor_id)

        if actor_location is None:
            new_background.append(advanced)
            continue

        if actor_location.is_home or process.can_continue_without_actor:
            new_background.append(advanced)

    new_action_cooldowns = {
        action_name: max(0.0, remaining - minutes)
        for action_name, remaining in execution.action_cooldowns.items()
        if max(0.0, remaining - minutes) > 0.0
    }
    
    new_execution = execution.copy(
        foreground_actions=new_foreground,
        background_processes=new_background,
        action_cooldowns=new_action_cooldowns,
    )

    return people, locations, household, systems, new_execution

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
    """
    Make power/energy log for the current execution state.

    Energy is capped by each action's remaining time.
    Example:
        15-min laptop inside 30-min chunk counts as 15 min, not 30 min.
    """

    power_breakdown = []
    total_energy_wh = 0.0

    for action in execution.foreground_actions:
        action_minutes = min(minutes, float(action.remaining_minutes))
        energy_wh = float(action.power_w) * action_minutes / 60.0

        power_breakdown.append(
            {
                "name": action.name,
                "category": action.category,
                "execution_type": action.execution_type,
                "actor_id": action.actor_id,
                "target_zone_role": action.target_zone_role,
                "target_space_id": action.target_space_id,
                "minutes": action_minutes,
                "power_w": float(action.power_w),
                "energy_wh": energy_wh,
            }
        )

        total_energy_wh += energy_wh

    for process in execution.background_processes:
        process_minutes = min(minutes, float(process.remaining_minutes))
        energy_wh = float(process.power_w) * process_minutes / 60.0

        power_breakdown.append(
            {
                "name": process.name,
                "category": process.category,
                "execution_type": process.execution_type,
                "actor_id": process.actor_id,
                "target_zone_role": process.target_zone_role,
                "target_space_id": process.target_space_id,
                "minutes": process_minutes,
                "power_w": float(process.power_w),
                "energy_wh": energy_wh,
            }
        )

        total_energy_wh += energy_wh

    total_power_w = 0.0

    if minutes > 0:
        total_power_w = total_energy_wh / (minutes / 60.0)

    return {
        "step": clock.step,
        "day": clock.day,
        "hour": clock.hour,
        "chunk_label": label,
        "chunk_minutes": minutes,
        "total_power_w": total_power_w,
        "total_energy_wh": total_energy_wh,
        "power_breakdown": power_breakdown,
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


def execute_household_timestep(
    people: dict[str, PersonState],
    locations: dict[str, OccupantLocation],
    assignments: dict[str, SpaceAssignment],
    household,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    cooldowns: CooldownState,
    clock: SimulationClock,
    config: AbbeyConfig,
    rng,
) -> tuple[
    dict[str, PersonState],
    dict[str, OccupantLocation],
    HouseholdState,
    SystemState,
    ExecutionState,
    CooldownState,
    list[dict[str, Any]],
]:
    """
    v0.3 household timestep.

    Pipeline:
        collect proposals
        arbitrate proposals
        start selected proposals
        record active power/energy
        advance active actions
    """

    from nexusep.abbey.household import (
        collect_household_action_proposals,
        arbitrate_household_actions,
    )

    if cooldowns is None:
        cooldowns = CooldownState()

    dt_minutes = clock.dt_hours * 60.0

    proposals = collect_household_action_proposals(
        people=people,
        locations=locations,
        assignments=assignments,
        household=household,
        observation=observation,
        systems=systems,
        execution=execution,
        clock=clock,
        config=config,
        cooldowns=cooldowns,
    )

    selected = arbitrate_household_actions(
        proposals=proposals,
        household=household,
        rng=rng,
    )

    if selected:
        (
            people,
            locations,
            systems,
            execution,
            cooldowns,
            started_actions,
        ) = start_selected_proposals(
            selected_proposals=selected,
            people=people,
            locations=locations,
            assignments=assignments,
            observation=observation,
            systems=systems,
            execution=execution,
            cooldowns=cooldowns,
            config=config,
        )

    chunk_records = [
        make_chunk_record(
            clock=clock,
            minutes=dt_minutes,
            execution=execution,
            label="household_execution",
        )
    ]

    (
        people,
        locations,
        household,
        systems,
        execution,
    ) = advance_household_execution_state(
        people=people,
        locations=locations,
        assignments=assignments,
        household=household,
        observation=observation,
        systems=systems,
        execution=execution,
        config=config,
        minutes=dt_minutes,
    )

    return people, locations, household, systems, execution, cooldowns, chunk_records

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
    cooldowns: Optional[CooldownState] = None,
) -> tuple[PersonState, OccupantLocation, SystemState, ExecutionState, Optional[CooldownState], list[dict[str, Any]]]:
    remaining_minutes = clock.dt_hours * 60.0
    chunk_records = []

    max_iterations = 100
    iteration = 0

    execution = clean_execution_state(execution, person)
    if cooldowns is None:
        cooldowns = CooldownState()
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
            cooldowns=cooldowns,
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

        person, location, systems, execution, cooldowns, started_action = start_action(
            action=action,
            person=person,
            location=location,
            assignment=assignment,
            observation=observation,
            systems=systems,
            execution=execution,
            config=config,
            actor_id=actor_id,
            cooldowns=cooldowns,
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

    return person, location, systems, execution, cooldowns, chunk_records