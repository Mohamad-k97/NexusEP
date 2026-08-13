"""
ABBEY decision engine.

Deterministic v0.1 decision logic:
    score all available actions
    choose max score

Later:
    replace deterministic max with softmax/stochastic choice.
"""

from collections.abc import Mapping
from typing import Any

from nexusep.abbey.actions.action import Action
from nexusep.abbey.actions.proposal import ActionProposal
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.schedule import (
    homeostatic_sleep_signal,
    melatonin_signal,
    planned_leave_soon,
    sleep_drive,
    wake_drive,
    work_day_active,
    work_day_finished,
    work_obligation_signal,
)
from nexusep.abbey.agents.states import (
    DwellingObservation,
    ExecutionState,
    PersonState,
    SimulationClock,
    SystemState,
)

AbbeyConfig = Mapping[str, Any]


def _decision_cfg(config: AbbeyConfig) -> Mapping[str, Any]:
    return config["decision"]


def _sleep_target_protection(
    minutes_asleep: float,
    minimum_minutes: float,
    target_minutes: float,
) -> float:
    """Return a continuous sleep-protection factor in ``[0, 1]``.

    Protection is complete through the configured minimum sleep duration and
    then tapers linearly to zero at the target.  The previous implementation
    removed the entire continuation bonus and wake penalty at the minimum,
    which made otherwise healthy episodes terminate at exactly five hours.
    """

    if target_minutes <= minimum_minutes:
        return 1.0 if minutes_asleep < minimum_minutes else 0.0
    if minutes_asleep <= minimum_minutes:
        return 1.0
    if minutes_asleep >= target_minutes:
        return 0.0
    return (target_minutes - minutes_asleep) / (
        target_minutes - minimum_minutes
    )


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

    try:
        current_zone = observation.get_zone(location.current_space_id)
    except Exception:
        current_zone = None

    current_temp_c = 20.0
    current_co2_ppm = 420.0

    if current_zone is not None:
        current_temp_c = getattr(current_zone, "indoor_temp", None)

        if current_temp_c is None:
            current_temp_c = getattr(current_zone, "indoor_temp_c", 20.0)

        current_temp_c = float(current_temp_c)
        current_co2_ppm = float(getattr(current_zone, "co2_ppm", 420.0))

    heating_on = bool(getattr(zone_controls, "heating_on", False))
    window_open = bool(getattr(zone_controls, "window_open", False))

    if current_zone is not None:
        heating_on = bool(
            heating_on
            or getattr(current_zone, "heating_on", False)
        )

        window_open = bool(
            window_open
            or getattr(current_zone, "window_open", False)
        )

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
        hour = clock.hour % 24.0
    
        in_hot_drink_window = (
            6.5 <= hour <= 10.0
            or 15.0 <= hour <= 17.5
            or 20.0 <= hour <= 22.0
        )
    
        if not in_hot_drink_window and person.sickness_severity < 0.4:
            score -= 999.0
        else:
            score += 0.35
            score += float(cfg["hot_drink_sickness_weight"]) * person.sickness_severity
    
            # Very weak comfort effect only. Do not let thermal discomfort create endless tea.
            score += 0.03 * person.thermal_discomfort
    
        # Do not make hot drinks while very hungry; food should dominate.
        if person.hunger > 0.65:
            score -= 1.0
    
        # Do not make hot drinks while exhausted; sleep/rest should dominate.
        if person.fatigue > 0.75 or person.sleep_pressure > 0.85:
            score -= 1.0

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
            protection = _sleep_target_protection(
                person.minutes_asleep,
                min_sleep,
                target_sleep,
            )
            sleep_score += (
                float(cfg["sleep_continuation_before_min_bonus"])
                * protection
            )
    
            # After target sleep duration, continuing sleep becomes less attractive.
            if person.minutes_asleep > target_sleep:
                oversleep_hours = (person.minutes_asleep - target_sleep) / 60.0
                sleep_score -= float(cfg["oversleep_penalty_weight"]) * oversleep_hours
    
            # After maximum sleep duration, sleep should almost never continue.
            if person.minutes_asleep >= max_sleep:
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

            # A scheduled departure is an external obligation, not merely a
            # weak biological preference.  Prevent a new ordinary sleep
            # episode from starting immediately before work; sickness remains
            # an explicit exception.
            if person.sickness_severity <= 0.5:
                leave_signal = planned_leave_soon(
                    person=person,
                    clock=clock,
                    config=config,
                    horizon_hours=float(
                        cfg.get("pre_work_sleep_horizon_hours", 1.5)
                    ),
                )
                sleep_score -= float(
                    cfg.get("pre_work_sleep_penalty", 50.0)
                ) * leave_signal
    
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
            protection = _sleep_target_protection(
                person.minutes_asleep,
                min_sleep,
                target_sleep,
            )
            wake_score -= float(
                cfg.get("wake_before_target_penalty", 20.0)
            ) * protection
            emergency_hot_temp_c = float(
                cfg.get("emergency_wake_hot_temp_c", 28.0)
            )

            emergency_cold_temp_c = float(
                cfg.get("emergency_wake_cold_temp_c", 15.0)
            )

            emergency_co2_ppm = float(
                cfg.get("emergency_wake_co2_ppm", 1800.0)
            )

            if current_temp_c > emergency_hot_temp_c:
                wake_score += float(
                    cfg.get("emergency_wake_thermal_bonus", 80.0)
                )
                wake_score += 5.0 * (current_temp_c - emergency_hot_temp_c)

            if current_temp_c < emergency_cold_temp_c:
                wake_score += float(
                    cfg.get("emergency_wake_thermal_bonus", 80.0)
                )
                wake_score += 5.0 * (emergency_cold_temp_c - current_temp_c)

            if current_co2_ppm > emergency_co2_ppm:
                wake_score += float(
                    cfg.get("emergency_wake_air_quality_bonus", 50.0)
                )    
            if person.minutes_asleep > target_sleep:
                extra_hours = (person.minutes_asleep - target_sleep) / 60.0
                wake_score += float(cfg["wake_after_target_weight"]) * extra_hours
    
            if person.minutes_asleep >= max_sleep:
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

        # If the room is cold but the window is open, the realistic first
        # action is usually close_window, not heat harder.
        if window_open:
            high_co2_ppm = float(
                cfg.get("keep_window_open_high_co2_ppm", 1200.0)
            )

            co2_pressure = 0.0

            if current_co2_ppm > high_co2_ppm:
                co2_pressure = min(
                    1.0,
                    (current_co2_ppm - high_co2_ppm) / 1000.0,
                )

            score -= (
                float(cfg.get("heating_on_with_open_window_penalty", 6.0))
                * max(0.0, 1.0 - co2_pressure)
            )

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

        if heating_on:
            score -= float(cfg["open_window_while_heating_penalty"]) * (
                0.5 + heat_pressure
            )

        # Do not casually open windows in cold rooms unless air quality is bad.
        if cold_pressure > 0.0 and person.air_quality_discomfort < 0.50:
            score -= float(
                cfg.get("open_window_cold_room_extra_penalty", 4.0)
            ) * cold_pressure

    if action.name == "close_window":
        score += float(cfg["window_cold_penalty"]) * cold_pressure
        score += float(cfg["window_noise_penalty"]) * person.acoustic_discomfort

        if window_open:
            score += float(
                cfg.get("close_window_open_window_base_bonus", 0.75)
            )

        if heating_on and window_open:
            score += float(
                cfg.get("close_window_while_heating_bonus", 1.5)
            )

        if window_open and cold_pressure > 0.0:
            score += (
                float(cfg.get("close_window_before_heating_bonus", 4.0))
                * cold_pressure
            )

        close_window_cold_temp_c = float(
            cfg.get("close_window_cold_temp_c", 18.5)
        )

        if window_open and current_temp_c < close_window_cold_temp_c:
            score += float(
                cfg.get("close_window_cold_temp_bonus", 3.0)
            )

        # But if CO2 is very high, there is a reason to keep ventilating.
        high_co2_ppm = float(
            cfg.get("keep_window_open_high_co2_ppm", 1200.0)
        )

        if current_co2_ppm > high_co2_ppm:
            co2_pressure = min(
                1.0,
                (current_co2_ppm - high_co2_ppm) / 1000.0,
            )

            score -= (
                float(cfg.get("keep_window_open_high_co2_penalty", 3.0))
                * co2_pressure
            )

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
    # Laundry / tariff #TEMPPP
    # ------------------------------------------------------------
    if action.name == "run_washing_machine":
        # Temporarily disabled until household-level decision/arbitration is added.
        score -= 999.0

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

def propose_actions_for_person(
    available_actions: list[Action],
    person: PersonState,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    location: OccupantLocation,
    assignment: SpaceAssignment,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> list[ActionProposal]:
    """
    Generate scored action proposals for one occupant.

    This does not choose the final action.
    Household arbitration will later decide which proposals survive.
    """

    if not person.can_act:
        return []

    proposals: list[ActionProposal] = []

    available_space_ids = observation.available_space_ids()

    external_schedule_only_actions = {
        "go_to_work",
        "go_to_school",
        "return_home",
    }

    for action in available_actions:
        if action.name in external_schedule_only_actions:
            continue

        score = score_action(
            action=action,
            person=person,
            observation=observation,
            systems=systems,
            execution=execution,
            location=location,
            clock=clock,
            config=config,
        )
        score = score_action(
            action=action,
            person=person,
            observation=observation,
            systems=systems,
            execution=execution,
            location=location,
            clock=clock,
            config=config,
        )

        role = action.target_zone_role

        if role == "door":
            resolved_role = "entrance"
        else:
            resolved_role = role

        if resolved_role in ("current", "outside"):
            target_space_id = location.current_space_id
        elif resolved_role == "outside":
            target_space_id = "outside"
        else:
            target_space_id = assignment.resolve(
                role=resolved_role,
                available_space_ids=available_space_ids,
            )

        proposals.append(
            ActionProposal(
                actor_id=person.occupant_id,
                action_name=action.name,
                score=score,
                target_space_id=target_space_id,
                target_space_role=resolved_role,
                is_household_action=action.name in {
                    "cook",
                    "run_washing_machine",
                    "turn_lights_on",
                    "turn_lights_off",
                    "turn_heating_on",
                    "turn_heating_off",
                    "open_window",
                    "close_window",
                    "open_curtain",
                    "close_curtain",
                },
                conflict_group=_proposal_conflict_group(
                    action=action,
                    target_space_id=target_space_id,
                    actor_id=person.occupant_id,
                ),
                authority_weight=person.authority_weight,
                reason="scored_by_person_decision",
                metadata={
                    "category": action.category,
                    "execution_type": action.execution_type,
                    "requires_home": action.requires_home,
                    "requires_awake": action.requires_awake,
                    "blocks_actor": action.blocks_actor,
                    "background_process": action.background_process,
                },
            )
        )

    return proposals


def _proposal_conflict_group(
    action: Action,
    target_space_id: str,
    actor_id: str,
) -> str:
    """
    Assign broad conflict groups for household arbitration.
    """

    if action.name in {"turn_lights_on", "turn_lights_off"}:
        return f"same_space_light_control:{target_space_id}"

    if action.name in {"open_window", "close_window"}:
        return f"same_space_window_control:{target_space_id}"

    if action.name in {"turn_heating_on", "turn_heating_off"}:
        return f"same_space_heating_control:{target_space_id}"

    if action.name in {"open_curtain", "close_curtain"}:
        return f"same_space_curtain_control:{target_space_id}"

    if action.name == "run_washing_machine":
        return "laundry_machine"

    if action.name == "cook":
        return "household_cooking"

    if action.blocks_actor:
        return f"same_person_foreground:{actor_id}"

    return ""



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
    # A scheduled work obligation first wakes a sleeping occupant, then sends
    # an awake occupant to work on the next decision cycle.  Requiring the
    # person to already be awake allowed sleep to suppress the obligation.
    if (
        person.has_job
        and location.is_home
        and work_day_active(person, clock, config)
    ):
        required_action = "wake_up" if person.is_sleeping else "go_to_work"
        for action in available_actions:
            if action.name == required_action:
                return action

        raise RuntimeError(
            "Work obligation requires "
            f"'{required_action}', but it is not available. "
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
