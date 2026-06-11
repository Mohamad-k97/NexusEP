"""
ABBEY idle/ambient movement.

Purposeful movement is handled by actions:
    sleep -> bedroom
    cook -> kitchen
    work -> office

Idle movement is different:
    while awake, home, and not blocked, the occupant may randomly move
    between assigned semantic spaces using a Markov transition matrix.
"""

import random
from typing import Any, Mapping, List

from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import PersonState, ExecutionState, SimulationClock


AbbeyConfig = Mapping[str, Any]


def _weighted_choice(
    probabilities: Mapping[str, float],
    rng: random.Random,
) -> str:
    total = sum(float(v) for v in probabilities.values())

    if total <= 0.0:
        raise ValueError("Transition probabilities must have positive total.")

    draw = rng.random() * total
    cumulative = 0.0

    for key, value in probabilities.items():
        cumulative += float(value)
        if draw <= cumulative:
            return key

    return list(probabilities.keys())[-1]


def _get_profile(
    person: PersonState,
    config: AbbeyConfig,
) -> Mapping[str, Any]:
    profiles = config["idle_movement_profiles"]
    profile_name = person.idle_movement_profile

    if profile_name not in profiles:
        profile_name = "normal"

    return profiles[profile_name]


def update_idle_location(
    person: PersonState,
    location: OccupantLocation,
    assignment: SpaceAssignment,
    execution: ExecutionState,
    available_space_ids: List[str],
    clock: SimulationClock,
    config: AbbeyConfig,
    rng: random.Random,
) -> OccupantLocation:
    """
    Randomly update occupant location while idle.

    This only runs when:
        - person is home
        - person is awake
        - actor is not blocked by foreground action
        - minimum dwell time has passed
    """

    profile = _get_profile(person, config)

    updated_location = location.copy(
        minutes_since_last_space_change=(
            location.minutes_since_last_space_change + clock.dt_hours * 60.0
        )
    )

    if not updated_location.is_home:
        return updated_location

    if person.is_sleeping:
        return updated_location

    if execution.actor_is_blocked(person.occupant_id):
        return updated_location

    minimum_dwell = float(profile["minimum_dwell_minutes"])

    if updated_location.minutes_since_last_space_change < minimum_dwell:
        return updated_location

    probability_per_hour = (
        float(profile["transition_probability_per_hour"])
        * person.mobility_tendency
    )

    probability_this_step = probability_per_hour * clock.dt_hours

    if rng.random() > probability_this_step:
        return updated_location

    matrix = profile["role_transition_matrix"]

    current_role = updated_location.current_space_role

    if current_role not in matrix:
        current_role = "idle"

    next_role = _weighted_choice(
        probabilities=matrix[current_role],
        rng=rng,
    )

    next_space_id = assignment.resolve(
        role=next_role,
        available_space_ids=available_space_ids,
    )

    if next_space_id == updated_location.current_space_id:
        return updated_location

    return updated_location.copy(
        current_space_id=next_space_id,
        current_space_role=next_role,
        minutes_since_last_space_change=0.0,
    )