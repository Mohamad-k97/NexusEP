"""
ABBEY action library.

Builds action blueprints from abbey_config.jsonc and filters available
actions from the current person/system/execution state.
"""

from typing import Any, Mapping, List, Dict

from nexusep.abbey.actions.action import Action
from nexusep.abbey.agents.states import (
    PersonState,
    SystemState,
    ActionState,
    ExecutionState,
    SimulationClock,
)
from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.agents.schedule import work_obligation_signal, work_day_finished, work_day_active

AbbeyConfig = Mapping[str, Any]


def build_action(name: str, config: AbbeyConfig) -> Action:
    """
    Build one Action object from the config.
    """

    if "actions" not in config:
        raise KeyError("Missing 'actions' section in ABBEY config.")

    if name not in config["actions"]:
        raise KeyError(f"Action '{name}' not found in ABBEY config.")

    cfg = config["actions"][name]
    
    return Action(
        name=name,
        category=str(cfg["category"]),
        execution_type=str(cfg["execution_type"]),
        duration_minutes=float(cfg["duration_minutes"]),
        power_w=float(cfg["power_w"]),
        activity_intensity=float(cfg["activity_intensity"]),
        effort=float(cfg["effort"]),
        requires_home=bool(cfg["requires_home"]),
        requires_awake=bool(cfg["requires_awake"]),
        blocks_actor=bool(cfg["blocks_actor"]),
        background_process=bool(cfg["background_process"]),
        can_continue_without_actor=bool(cfg["can_continue_without_actor"]),
        can_be_interrupted=bool(cfg["can_be_interrupted"]),
        can_fill_remaining_time=bool(cfg.get("can_fill_remaining_time", False)),
        can_repeat=bool(cfg.get("can_repeat", False)),
        system_effects=dict(cfg.get("system_effects", {})),
        person_effects=dict(cfg.get("person_effects", {})),
        action_cooldowns_on_start=dict(cfg.get("action_cooldowns_on_start", {})),
        target_zone_role=str(cfg.get("target_zone_role", "current")),
        post_action_zone_role=str(cfg.get("post_action_zone_role", "current")),
    )


def build_action_library(config: AbbeyConfig) -> Dict[str, Action]:
    """
    Build all actions from config, skipping metadata keys.
    """

    if "actions" not in config:
        raise KeyError("Missing 'actions' section in ABBEY config.")

    return {
        name: build_action(name, config)
        for name in config["actions"]
        if not name.startswith("_")
    }


def _is_noop_control(
    action: Action,
    systems: SystemState,
    location: OccupantLocation,
) -> bool:
    """
    Returns True if a control action would not change the current space state.
    """

    if not action.system_effects:
        return False

    controls = systems.get_space_controls(location.current_space_id)

    for field_name, target_value in action.system_effects.items():
        if not hasattr(controls, field_name):
            raise AttributeError(
                f"ZoneSystemState has no field '{field_name}', "
                f"but action '{action.name}' tries to set it."
            )

        current_value = getattr(controls, field_name)

        if current_value != target_value:
            return False

    return True

def _is_noop_person_effect(action: Action, person: PersonState) -> bool:
    """
    Returns True if a person-state action would not change the person state.

    Example:
        wake_up sets is_sleeping=False.
        If person.is_sleeping is already False, wake_up is useless.
    """

    if not action.person_effects:
        return False

    # Repeating actions like sleep can be valid even if person is already sleeping.
    if action.can_repeat:
        return False

    for field_name, target_value in action.person_effects.items():
        if not hasattr(person, field_name):
            raise AttributeError(
                f"PersonState has no field '{field_name}', "
                f"but action '{action.name}' tries to set it."
            )

        current_value = getattr(person, field_name)

        if current_value != target_value:
            return False

    return True

def _same_background_process_running(
    action: Action,
    active_background_processes: List[ActionState],
) -> bool:
    """
    Prevent starting the same background process twice.
    """

    if not action.background_process:
        return False

    return any(
        process.name == action.name and process.is_active()
        for process in active_background_processes
    )


def is_action_available(
    action: Action,
    person: PersonState,
    systems: SystemState,
    execution: ExecutionState,
    location: OccupantLocation,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> bool:
    
        # Forced work-return override.
    # If the occupant is outside because of work and the workday is finished,
    # return_home must be available even if normal filters would block it.
    if action.name == "return_home":
        if (
            not location.is_home
            and location.away_reason == "work"
            and work_day_finished(clock, config)
        ):
            return True

    if action.name == "go_to_work":
        if (
            person.has_job
            and location.is_home
            and not person.is_sleeping
            and work_day_active(person, clock, config)
        ):
            return True
    if execution.action_on_cooldown(action.name):
        return False

    if action.requires_home and not person.is_home:
        return False

    if action.requires_awake and person.is_sleeping:
        return False

    if _is_noop_control(action, systems, location):    
        return False

    if _is_noop_person_effect(action, person):
        return False

    if _same_background_process_running(
        action=action,
        active_background_processes=execution.background_processes,
    ):
        return False

    # Work absence rule:
    # If the person is away because of work, they cannot return home
    # while work obligation is still active.
    if action.name == "return_home":
        if person.away_reason == "work":
            # During work hours, block return_home.
            # After work_end_hour, return_home must be available.
            if not work_day_finished(clock, config):
                return False

    # Do not go to work if already away.
    if action.name == "go_to_work":
        if not person.is_home:
            return False

    return True


def get_available_actions(
    person: PersonState,
    systems: SystemState,
    execution: ExecutionState,
    location: OccupantLocation,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> List[Action]:
    action_library = build_action_library(config)

    available: List[Action] = []

    for action in action_library.values():
        if is_action_available(
            action=action,
            person=person,
            systems=systems,
            execution=execution,
            location=location,
            clock=clock,
            config=config,
        ):
            available.append(action)

    return available