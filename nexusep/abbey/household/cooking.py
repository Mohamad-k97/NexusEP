"""
ABBEY household cooking effects.
"""

from typing import Dict, Mapping, Any

from nexusep.abbey.agents.states import PersonState
from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.household.state import HouseholdState


AbbeyConfig = Mapping[str, Any]


def person_can_receive_family_meal(
    person: PersonState,
    location: OccupantLocation,
) -> bool:
    """
    Returns True if this person can benefit from a generic household cooked meal.

    Infants are excluded for now because they need separate feeding logic later.
    """

    if not location.is_home:
        return False

    if person.age_group == "infant":
        return False

    return True


def apply_family_meal_effect(
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
    household: HouseholdState,
    cook_id: str,
    config: AbbeyConfig,
) -> tuple[Dict[str, PersonState], HouseholdState]:
    """
    Apply the effect of one completed family cooking event.
    """

    cfg = config.get("household_cooking", {})

    hunger_down = float(cfg.get("family_meal_hunger_down", 0.75))

    updated_people = dict(people)

    for occupant_id, person in people.items():
        location = locations.get(occupant_id)

        if location is None:
            continue

        if not person_can_receive_family_meal(
            person=person,
            location=location,
        ):
            continue

        updated_people[occupant_id] = person.copy(
            hunger=max(0.0, person.hunger - hunger_down)
        )

    household = household.copy(
        cooked_meal_events=household.cooked_meal_events + 1,
        last_cook_id=cook_id,
    )

    return updated_people, household