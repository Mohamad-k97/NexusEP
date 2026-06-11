"""
ABBEY decision engine.

Deterministic v0.1 decision logic:
    score all available actions
    choose max score

Later:
    replace deterministic max with softmax/stochastic choice.
"""

from typing import Any, Mapping

from nexusep.abbey.actions.action import Action
from nexusep.abbey.agents.schedule import (
    sleep_drive,
    wake_drive,
    work_obligation_signal,
    melatonin_signal,
    work_day_active,
    work_day_finished,
)
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ExecutionState,
    SimulationClock,
)
from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.agents.schedule import homeostatic_sleep_signal

AbbeyConfig = Mapping[str, Any]


def _decision_cfg(config: AbbeyConfig) -> Mapping[str, Any]:
    return config["decision"]


def score_action(
    action: Action,
    person: PersonState,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    location: OccupantLocation,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> float:
    
    cfg = _decision_cfg(config)
    zone_controls = systems.get_space_controls(location.current_space_id)
    score = 0.0

    # ------------------------------------------------------------
    # Passive baseline
    # ------------------------------------------------------------
    if action.name == "do_nothing":
        score += float(cfg["do_nothing_bias"])

    # ------------------------------------------------------------
    # Hunger / food
    # ------------------------------------------------------------
    if action.name == "cook":
        score += float(cfg["hunger_food_weight"]) * person.hunger
    
        if person.hunger >= float(cfg["cook_hunger_threshold"]):
            score += float(cfg["cook_bonus_above_threshold"])
    
        # If too fatigued, cooking becomes less attractive.
        score -= 1.5 * max(0.0, person.fatigue - 0.65)
    
    if action.name == "emergency_eat":
        # This is fallback food. It should not dominate normal cooking.
        if person.hunger < 0.85:
            score -= 999.0
        else:
            score += 2.0 * person.hunger
            score += 1.5 * max(0.0, person.fatigue - 0.75)

    if action.name == "make_hot_drink":
        score += float(cfg["hot_drink_sickness_weight"]) * person.sickness_severity
        score += 0.25 * person.thermal_discomfort

    # ------------------------------------------------------------
    # Sleep / wake
    # ------------------------------------------------------------
    if action.name == "sleep":
        melatonin = melatonin_signal(clock, config)
    
        sleep_score = float(cfg["sleep_drive_weight"]) * sleep_drive(
            person=person,
            clock=clock,
            config=config,
        )
    
        sleep_score -= (
            float(cfg["sleep_work_obligation_penalty"])
            * work_obligation_signal(person, clock, config)
        )
        homeostatic = homeostatic_sleep_signal(person, config)
        sleep_score += 3.0 * homeostatic
    
        min_sleep = float(cfg["minimum_sleep_minutes_before_wake"])
        target_sleep = float(cfg["target_sleep_minutes"])
        max_sleep = float(cfg["maximum_sleep_minutes"])
    
        if person.is_sleeping:
            # Before minimum sleep duration, continuing sleep is strongly preferred.
            if person.minutes_asleep < min_sleep:
                sleep_score += float(cfg["sleep_continuation_before_min_bonus"])
    
            # After target sleep duration, continuing sleep becomes less attractive.
            if person.minutes_asleep > target_sleep:
                oversleep_hours = (person.minutes_asleep - target_sleep) / 60.0
                sleep_score -= float(cfg["oversleep_penalty_weight"]) * oversleep_hours
    
            # After maximum sleep duration, sleep should almost never continue.
            if person.minutes_asleep > max_sleep:
                sleep_score -= float(cfg["forced_wake_after_max_bonus"])
    
        else:
            # Starting sleep should be harder before biological night,
            # unless fatigue/sleep pressure are extreme.
            gate_strength = float(cfg["sleep_initiation_melatonin_gate"])
            sleep_score *= (1.0 - gate_strength) + gate_strength * melatonin
    
            early_sleep_end = float(cfg["early_sleep_end_hour"])
            is_early_evening = 17.0 <= (clock.hour % 24.0) < early_sleep_end
    
            extreme_need = (
                person.fatigue >= float(cfg["extreme_fatigue_for_early_sleep"])
                or person.sleep_pressure >= float(cfg["extreme_sleep_pressure_for_early_sleep"])
                or person.sickness_severity > 0.5
            )
    
            if is_early_evening and not extreme_need:
                sleep_score -= float(cfg["early_sleep_penalty"])
    
            if 8.0 <= (clock.hour % 24.0) <= 17.0:
                sleep_score -= float(cfg["sleep_daytime_penalty"])
    
            if person.fatigue < float(cfg["long_sleep_threshold_fatigue"]):
                sleep_score -= float(cfg["sleep_after_long_sleep_penalty"])
    
            if person.sleep_pressure < float(cfg["long_sleep_threshold_sleep_pressure"]):
                sleep_score -= float(cfg["sleep_after_long_sleep_penalty"])
    
        score += sleep_score

    if action.name == "wake_up":
        wake_score = float(cfg["wake_drive_weight"]) * wake_drive(
            person=person,
            clock=clock,
            config=config,
        )
    
        min_sleep = float(cfg["minimum_sleep_minutes_before_wake"])
        target_sleep = float(cfg["target_sleep_minutes"])
        max_sleep = float(cfg["maximum_sleep_minutes"])
    
        if person.is_sleeping:
            if person.minutes_asleep < min_sleep:
                wake_score -= 20.0
    
            if person.minutes_asleep > target_sleep:
                extra_hours = (person.minutes_asleep - target_sleep) / 60.0
                wake_score += float(cfg["wake_after_target_weight"]) * extra_hours
    
            if person.minutes_asleep > max_sleep:
                wake_score += float(cfg["forced_wake_after_max_bonus"])
    
        score += wake_score

    # ------------------------------------------------------------
    # Leaving / returning
    # ------------------------------------------------------------
    work_pressure = work_obligation_signal(
        person=person,
        clock=clock,
        config=config,
    )


        
    if action.name == "go_to_work":
        score += float(cfg["leave_work_weight"]) * work_pressure
        score -= float(cfg["sickness_leave_penalty"]) * person.sickness_severity
        score -= float(cfg["fatigue_leave_penalty"]) * person.fatigue

    if action.name == "return_home":
        score += float(cfg["return_home_weight"]) * (1.0 - work_pressure)
    
        if person.away_reason == "work":
            score += float(cfg.get("return_home_after_work_bonus", 50.0)) * max(
                0.0,
                1.0 - work_pressure,
            )
    
        score += 0.5 * person.fatigue
        score += 0.8 * person.sickness_severity
    # ------------------------------------------------------------
    # Thermal control
    # thermal_sensation < 0 means cold
    # thermal_sensation > 0 means warm
    # ------------------------------------------------------------
    cold_pressure = max(0.0, -person.thermal_sensation) * person.thermal_discomfort
    heat_pressure = max(0.0, person.thermal_sensation) * person.thermal_discomfort

    if action.name == "turn_heating_on":
        score += float(cfg["thermal_control_weight"]) * cold_pressure

    if action.name == "turn_heating_off":
        score += float(cfg["thermal_control_weight"]) * heat_pressure
        score += float(cfg["heating_off_hot_bonus"]) * heat_pressure
        score -= float(cfg["heating_off_penalty_when_cold"]) * cold_pressure

    if action.name == "turn_cooling_on":
        score += float(cfg["thermal_control_weight"]) * heat_pressure

    if action.name == "turn_cooling_off":
        score += float(cfg["thermal_control_weight"]) * cold_pressure
        score -= float(cfg["cooling_off_penalty_when_hot"]) * heat_pressure

    # ------------------------------------------------------------
    # Air quality / window
    # ------------------------------------------------------------
    if action.name == "open_window":
        score += float(cfg["air_quality_window_weight"]) * person.air_quality_discomfort
        score += float(cfg["thermal_control_weight"]) * heat_pressure
        score -= float(cfg["window_cold_penalty"]) * cold_pressure
        score -= float(cfg["window_noise_penalty"]) * person.acoustic_discomfort
    
        if zone_controls.heating_on:
            score -= float(cfg["open_window_while_heating_penalty"]) * (0.5 + heat_pressure)

    if action.name == "close_window":
        score += float(cfg["window_cold_penalty"]) * cold_pressure
        score += float(cfg["window_noise_penalty"]) * person.acoustic_discomfort
    
        if zone_controls.heating_on:
            score += float(cfg["close_window_while_heating_bonus"])

    # ------------------------------------------------------------
    # Daylight / lights / curtain
    # ------------------------------------------------------------
    if action.name == "turn_lights_on":
        score += float(cfg["visual_light_weight"]) * person.visual_discomfort

    if action.name == "turn_lights_off":
        score += float(cfg["visual_light_weight"]) * max(
            0.0,
            1.0 - person.visual_discomfort,
        )

    if action.name == "open_curtain":
        score += float(cfg["visual_curtain_weight"]) * person.visual_discomfort

    if action.name == "close_curtain":
        # v0.1: no glare state yet, so curtain closing is mainly weakly useful
        # when daylight is high and visual discomfort is low.
        score += float(cfg["visual_curtain_weight"]) * max(
            0.0,
            observation.indoor_daylight - 0.8,
        ) * max(0.0, 1.0 - person.visual_discomfort)

    # ------------------------------------------------------------
    # Laundry / tariff
    # ------------------------------------------------------------
    if action.name == "run_washing_machine":
        score += float(cfg["dirty_clothes_laundry_weight"]) * person.dirty_clothes

        tariff_reference = float(cfg["laundry_tariff_reference"])
        tariff_excess = max(
            0.0,
            observation.electricity_tariff - tariff_reference,
        )

        score -= (
            float(cfg["tariff_penalty_weight"])
            * person.money_sensitivity
            * tariff_excess
        )

    # ------------------------------------------------------------
    # Background process bonus
    # ------------------------------------------------------------
    if action.background_process:
        score += float(cfg["background_process_bonus"])

    # ------------------------------------------------------------
    # Effort/action-friction penalty
    # ------------------------------------------------------------
    score -= (
        float(cfg["effort_penalty_weight"])
        * action.effort
        * person.action_friction
    )

    return score


def choose_action(
    available_actions: list[Action],
    person: PersonState,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    location: OccupantLocation,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> Action:
    if not available_actions:
        raise ValueError("No available actions were provided to choose_action().")

    # HARD RULE 1:
    # If at home during work hours, go to work.
    if (
        person.has_job
        and location.is_home
        and not person.is_sleeping
        and work_day_active(person, clock, config)
    ):
        for action in available_actions:
            if action.name == "go_to_work":
                return action

        raise RuntimeError(
            "Person should go to work, but 'go_to_work' is not available. "
            f"Available actions: {[a.name for a in available_actions]}"
        )

    # HARD RULE 2:
    # If outside because of work and workday is finished, return home.
    if (
        not location.is_home
        and location.away_reason == "work"
        and work_day_finished(clock, config)
    ):
        for action in available_actions:
            if action.name == "return_home":
                return action

        raise RuntimeError(
            "Person should return from work, but 'return_home' is not available. "
            f"Available actions: {[a.name for a in available_actions]}"
        )

    scored = [
        (
            score_action(
                action=action,
                person=person,
                observation=observation,
                systems=systems,
                execution=execution,
                location=location,
                clock=clock,
                config=config,
            ),
            action,
        )
        for action in available_actions
    ]

    scored.sort(key=lambda item: item[0], reverse=True)

    return scored[0][1]