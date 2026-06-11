"""
ABBEY temporal/circadian utilities.

This file does not force sleep or work.
It only provides soft biological and obligation signals.
"""

import math
from typing import Any, Mapping

from nexusep.abbey.agents.states import PersonState, SimulationClock


AbbeyConfig = Mapping[str, Any]


def _sigmoid(x: float) -> float:
    if x >= 60.0:
        return 1.0
    if x <= -60.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))

def hour_of_day(clock: SimulationClock) -> float:
    return clock.hour % 24.0


def work_day_active(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> bool:
    if not person.has_job:
        return False

    cfg = config["circadian"]

    hour = hour_of_day(clock)
    start = float(cfg["work_start_hour"])
    end = float(cfg["work_end_hour"])

    return start <= hour < end


def work_day_finished(
    clock: SimulationClock,
    config: AbbeyConfig,
) -> bool:
    cfg = config["circadian"]

    hour = hour_of_day(clock)
    end = float(cfg["work_end_hour"])

    return hour >= end

def _hour_forward_distance(start: float, end: float) -> float:
    return (end - start) % 24.0


def melatonin_signal(
    clock: SimulationClock,
    config: AbbeyConfig,
) -> float:
    """
    Simplified melatonin-like night signal in [0, 1].

    Uses hour_of_day so it works across multiple days.
    """

    cfg = config["circadian"]

    hour = (hour_of_day(clock) - float(cfg["chronotype_shift_h"])) % 24.0
    onset = float(cfg["melatonin_onset_hour"])
    offset = float(cfg["melatonin_offset_hour"])
    k = float(cfg["transition_steepness"])

    if onset > offset:
        if hour >= onset:
            return _sigmoid(k * (hour - onset))

        if hour <= offset:
            return _sigmoid(k * (offset - hour))

        return 0.0

    if onset <= hour <= offset:
        after_onset = _sigmoid(k * (hour - onset))
        before_offset = _sigmoid(k * (offset - hour))
        return max(0.0, min(1.0, after_onset * before_offset))

    return 0.0


def homeostatic_sleep_signal(
    person: PersonState,
    config: AbbeyConfig,
) -> float:
    """
    Sleep pressure from time awake.

    This is not a hard bedtime. It is biological pressure.
    The longer the person stays awake, the more sleep becomes attractive.
    """

    cfg = config["sleep_pressure"]

    center = float(cfg["awake_duration_center_minutes"])
    width = float(cfg["awake_duration_width_minutes"])

    x = (person.minutes_awake_since_sleep - center) / width

    return _sigmoid(6.0 * x)

def work_obligation_signal(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> float:
    """
    Soft work pressure in [0, 1].

    High during work hours.
    Uses hour_of_day so it works for multi-day simulations.
    """

    if not person.has_job:
        return 0.0

    cfg = config["circadian"]

    hour = hour_of_day(clock)
    start = float(cfg["work_start_hour"])
    end = float(cfg["work_end_hour"])
    transition = float(cfg["work_transition_h"])

    start_signal = _sigmoid((hour - start) / transition * 6.0)
    end_signal = _sigmoid((end - hour) / transition * 6.0)

    return max(0.0, min(1.0, start_signal * end_signal))


def wake_drive(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> float:
    melatonin = melatonin_signal(clock, config)
    work = work_obligation_signal(person, clock, config)

    drive = (
        0.45 * (1.0 - person.sleep_pressure)
        + 0.25 * (1.0 - person.fatigue)
        + 0.20 * (1.0 - melatonin)
        + 0.25 * work
    )

    return max(0.0, min(1.0, drive))

def sleep_drive(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> float:
    melatonin = melatonin_signal(clock, config)

    drive = (
        0.45 * person.sleep_pressure
        + 0.35 * person.fatigue
        + 0.20 * melatonin
        + 0.15 * person.sickness_severity
    )

    return max(0.0, min(1.0, drive))

def planned_leave_soon(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
    horizon_hours: float = 1.0,
) -> float:
    if not person.has_job:
        return 0.0

    start = float(config["circadian"]["work_start_hour"])
    hours_until_work = _hour_forward_distance(clock.hour, start)

    if hours_until_work > horizon_hours:
        return 0.0

    return 1.0 - (hours_until_work / horizon_hours)


def planned_sleep_soon(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
    horizon_hours: float = 1.0,
) -> float:
    future_clock = clock.copy(hour=(clock.hour + horizon_hours) % 24.0)

    return max(
        sleep_drive(person, clock, config),
        sleep_drive(person, future_clock, config),
    )