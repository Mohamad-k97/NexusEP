"""
ABBEY array person kernels.

Purpose:
    Move person dynamics from object/dataclass logic into numeric array logic.

This module updates:
    - hunger
    - fatigue
    - sickness
    - dirty clothes
    - effort/laziness proxy
    - thermal perception
    - air-quality perception
    - visual perception
    - acoustic perception
    - total discomfort
    - home/away status from numeric schedule logic
    - sleeping/awake occupancy state from numeric action state

Important:
    - No person objects.
    - No observation objects.
    - No dicts in timestep-facing kernels.
    - No strings in timestep-facing kernels.
    - Arrays use column indices from schema.py.

Notes:
    The old object model had explicit sleep_pressure and action_friction fields.
    The current array schema does not yet have dedicated columns for those.

    Therefore:
        - sleep pressure is computed as a numeric score array
        - PERSON_LAZINESS is used as the dynamic effort/friction-like state
"""

import math

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Small numeric helpers
# =============================================================================

def clamp01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def sigmoid(x):
    if x >= 60.0:
        return 1.0
    if x <= -60.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def smooth_bounded_update_scalar(x, up, down, dt_hours):
    """
    Smooth bounded update.

    x_next = x + dt * (up * (1 - x) - down * x)

    This intentionally mirrors dynamics/smooth_update.py.
    """
    return x + dt_hours * (up * (1.0 - x) - down * x)


def stress_from_excess(excess, scale):
    """
    Convert positive excess into [0, 1)-like stress using tanh.
    """
    if scale <= 0.0:
        raise ValueError("stress scale must be positive.")

    if excess <= 0.0:
        return 0.0

    return math.tanh(excess / scale)


def minute_forward_distance(start_minute, end_minute):
    """
    Forward distance on a 24h clock.
    """
    return (end_minute - start_minute) % 1440.0


def minute_window_active(minute_of_day, start_minute, end_minute):
    """
    Check whether minute_of_day is inside a possibly overnight interval.

    Examples:
        09:00 -> 17:00
        22:00 -> 06:00
    """
    minute_of_day = minute_of_day % 1440.0
    start_minute = start_minute % 1440.0
    end_minute = end_minute % 1440.0

    if start_minute <= end_minute:
        return start_minute <= minute_of_day < end_minute

    return minute_of_day >= start_minute or minute_of_day < end_minute


def is_person_sleeping(person_state, person_i):
    occupancy_state = int(person_state[person_i, schema.PERSON_OCCUPANCY_STATE])
    action_type = int(person_state[person_i, schema.PERSON_CURRENT_ACTION_TYPE])

    if occupancy_state == schema.OCCUPANCY_HOME_SLEEPING:
        return True

    if action_type == schema.ACTION_TYPE_SLEEP:
        return True

    return False


def is_person_home(person_state, person_i):
    return person_state[person_i, schema.PERSON_IS_HOME] > 0.0


def get_person_zone_id(person_state, person_i):
    return int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])


def get_minute_of_day(time_state):
    return float(time_state[schema.TIME_MINUTE_OF_DAY])


# =============================================================================
# Fanger PMV helpers
# =============================================================================

def fanger_pmv_scalar(
    ta_c,
    tr_c,
    vel_m_s,
    rh_percent,
    met,
    clo,
):
    """
    Scalar Fanger PMV calculation.

    This is copied into numeric form from the old perception module.
    """
    if clo <= 0.0:
        clo = 0.01

    if vel_m_s < 0.0:
        vel_m_s = 0.0

    pa = rh_percent * 10.0 * math.exp(16.6536 - 4030.183 / (ta_c + 235.0))

    icl = 0.155 * clo
    m = met * 58.15
    w = 0.0
    mw = m - w

    if icl <= 0.078:
        fcl = 1.0 + 1.29 * icl
    else:
        fcl = 1.05 + 0.645 * icl

    hcf = 12.1 * math.sqrt(vel_m_s)

    taa = ta_c + 273.0
    tra = tr_c + 273.0

    tcla = taa + (35.5 - ta_c) / (3.5 * icl + 0.1)

    p1 = icl * fcl
    p2 = p1 * 3.96
    p3 = p1 * 100.0
    p4 = p1 * taa
    p5 = 308.7 - 0.028 * mw + p2 * ((tra / 100.0) ** 4)

    xn = tcla / 100.0
    eps = 0.00015

    for _ in range(150):
        xf = xn
        hcn = 2.38 * abs(100.0 * xf - taa) ** 0.25
        hc = hcf
        if hcn > hc:
            hc = hcn

        xn = (p5 + p4 * hc - p2 * (xf ** 4)) / (100.0 + p3 * hc)

        if abs(xn - xf) <= eps:
            break

    tcl = 100.0 * xn - 273.0

    hl1 = 3.05 * 0.001 * (5733.0 - 6.99 * mw - pa)

    if mw > 58.15:
        hl2 = 0.42 * (mw - 58.15)
    else:
        hl2 = 0.0

    hl3 = 1.7 * 0.00001 * m * (5867.0 - pa)
    hl4 = 0.0014 * m * (34.0 - ta_c)
    hl5 = 3.96 * fcl * ((xn ** 4) - ((tra / 100.0) ** 4))
    hl6 = fcl * hc * (tcl - ta_c)

    transfer = 0.303 * math.exp(-0.036 * m) + 0.028

    return transfer * (mw - hl1 - hl2 - hl3 - hl4 - hl5 - hl6)


def pmv_to_ppd_scalar(pmv):
    return 100.0 - 95.0 * math.exp(
        -0.03353 * (pmv ** 4)
        - 0.2179 * (pmv ** 2)
    )


def personal_pmv_scalar(
    pmv,
    sickness,
    cold_sensitivity,
    heat_sensitivity,
    thermal_neutral_shift=0.0,
    sickness_pmv_cold_shift=0.25,
):
    adjusted = pmv + thermal_neutral_shift
    adjusted -= sickness_pmv_cold_shift * sickness

    if adjusted < 0.0:
        adjusted *= cold_sensitivity
    else:
        adjusted *= heat_sensitivity

    return adjusted


# =============================================================================
# Schedule and sleep-pressure score kernels
# =============================================================================

def make_schedule_array_from_person_static(person_static):
    """
    Build schedule_array from person_static.

    Shape:
        [n_persons, 5]

    Columns:
        0 has_job
        1 usual_wake_minute
        2 usual_sleep_minute
        3 work_start_minute
        4 work_end_minute
    """
    n_persons = person_static.shape[0]
    schedule_array = np.zeros((n_persons, 5), dtype=np.float64)

    schedule_array[:, 0] = person_static[:, schema.PERSON_STATIC_HAS_JOB]
    schedule_array[:, 1] = person_static[:, schema.PERSON_STATIC_USUAL_WAKE_MINUTE]
    schedule_array[:, 2] = person_static[:, schema.PERSON_STATIC_USUAL_SLEEP_MINUTE]
    schedule_array[:, 3] = person_static[:, schema.PERSON_STATIC_WORK_START_MINUTE]
    schedule_array[:, 4] = person_static[:, schema.PERSON_STATIC_WORK_END_MINUTE]

    return schedule_array


def work_day_active_for_person(
    schedule_array,
    person_i,
    minute_of_day,
):
    has_job = schedule_array[person_i, 0] > 0.0

    if not has_job:
        return False

    start_minute = schedule_array[person_i, 3]
    end_minute = schedule_array[person_i, 4]

    return minute_window_active(
        minute_of_day=minute_of_day,
        start_minute=start_minute,
        end_minute=end_minute,
    )


def work_obligation_score_for_person(
    schedule_array,
    person_i,
    minute_of_day,
    transition_minutes=45.0,
):
    """
    Soft work signal in [0, 1].

    High during work hours.
    """
    has_job = schedule_array[person_i, 0] > 0.0

    if not has_job:
        return 0.0

    start_minute = schedule_array[person_i, 3]
    end_minute = schedule_array[person_i, 4]

    if transition_minutes <= 0.0:
        if minute_window_active(minute_of_day, start_minute, end_minute):
            return 1.0
        return 0.0

    # For normal daytime work this is smooth.
    # For overnight work, the hard active check prevents wrong midday activation.
    active = minute_window_active(minute_of_day, start_minute, end_minute)

    start_distance = minute_forward_distance(start_minute, minute_of_day)
    end_distance = minute_forward_distance(minute_of_day, end_minute)

    start_signal = sigmoid((start_distance / transition_minutes) * 6.0)
    end_signal = sigmoid((end_distance / transition_minutes) * 6.0)

    value = start_signal * end_signal

    if not active:
        # Keep a small ramp only near the next start.
        minutes_until_start = minute_forward_distance(minute_of_day, start_minute)
        if minutes_until_start <= transition_minutes:
            return clamp01(1.0 - minutes_until_start / transition_minutes)
        return 0.0

    return clamp01(value)


def night_signal_from_minute(
    minute_of_day,
    sleep_minute,
    wake_minute,
    transition_minutes=60.0,
):
    """
    Simplified night/sleep-window signal.

    Uses personal sleep/wake minutes instead of global config.
    """
    if transition_minutes <= 0.0:
        if minute_window_active(minute_of_day, sleep_minute, wake_minute):
            return 1.0
        return 0.0

    active = minute_window_active(minute_of_day, sleep_minute, wake_minute)

    if active:
        after_sleep = minute_forward_distance(sleep_minute, minute_of_day)
        before_wake = minute_forward_distance(minute_of_day, wake_minute)

        start_signal = sigmoid((after_sleep / transition_minutes) * 6.0)
        end_signal = sigmoid((before_wake / transition_minutes) * 6.0)

        return clamp01(start_signal * end_signal)

    minutes_until_sleep = minute_forward_distance(minute_of_day, sleep_minute)

    if minutes_until_sleep <= transition_minutes:
        return clamp01(1.0 - minutes_until_sleep / transition_minutes)

    return 0.0


def compute_sleep_pressure_scores(
    person_state,
    person_static,
    schedule_array,
    time_state,
    out_scores=None,
    fatigue_weight=0.40,
    night_weight=0.40,
    sickness_weight=0.15,
    work_penalty_weight=0.25,
):
    """
    Fast sleep-pressure score for each person.

    Same public API as the reference version, but inlines:
        - get_minute_of_day
        - night_signal_from_minute
        - work_obligation_score_for_person
        - clamp01
        - sigmoid boundaries
    """
    n_persons = person_state.shape[0]

    if out_scores is None:
        out_scores = np.zeros((n_persons,), dtype=np.float64)

    minute_of_day = float(time_state[schema.TIME_MINUTE_OF_DAY]) % 1440.0
    transition_minutes_night = 60.0
    transition_minutes_work = 45.0

    for i in range(n_persons):
        fatigue = person_state[i, schema.PERSON_FATIGUE]
        sickness = person_state[i, schema.PERSON_SICKNESS]

        wake_minute = schedule_array[i, 1] % 1440.0
        sleep_minute = schedule_array[i, 2] % 1440.0

        # ------------------------------------------------------------------
        # Night signal.
        # ------------------------------------------------------------------

        if sleep_minute <= wake_minute:
            night_active = sleep_minute <= minute_of_day < wake_minute
        else:
            night_active = minute_of_day >= sleep_minute or minute_of_day < wake_minute

        if night_active:
            after_sleep = (minute_of_day - sleep_minute) % 1440.0
            before_wake = (wake_minute - minute_of_day) % 1440.0

            x1 = (after_sleep / transition_minutes_night) * 6.0
            if x1 >= 60.0:
                start_signal = 1.0
            elif x1 <= -60.0:
                start_signal = 0.0
            else:
                start_signal = 1.0 / (1.0 + math.exp(-x1))

            x2 = (before_wake / transition_minutes_night) * 6.0
            if x2 >= 60.0:
                end_signal = 1.0
            elif x2 <= -60.0:
                end_signal = 0.0
            else:
                end_signal = 1.0 / (1.0 + math.exp(-x2))

            night = start_signal * end_signal
            if night < 0.0:
                night = 0.0
            elif night > 1.0:
                night = 1.0
        else:
            minutes_until_sleep = (sleep_minute - minute_of_day) % 1440.0
            if minutes_until_sleep <= transition_minutes_night:
                night = 1.0 - minutes_until_sleep / transition_minutes_night
                if night < 0.0:
                    night = 0.0
                elif night > 1.0:
                    night = 1.0
            else:
                night = 0.0

        # ------------------------------------------------------------------
        # Work obligation.
        # ------------------------------------------------------------------

        if schedule_array[i, 0] <= 0.0:
            work = 0.0
        else:
            work_start = schedule_array[i, 3] % 1440.0
            work_end = schedule_array[i, 4] % 1440.0

            if work_start <= work_end:
                work_active = work_start <= minute_of_day < work_end
            else:
                work_active = minute_of_day >= work_start or minute_of_day < work_end

            if not work_active:
                minutes_until_start = (work_start - minute_of_day) % 1440.0
                if minutes_until_start <= transition_minutes_work:
                    work = 1.0 - minutes_until_start / transition_minutes_work
                    if work < 0.0:
                        work = 0.0
                    elif work > 1.0:
                        work = 1.0
                else:
                    work = 0.0
            else:
                start_distance = (minute_of_day - work_start) % 1440.0
                end_distance = (work_end - minute_of_day) % 1440.0

                x1 = (start_distance / transition_minutes_work) * 6.0
                if x1 >= 60.0:
                    start_signal = 1.0
                elif x1 <= -60.0:
                    start_signal = 0.0
                else:
                    start_signal = 1.0 / (1.0 + math.exp(-x1))

                x2 = (end_distance / transition_minutes_work) * 6.0
                if x2 >= 60.0:
                    end_signal = 1.0
                elif x2 <= -60.0:
                    end_signal = 0.0
                else:
                    end_signal = 1.0 / (1.0 + math.exp(-x2))

                work = start_signal * end_signal
                if work < 0.0:
                    work = 0.0
                elif work > 1.0:
                    work = 1.0

        raw = (
            fatigue_weight * fatigue
            + night_weight * night
            + sickness_weight * sickness
            - work_penalty_weight * work
        )

        if raw < 0.0:
            raw = 0.0
        elif raw > 1.0:
            raw = 1.0

        out_scores[i] = raw

    return out_scores

# =============================================================================
# Home/away and sleeping status kernels
# =============================================================================

def update_sleeping_status_from_action(person_state):
    """
    Set sleeping occupancy state from current action type.

    This does not choose actions. It only keeps numeric state consistent.
    """
    n_persons = person_state.shape[0]

    for i in range(n_persons):
        is_home = person_state[i, schema.PERSON_IS_HOME] > 0.0
        action_type = int(person_state[i, schema.PERSON_CURRENT_ACTION_TYPE])

        if not is_home:
            person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_AWAY
            continue

        if action_type == schema.ACTION_TYPE_SLEEP:
            person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_SLEEPING
        else:
            if int(person_state[i, schema.PERSON_OCCUPANCY_STATE]) == schema.OCCUPANCY_HOME_SLEEPING:
                person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

    return person_state


def update_home_away_from_work_schedule(
    person_state,
    person_static,
    schedule_array,
    time_state,
    enforce_work_schedule=True,
):
    """
    Numeric home/away update from work schedule.

    If enforce_work_schedule is True:
        - person with job is away during work window
        - if the person was away and work window ended, return to home zone

    This is intentionally simple. Richer travel/commute behavior belongs later.
    """
    if not enforce_work_schedule:
        return person_state

    n_persons = person_state.shape[0]
    minute_of_day = get_minute_of_day(time_state)

    for i in range(n_persons):
        active_work = work_day_active_for_person(
            schedule_array=schedule_array,
            person_i=i,
            minute_of_day=minute_of_day,
        )

        home_zone_id = int(person_static[i, schema.PERSON_STATIC_HOME_ZONE_ID])

        if active_work:
            person_state[i, schema.PERSON_IS_HOME] = 0.0
            person_state[i, schema.PERSON_PREVIOUS_ZONE_ID] = person_state[
                i,
                schema.PERSON_CURRENT_ZONE_ID,
            ]
            person_state[i, schema.PERSON_CURRENT_ZONE_ID] = schema.MISSING_ID
            person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_AWAY
            person_state[i, schema.PERSON_ACTION_TARGET_ZONE_ID] = schema.MISSING_ID
            person_state[i, schema.PERSON_ACTION_TARGET_SYSTEM_ID] = schema.MISSING_ID
        else:
            was_away = person_state[i, schema.PERSON_IS_HOME] <= 0.0
            if was_away and home_zone_id != schema.MISSING_ID:
                person_state[i, schema.PERSON_IS_HOME] = 1.0
                person_state[i, schema.PERSON_PREVIOUS_ZONE_ID] = schema.MISSING_ID
                person_state[i, schema.PERSON_CURRENT_ZONE_ID] = home_zone_id
                person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

    return person_state


# =============================================================================
# Perception kernels
# =============================================================================

def find_first_system_for_zone(system_state, zone_id):
    n_systems = system_state.shape[0]

    for i in range(n_systems):
        if int(system_state[i, schema.SYSTEM_ZONE_ID]) == zone_id:
            return i

    return schema.MISSING_ID


def zone_lights_on(system_state, zone_id):
    system_i = find_first_system_for_zone(system_state, zone_id)

    if system_i == schema.MISSING_ID:
        return False

    return int(system_state[system_i, schema.SYSTEM_LIGHT_STATE]) == schema.LIGHT_STATE_ON


def update_person_perception(
    person_state,
    person_static,
    zone_state,
    system_state,
    dt_minutes,
    thermal_response_up=2.0,
    thermal_response_down=1.5,
    air_response_up=2.0,
    air_response_down=1.0,
    visual_response_up=2.0,
    visual_response_down=1.0,
    acoustic_response_up=2.0,
    acoustic_response_down=1.0,
    air_velocity_m_s=0.1,
    met=1.1,
    clo=0.8,
    sickness_pmv_cold_shift=0.25,
    comfortable_co2_ppm=1000.0,
    co2_stress_scale_ppm=700.0,
    sickness_air_multiplier=0.5,
    artificial_light_equivalent_lux=300.0,
    required_daylight_lux=150.0,
    daylight_stress_scale_lux=200.0,
    comfortable_noise_db=45.0,
    noise_stress_scale_db=15.0,
):
    """
    Fast perception/discomfort update.

    Same public API as the reference version, but inlines small helpers and
    avoids per-person function-call chains.
    """
    dt_hours = dt_minutes / 60.0
    n_persons = person_state.shape[0]
    n_systems = system_state.shape[0]

    for i in range(n_persons):
        is_home = person_state[i, schema.PERSON_IS_HOME] > 0.0

        if not is_home:
            x = person_state[i, schema.PERSON_THERMAL_STRESS]
            person_state[i, schema.PERSON_THERMAL_STRESS] = x + dt_hours * (
                -thermal_response_down * x
            )

            x = person_state[i, schema.PERSON_AIR_QUALITY_STRESS]
            person_state[i, schema.PERSON_AIR_QUALITY_STRESS] = x + dt_hours * (
                -air_response_down * x
            )

            x = person_state[i, schema.PERSON_VISUAL_STRESS]
            person_state[i, schema.PERSON_VISUAL_STRESS] = x + dt_hours * (
                -visual_response_down * x
            )

            x = person_state[i, schema.PERSON_ACOUSTIC_STRESS]
            person_state[i, schema.PERSON_ACOUSTIC_STRESS] = x + dt_hours * (
                -acoustic_response_down * x
            )

            thermal = person_state[i, schema.PERSON_THERMAL_STRESS]
            air = person_state[i, schema.PERSON_AIR_QUALITY_STRESS]
            visual = person_state[i, schema.PERSON_VISUAL_STRESS]
            acoustic = person_state[i, schema.PERSON_ACOUSTIC_STRESS]
            person_state[i, schema.PERSON_TOTAL_DISCOMFORT] = (
                0.35 * thermal
                + 0.30 * air
                + 0.20 * visual
                + 0.15 * acoustic
            )
            continue

        zone_id = int(person_state[i, schema.PERSON_CURRENT_ZONE_ID])

        if zone_id == schema.MISSING_ID:
            thermal = person_state[i, schema.PERSON_THERMAL_STRESS]
            air = person_state[i, schema.PERSON_AIR_QUALITY_STRESS]
            visual = person_state[i, schema.PERSON_VISUAL_STRESS]
            acoustic = person_state[i, schema.PERSON_ACOUSTIC_STRESS]
            person_state[i, schema.PERSON_TOTAL_DISCOMFORT] = (
                0.35 * thermal
                + 0.30 * air
                + 0.20 * visual
                + 0.15 * acoustic
            )
            continue

        ta = zone_state[zone_id, schema.ZONE_AIR_TEMPERATURE_C]
        tr = zone_state[zone_id, schema.ZONE_MEAN_RADIANT_TEMPERATURE_C]
        rh = zone_state[zone_id, schema.ZONE_RELATIVE_HUMIDITY]

        if rh <= 1.0:
            rh_percent = rh * 100.0
        else:
            rh_percent = rh

        pmv = fanger_pmv_scalar(
            ta_c=ta,
            tr_c=tr,
            vel_m_s=air_velocity_m_s,
            rh_percent=rh_percent,
            met=met,
            clo=clo,
        )

        sickness = person_state[i, schema.PERSON_SICKNESS]
        adjusted_pmv = pmv - sickness_pmv_cold_shift * sickness

        if adjusted_pmv < 0.0:
            adjusted_pmv *= person_static[i, schema.PERSON_STATIC_COLD_SENSITIVITY]
        else:
            adjusted_pmv *= person_static[i, schema.PERSON_STATIC_HEAT_SENSITIVITY]

        ppd = 100.0 - 95.0 * math.exp(
            -0.03353 * (adjusted_pmv ** 4)
            - 0.2179 * (adjusted_pmv ** 2)
        )
        thermal_dissatisfaction = ppd / 100.0
        thermal_satisfaction = 1.0 - thermal_dissatisfaction

        x = person_state[i, schema.PERSON_THERMAL_STRESS]
        thermal_discomfort = x + dt_hours * (
            thermal_response_up * thermal_dissatisfaction * (1.0 - x)
            - thermal_response_down * thermal_satisfaction * x
        )

        co2 = zone_state[zone_id, schema.ZONE_CO2_PPM]
        co2_excess = co2 - comfortable_co2_ppm

        if co2_excess <= 0.0:
            air_raw = 0.0
        else:
            air_raw = math.tanh(co2_excess / co2_stress_scale_ppm)

        air_raw *= person_static[i, schema.PERSON_STATIC_CO2_SENSITIVITY]
        air_raw *= 1.0 + sickness_air_multiplier * sickness

        if air_raw < 0.0:
            air_raw = 0.0
        elif air_raw > 1.0:
            air_raw = 1.0

        x = person_state[i, schema.PERSON_AIR_QUALITY_STRESS]
        air_discomfort = x + dt_hours * (
            air_response_up * air_raw * (1.0 - x)
            - air_response_down * (1.0 - air_raw) * x
        )

        occupancy_state = int(person_state[i, schema.PERSON_OCCUPANCY_STATE])
        action_type = int(person_state[i, schema.PERSON_CURRENT_ACTION_TYPE])
        sleeping = (
            occupancy_state == schema.OCCUPANCY_HOME_SLEEPING
            or action_type == schema.ACTION_TYPE_SLEEP
        )

        if sleeping:
            visual_raw = 0.0
        else:
            effective_light = zone_state[zone_id, schema.ZONE_ILLUMINANCE_LUX]

            lights_on = False
            for system_i in range(n_systems):
                if int(system_state[system_i, schema.SYSTEM_ZONE_ID]) == zone_id:
                    lights_on = int(system_state[system_i, schema.SYSTEM_LIGHT_STATE]) == schema.LIGHT_STATE_ON
                    break

            if lights_on:
                effective_light += artificial_light_equivalent_lux

            light_deficit = required_daylight_lux - effective_light

            if light_deficit <= 0.0:
                visual_raw = 0.0
            else:
                visual_raw = math.tanh(light_deficit / daylight_stress_scale_lux)

            visual_raw *= person_static[i, schema.PERSON_STATIC_LIGHT_SENSITIVITY]

            if visual_raw < 0.0:
                visual_raw = 0.0
            elif visual_raw > 1.0:
                visual_raw = 1.0

        x = person_state[i, schema.PERSON_VISUAL_STRESS]
        visual_discomfort = x + dt_hours * (
            visual_response_up * visual_raw * (1.0 - x)
            - visual_response_down * (1.0 - visual_raw) * x
        )

        noise = zone_state[zone_id, schema.ZONE_NOISE_DB]
        noise_excess = noise - comfortable_noise_db

        if noise_excess <= 0.0:
            acoustic_raw = 0.0
        else:
            acoustic_raw = math.tanh(noise_excess / noise_stress_scale_db)

        acoustic_raw *= person_static[i, schema.PERSON_STATIC_NOISE_SENSITIVITY]

        if acoustic_raw < 0.0:
            acoustic_raw = 0.0
        elif acoustic_raw > 1.0:
            acoustic_raw = 1.0

        x = person_state[i, schema.PERSON_ACOUSTIC_STRESS]
        acoustic_discomfort = x + dt_hours * (
            acoustic_response_up * acoustic_raw * (1.0 - x)
            - acoustic_response_down * (1.0 - acoustic_raw) * x
        )

        person_state[i, schema.PERSON_THERMAL_STRESS] = thermal_discomfort
        person_state[i, schema.PERSON_AIR_QUALITY_STRESS] = air_discomfort
        person_state[i, schema.PERSON_VISUAL_STRESS] = visual_discomfort
        person_state[i, schema.PERSON_ACOUSTIC_STRESS] = acoustic_discomfort

        person_state[i, schema.PERSON_TOTAL_DISCOMFORT] = (
            0.35 * thermal_discomfort
            + 0.30 * air_discomfort
            + 0.20 * visual_discomfort
            + 0.15 * acoustic_discomfort
        )

    return person_state

def _update_total_discomfort_for_person(person_state, person_i):
    thermal = person_state[person_i, schema.PERSON_THERMAL_STRESS]
    air = person_state[person_i, schema.PERSON_AIR_QUALITY_STRESS]
    visual = person_state[person_i, schema.PERSON_VISUAL_STRESS]
    acoustic = person_state[person_i, schema.PERSON_ACOUSTIC_STRESS]

    person_state[person_i, schema.PERSON_TOTAL_DISCOMFORT] = (
        0.35 * thermal
        + 0.30 * air
        + 0.20 * visual
        + 0.15 * acoustic
    )


# =============================================================================
# Health kernel
# =============================================================================

def update_person_health(
    person_state,
    dt_minutes,
    sickness_spontaneous_up=0.0,
    sickness_recovery_down=0.05,
):
    """
    Update sickness severity.

    Writes:
        PERSON_SICKNESS
    """
    dt_hours = dt_minutes / 60.0
    n_persons = person_state.shape[0]

    for i in range(n_persons):
        person_state[i, schema.PERSON_SICKNESS] = smooth_bounded_update_scalar(
            x=person_state[i, schema.PERSON_SICKNESS],
            up=sickness_spontaneous_up,
            down=sickness_recovery_down,
            dt_hours=dt_hours,
        )

    return person_state


# =============================================================================
# Need-state kernels
# =============================================================================

def update_person_needs(
    person_state,
    person_static,
    zone_state,
    schedule_array,
    time_state,
    dt_minutes,
    sleep_pressure_scores=None,
    hunger_base_up=0.08,
    hunger_sleep_multiplier=0.25,
    hunger_fatigue_up=0.03,
    hunger_eat_down=2.5,
    hunger_cook_down=1.2,
    fatigue_base_up=0.02,
    fatigue_awake_up=0.05,
    fatigue_hunger_up=0.05,
    fatigue_sickness_up=0.10,
    fatigue_thermal_up=0.05,
    fatigue_air_up=0.04,
    fatigue_acoustic_up=0.03,
    fatigue_sleep_down=1.2,
    fatigue_rest_down=0.08,
    dirty_base_up=0.01,
    dirty_home_up=0.01,
    dirty_sickness_up=0.02,
    dirty_laundry_down=1.5,
    laziness_fatigue_up=0.08,
    laziness_sickness_up=0.05,
    laziness_sleep_pressure_up=0.04,
    laziness_base_down=0.04,
    laziness_sleep_down=0.08,
):
    """
    Fast hunger/fatigue/dirty/laziness update.

    Same public API as the reference version, but inlines sleeping/home checks
    and smooth_bounded_update_scalar calls.
    """
    dt_hours = dt_minutes / 60.0
    n_persons = person_state.shape[0]

    if sleep_pressure_scores is None:
        sleep_pressure_scores = compute_sleep_pressure_scores(
            person_state=person_state,
            person_static=person_static,
            schedule_array=schedule_array,
            time_state=time_state,
        )

    for i in range(n_persons):
        action_type = int(person_state[i, schema.PERSON_CURRENT_ACTION_TYPE])
        occupancy_state = int(person_state[i, schema.PERSON_OCCUPANCY_STATE])
        sleeping = (
            occupancy_state == schema.OCCUPANCY_HOME_SLEEPING
            or action_type == schema.ACTION_TYPE_SLEEP
        )
        home = person_state[i, schema.PERSON_IS_HOME] > 0.0

        # ------------------------------------------------------------------
        # Hunger.
        # ------------------------------------------------------------------

        fatigue = person_state[i, schema.PERSON_FATIGUE]
        hunger_up = hunger_base_up

        if sleeping:
            hunger_up *= hunger_sleep_multiplier

        hunger_up += hunger_fatigue_up * fatigue

        hunger_down = 0.0
        if action_type == schema.ACTION_TYPE_EAT:
            hunger_down += hunger_eat_down
        if action_type == schema.ACTION_TYPE_COOK:
            hunger_down += hunger_cook_down

        x = person_state[i, schema.PERSON_HUNGER]
        hunger = x + dt_hours * (hunger_up * (1.0 - x) - hunger_down * x)
        person_state[i, schema.PERSON_HUNGER] = hunger

        # ------------------------------------------------------------------
        # Fatigue.
        # ------------------------------------------------------------------

        sickness = person_state[i, schema.PERSON_SICKNESS]
        thermal = person_state[i, schema.PERSON_THERMAL_STRESS]
        air = person_state[i, schema.PERSON_AIR_QUALITY_STRESS]
        acoustic = person_state[i, schema.PERSON_ACOUSTIC_STRESS]

        fatigue_up = fatigue_base_up
        if not sleeping:
            fatigue_up += fatigue_awake_up

        fatigue_up += fatigue_hunger_up * hunger
        fatigue_up += fatigue_sickness_up * sickness
        fatigue_up += fatigue_thermal_up * thermal
        fatigue_up += fatigue_air_up * air
        fatigue_up += fatigue_acoustic_up * acoustic

        fatigue_down = 0.0
        if sleeping or action_type == schema.ACTION_TYPE_SLEEP:
            fatigue_down += fatigue_sleep_down
        if action_type == schema.ACTION_TYPE_IDLE:
            fatigue_down += fatigue_rest_down

        x = person_state[i, schema.PERSON_FATIGUE]
        fatigue = x + dt_hours * (fatigue_up * (1.0 - x) - fatigue_down * x)
        person_state[i, schema.PERSON_FATIGUE] = fatigue

        # ------------------------------------------------------------------
        # Dirty clothes.
        # ------------------------------------------------------------------

        dirty_up = dirty_base_up
        if home:
            dirty_up += dirty_home_up
        dirty_up += dirty_sickness_up * sickness

        dirty_down = 0.0
        if action_type == schema.ACTION_TYPE_DO_LAUNDRY:
            dirty_down += dirty_laundry_down

        x = person_state[i, schema.PERSON_DIRTY_CLOTHES]
        dirty = x + dt_hours * (dirty_up * (1.0 - x) - dirty_down * x)
        person_state[i, schema.PERSON_DIRTY_CLOTHES] = dirty

        # ------------------------------------------------------------------
        # Laziness / effort-friction proxy.
        # ------------------------------------------------------------------

        laziness_up = 0.0
        laziness_up += laziness_fatigue_up * fatigue
        laziness_up += laziness_sickness_up * sickness
        laziness_up += laziness_sleep_pressure_up * sleep_pressure_scores[i]

        laziness_down = laziness_base_down
        if sleeping:
            laziness_down += laziness_sleep_down

        x = person_state[i, schema.PERSON_LAZINESS]
        laziness = x + dt_hours * (laziness_up * (1.0 - x) - laziness_down * x)
        person_state[i, schema.PERSON_LAZINESS] = laziness

    return person_state

# =============================================================================
# Occupancy aggregation
# =============================================================================

def reset_zone_occupancy_from_person_state(person_state, zone_state):
    """
    Recompute zone occupant counts from person state.
    """
    zone_state[:, schema.ZONE_OCCUPANT_COUNT] = 0.0
    zone_state[:, schema.ZONE_IS_OCCUPIED] = 0.0

    n_persons = person_state.shape[0]

    for i in range(n_persons):
        if person_state[i, schema.PERSON_IS_HOME] <= 0.0:
            continue

        zone_id = int(person_state[i, schema.PERSON_CURRENT_ZONE_ID])

        if zone_id == schema.MISSING_ID:
            continue

        zone_state[zone_id, schema.ZONE_OCCUPANT_COUNT] += 1.0
        zone_state[zone_id, schema.ZONE_IS_OCCUPIED] = 1.0

    return zone_state


# =============================================================================
# Full person-dynamics step
# =============================================================================

def update_person_dynamics(
    person_state,
    person_static,
    zone_state,
    system_state,
    schedule_array,
    time_state,
    dt_minutes,
    sleep_pressure_scores=None,
    enforce_work_schedule=True,
):
    """
    Fast Phase 7 person-dynamics update.

    Same public API/order as the reference version, but inlines the cheap
    home/away, sleeping, health, and occupancy aggregation loops.
    """
    n_persons = person_state.shape[0]
    minute_of_day = float(time_state[schema.TIME_MINUTE_OF_DAY]) % 1440.0

    # ----------------------------------------------------------------------
    # 1. update home/away from work schedule
    # ----------------------------------------------------------------------

    if enforce_work_schedule:
        for i in range(n_persons):
            if schedule_array[i, 0] > 0.0:
                start_minute = schedule_array[i, 3] % 1440.0
                end_minute = schedule_array[i, 4] % 1440.0

                if start_minute <= end_minute:
                    active_work = start_minute <= minute_of_day < end_minute
                else:
                    active_work = minute_of_day >= start_minute or minute_of_day < end_minute
            else:
                active_work = False

            home_zone_id = int(person_static[i, schema.PERSON_STATIC_HOME_ZONE_ID])

            if active_work:
                person_state[i, schema.PERSON_IS_HOME] = 0.0
                person_state[i, schema.PERSON_PREVIOUS_ZONE_ID] = person_state[
                    i,
                    schema.PERSON_CURRENT_ZONE_ID,
                ]
                person_state[i, schema.PERSON_CURRENT_ZONE_ID] = schema.MISSING_ID
                person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_AWAY
                person_state[i, schema.PERSON_ACTION_TARGET_ZONE_ID] = schema.MISSING_ID
                person_state[i, schema.PERSON_ACTION_TARGET_SYSTEM_ID] = schema.MISSING_ID
            else:
                was_away = person_state[i, schema.PERSON_IS_HOME] <= 0.0
                if was_away and home_zone_id != schema.MISSING_ID:
                    person_state[i, schema.PERSON_IS_HOME] = 1.0
                    person_state[i, schema.PERSON_PREVIOUS_ZONE_ID] = schema.MISSING_ID
                    person_state[i, schema.PERSON_CURRENT_ZONE_ID] = home_zone_id
                    person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

    # ----------------------------------------------------------------------
    # 2. update sleeping status from current action
    # ----------------------------------------------------------------------

    for i in range(n_persons):
        is_home = person_state[i, schema.PERSON_IS_HOME] > 0.0
        action_type = int(person_state[i, schema.PERSON_CURRENT_ACTION_TYPE])

        if not is_home:
            person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_AWAY
        elif action_type == schema.ACTION_TYPE_SLEEP:
            person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_SLEEPING
        else:
            if int(person_state[i, schema.PERSON_OCCUPANCY_STATE]) == schema.OCCUPANCY_HOME_SLEEPING:
                person_state[i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

    # ----------------------------------------------------------------------
    # 3. update perception
    # ----------------------------------------------------------------------

    update_person_perception(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        system_state=system_state,
        dt_minutes=dt_minutes,
    )

    # ----------------------------------------------------------------------
    # 4. update health
    # ----------------------------------------------------------------------

    dt_hours = dt_minutes / 60.0
    sickness_spontaneous_up = 0.0
    sickness_recovery_down = 0.05

    for i in range(n_persons):
        x = person_state[i, schema.PERSON_SICKNESS]
        person_state[i, schema.PERSON_SICKNESS] = x + dt_hours * (
            sickness_spontaneous_up * (1.0 - x)
            - sickness_recovery_down * x
        )

    # ----------------------------------------------------------------------
    # 5. compute sleep pressure
    # ----------------------------------------------------------------------

    if sleep_pressure_scores is None:
        sleep_pressure_scores = compute_sleep_pressure_scores(
            person_state=person_state,
            person_static=person_static,
            schedule_array=schedule_array,
            time_state=time_state,
        )
    else:
        compute_sleep_pressure_scores(
            person_state=person_state,
            person_static=person_static,
            schedule_array=schedule_array,
            time_state=time_state,
            out_scores=sleep_pressure_scores,
        )

    # ----------------------------------------------------------------------
    # 6. update needs
    # ----------------------------------------------------------------------

    update_person_needs(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        schedule_array=schedule_array,
        time_state=time_state,
        dt_minutes=dt_minutes,
        sleep_pressure_scores=sleep_pressure_scores,
    )

    # ----------------------------------------------------------------------
    # 7. recompute zone occupancy
    # ----------------------------------------------------------------------

    zone_state[:, schema.ZONE_OCCUPANT_COUNT] = 0.0
    zone_state[:, schema.ZONE_IS_OCCUPIED] = 0.0

    for i in range(n_persons):
        if person_state[i, schema.PERSON_IS_HOME] <= 0.0:
            continue

        zone_id = int(person_state[i, schema.PERSON_CURRENT_ZONE_ID])

        if zone_id == schema.MISSING_ID:
            continue

        zone_state[zone_id, schema.ZONE_OCCUPANT_COUNT] += 1.0
        zone_state[zone_id, schema.ZONE_IS_OCCUPIED] = 1.0

    return person_state, zone_state, sleep_pressure_scores

# =============================================================================
# Numba-prep variants
# =============================================================================

def update_person_dynamics_numba_ready(
    person_state,
    person_static,
    zone_state,
    system_state,
    schedule_array,
    time_state,
    dt_minutes,
    sleep_pressure_scores,
    enforce_work_schedule_flag=1,
):
    """
    Numba-prep person dynamics step.

    Difference from update_person_dynamics(...):
        - sleep_pressure_scores is required
        - no optional None
        - no internal allocation
        - returns True instead of tuple
    """
    enforce_work_schedule = enforce_work_schedule_flag > 0

    update_home_away_from_work_schedule(
        person_state=person_state,
        person_static=person_static,
        schedule_array=schedule_array,
        time_state=time_state,
        enforce_work_schedule=enforce_work_schedule,
    )

    update_sleeping_status_from_action(person_state)

    update_person_perception(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        system_state=system_state,
        dt_minutes=dt_minutes,
    )

    update_person_health(
        person_state=person_state,
        dt_minutes=dt_minutes,
    )

    compute_sleep_pressure_scores(
        person_state=person_state,
        person_static=person_static,
        schedule_array=schedule_array,
        time_state=time_state,
        out_scores=sleep_pressure_scores,
    )

    update_person_needs(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        schedule_array=schedule_array,
        time_state=time_state,
        dt_minutes=dt_minutes,
        sleep_pressure_scores=sleep_pressure_scores,
    )

    reset_zone_occupancy_from_person_state(
        person_state=person_state,
        zone_state=zone_state,
    )

    return True