"""
Household cooking coordination.

v0.2 still runs one occupant, but this module is designed for
future multiagent cooking decisions.
"""

from typing import Optional

from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.agents.states import PersonState, ExecutionState, HouseholdState


def person_available_to_cook(
    person: PersonState,
    location: OccupantLocation,
    execution: ExecutionState,
    fatigue_threshold: float = 0.75,
) -> bool:
    if not person.can_cook:
        return False

    if not location.is_home:
        return False

    if person.is_sleeping:
        return False

    if person.fatigue >= fatigue_threshold:
        return False

    if execution.actor_is_blocked(person.occupant_id):
        return False

    return True


def choose_household_cook(
    people: list[PersonState],
    locations: dict[str, OccupantLocation],
    execution: ExecutionState,
    household: HouseholdState,
    fatigue_threshold: float = 0.75,
) -> Optional[str]:
    """
    Decide who should cook.

    Priority:
        1. main cook if available
        2. next priority available cook
        3. None if nobody available
    """

    people_by_id = {
        person.occupant_id: person
        for person in people
    }

    main_cook = people_by_id.get(household.main_cook_id)

    if main_cook is not None:
        main_location = locations.get(main_cook.occupant_id)

        if main_location is not None and person_available_to_cook(
            person=main_cook,
            location=main_location,
            execution=execution,
            fatigue_threshold=fatigue_threshold,
        ):
            return main_cook.occupant_id

    candidates = []

    for person in people:
        location = locations.get(person.occupant_id)

        if location is None:
            continue

        if not person_available_to_cook(
            person=person,
            location=location,
            execution=execution,
            fatigue_threshold=fatigue_threshold,
        ):
            continue

        priority = household.cooking_priority_by_occupant.get(
            person.occupant_id,
            person.cooking_priority,
        )

        candidates.append((priority, person.occupant_id))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def household_hunger_signal(
    people: list[PersonState],
    locations: dict[str, OccupantLocation],
) -> float:
    """
    For now: max hunger among people currently at home.
    Later we can use weighted average or meal norms.
    """

    home_hungers = []

    for person in people:
        location = locations.get(person.occupant_id)

        if location is not None and location.is_home:
            home_hungers.append(person.hunger)

    if not home_hungers:
        return 0.0

    return max(home_hungers)