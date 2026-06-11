"""
ABBEY influence functions.

These functions compute upward/downward pressures for smooth state updates.
They do not directly update states.

All numerical parameters come from abbey_config.jsonc.
No behavioral magic numbers should be hardcoded here.
"""

import math
from typing import Any, Mapping, Tuple

from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    ActionState,
    SimulationClock,
)
from nexusep.abbey.agents.schedule import melatonin_signal, homeostatic_sleep_signal

Pressure = Tuple[float, float]
AbbeyConfig = Mapping[str, Any]


def _param(config: AbbeyConfig, section: str, key: str) -> float:
    """
    Read one numerical parameter from the ABBEY config.
    Raises a clear error if the value is missing.
    """
    try:
        return float(config[section][key])
    except KeyError as exc:
        raise KeyError(
            f"Missing ABBEY config parameter: [{section}][{key}]"
        ) from exc


def _is_action(action: ActionState, *names: str) -> bool:
    return action.name in names


def _night_pressure(hour: float) -> float:
    """
    Smooth night signal.
    1.0 around midnight, 0.0 around noon.
    """
    return 0.5 * (1.0 + math.cos(2.0 * math.pi * hour / 24.0))


def compute_hunger_pressures(
    person: PersonState,
    action: ActionState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Pressure:
    hunger_cfg = config["hunger"]

    up = float(hunger_cfg["base_up"])

    if person.is_sleeping:
        up *= float(hunger_cfg["sleep_multiplier"])

    up += float(hunger_cfg["fatigue_to_hunger_up"]) * person.fatigue

    down = 0.0

    if _is_action(action, "eat_simple"):
        down += float(hunger_cfg["eat_simple_down"])

    if _is_action(action, "cook"):
        down += float(hunger_cfg["cook_down"])
    
    if _is_action(action, "emergency_eat"):
        down += float(hunger_cfg["emergency_eat_down"])
    
    return up, down


def compute_fatigue_pressures(
    person: PersonState,
    observation: DwellingObservation,
    action: ActionState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Pressure:
    fatigue_cfg = config["fatigue"]

    up = float(fatigue_cfg["base_up"])

    if not person.is_sleeping:
        up += float(fatigue_cfg["awake_up"])

    up += float(fatigue_cfg["hunger_to_fatigue_up"]) * person.hunger
    up += float(fatigue_cfg["sickness_to_fatigue_up"]) * person.sickness_severity
    up += float(fatigue_cfg["thermal_discomfort_to_fatigue_up"]) * person.thermal_discomfort
    up += float(fatigue_cfg["air_quality_discomfort_to_fatigue_up"]) * person.air_quality_discomfort
    up += float(fatigue_cfg["acoustic_discomfort_to_fatigue_up"]) * person.acoustic_discomfort
    up += float(fatigue_cfg["activity_intensity_to_fatigue_up"]) * action.activity_intensity

    down = 0.0

    if person.is_sleeping or _is_action(action, "sleep"):
        down += float(fatigue_cfg["sleep_down"])

    if _is_action(action, "do_nothing"):
        down += float(fatigue_cfg["rest_down"])

    return up, down


def compute_sleep_pressures(
    person: PersonState,
    action: ActionState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Pressure:
    sleep_cfg = config["sleep_pressure"]

    night = _night_pressure(clock.hour)

    up = float(sleep_cfg["base_up"])
    up += float(sleep_cfg["fatigue_to_sleep_up"]) * person.fatigue
    up += float(sleep_cfg["night_to_sleep_up"]) * night
    up += float(sleep_cfg["sickness_to_sleep_up"]) * person.sickness_severity
    if not person.is_sleeping:
        up += (
            float(sleep_cfg["awake_duration_to_sleep_up"])
            * homeostatic_sleep_signal(person, config)
        )
    down = 0.0

    if _is_action(action, "sleep"):
        down += float(sleep_cfg["sleep_down"])

    if not person.is_sleeping and night < 0.25:
        down += float(sleep_cfg["daytime_awake_down"])

    return up, down


def compute_sickness_pressures(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Pressure:
    sickness_cfg = config["sickness"]

    up = float(sickness_cfg["spontaneous_up"])
    down = float(sickness_cfg["recovery_down"])

    return up, down


def compute_dirty_clothes_pressures(
    person: PersonState,
    action: ActionState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Pressure:
    dirty_cfg = config["dirty_clothes"]

    up = float(dirty_cfg["base_up"])

    if person.is_home:
        up += float(dirty_cfg["home_up"])

    up += float(dirty_cfg["sickness_to_dirty_clothes_up"]) * person.sickness_severity

    down = 0.0

    if _is_action(action, "run_washing_machine"):
        down += float(dirty_cfg["washing_machine_down"])

    return up, down


def compute_action_friction_pressures(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Pressure:
    friction_cfg = config["action_friction"]

    up = 0.0
    up += float(friction_cfg["fatigue_to_friction_up"]) * person.fatigue
    up += float(friction_cfg["sickness_to_friction_up"]) * person.sickness_severity
    up += float(friction_cfg["sleep_pressure_to_friction_up"]) * person.sleep_pressure

    down = float(friction_cfg["base_down"])

    if person.is_sleeping:
        down += float(friction_cfg["sleep_down"])

    return up, down