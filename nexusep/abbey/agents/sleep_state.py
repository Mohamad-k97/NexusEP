"""
Sleep episode memory.
"""

from nexusep.abbey.agents.states import PersonState, SimulationClock


def update_sleep_episode_timers(
    person: PersonState,
    clock: SimulationClock,
) -> PersonState:
    dt_minutes = clock.dt_hours * 60.0

    if person.is_sleeping:
        return person.copy(
            minutes_asleep=person.minutes_asleep + dt_minutes,
            minutes_awake_since_sleep=0.0,
        )

    return person.copy(
        minutes_asleep=0.0,
        minutes_awake_since_sleep=person.minutes_awake_since_sleep + dt_minutes,
    )