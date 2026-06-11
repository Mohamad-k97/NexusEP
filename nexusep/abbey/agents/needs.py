"""
ABBEY internal need-state update.

This applies influence pressures to smooth bounded internal states.
"""

from typing import Any, Mapping

from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    ActionState,
    SimulationClock,
)
from nexusep.abbey.dynamics.smooth_update import smooth_bounded_update
from nexusep.abbey.dynamics.influences import (
    compute_hunger_pressures,
    compute_fatigue_pressures,
    compute_sleep_pressures,
    compute_dirty_clothes_pressures,
    compute_action_friction_pressures,
)


AbbeyConfig = Mapping[str, Any]


def update_needs(
    person: PersonState,
    observation: DwellingObservation,
    action: ActionState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> PersonState:
    hunger_up, hunger_down = compute_hunger_pressures(
        person=person,
        action=action,
        clock=clock,
        config=config,
    )

    fatigue_up, fatigue_down = compute_fatigue_pressures(
        person=person,
        observation=observation,
        action=action,
        clock=clock,
        config=config,
    )

    sleep_up, sleep_down = compute_sleep_pressures(
        person=person,
        action=action,
        clock=clock,
        config=config,
    )

    dirty_up, dirty_down = compute_dirty_clothes_pressures(
        person=person,
        action=action,
        clock=clock,
        config=config,
    )

    friction_up, friction_down = compute_action_friction_pressures(
        person=person,
        clock=clock,
        config=config,
    )

    return person.copy(
        hunger=smooth_bounded_update(
            x=person.hunger,
            up=hunger_up,
            down=hunger_down,
            dt_hours=clock.dt_hours,
        ),
        fatigue=smooth_bounded_update(
            x=person.fatigue,
            up=fatigue_up,
            down=fatigue_down,
            dt_hours=clock.dt_hours,
        ),
        sleep_pressure=smooth_bounded_update(
            x=person.sleep_pressure,
            up=sleep_up,
            down=sleep_down,
            dt_hours=clock.dt_hours,
        ),
        dirty_clothes=smooth_bounded_update(
            x=person.dirty_clothes,
            up=dirty_up,
            down=dirty_down,
            dt_hours=clock.dt_hours,
        ),
        action_friction=smooth_bounded_update(
            x=person.action_friction,
            up=friction_up,
            down=friction_down,
            dt_hours=clock.dt_hours,
        ),
    )