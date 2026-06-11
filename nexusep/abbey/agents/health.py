"""
ABBEY health-state update.

For v0.1, sickness is a smooth severity state.
Random infection events are not handled here yet.
"""

from typing import Any, Mapping

from nexusep.abbey.agents.states import PersonState, SimulationClock
from nexusep.abbey.dynamics.influences import compute_sickness_pressures
from nexusep.abbey.dynamics.smooth_update import smooth_bounded_update


AbbeyConfig = Mapping[str, Any]


def update_health(
    person: PersonState,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> PersonState:
    """
    Update health-related internal states.

    Currently updates:
        sickness_severity
    """

    sickness_up, sickness_down = compute_sickness_pressures(
        person=person,
        clock=clock,
        config=config,
    )

    new_sickness_severity = smooth_bounded_update(
        x=person.sickness_severity,
        up=sickness_up,
        down=sickness_down,
        dt_hours=clock.dt_hours,
    )

    return person.copy(
        sickness_severity=new_sickness_severity,
    )