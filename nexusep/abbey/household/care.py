from typing import Dict, Optional, Tuple, Any

from nexusep.abbey.agents.states import PersonState
from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.household.state import HouseholdState


def person_is_dependent(person: PersonState) -> bool:
    if getattr(person, "age_group", "") == "infant":
        return True

    return float(getattr(person, "care_dependency", 0.0)) >= 0.8


def dependent_care_need(person: PersonState) -> float:
    hunger = float(getattr(person, "hunger", 0.0))
    fatigue = float(getattr(person, "fatigue", 0.0))
    sleep_pressure = float(getattr(person, "sleep_pressure", 0.0))

    return max(
        hunger,
        fatigue,
        sleep_pressure,
        0.5 * hunger + 0.3 * sleep_pressure + 0.2 * fatigue,
    )


def most_needy_dependent_at_home(
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
) -> Tuple[Optional[str], float]:
    best_id = None
    best_need = -1.0

    for occupant_id, person in people.items():
        if not person_is_dependent(person):
            continue

        location = locations.get(occupant_id)

        if location is None or not location.is_home:
            continue

        need = dependent_care_need(person)

        if need > best_need:
            best_id = occupant_id
            best_need = need

    return best_id, best_need


def apply_dependent_care_effect(
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
    household: HouseholdState,
    caregiver_id: str,
    config: Dict[str, Any],
) -> Tuple[Dict[str, PersonState], HouseholdState]:
    care_config = config.get("household_care", {})

    hunger_down = float(care_config.get("hunger_down", 0.45))
    fatigue_down = float(care_config.get("fatigue_down", 0.20))
    sleep_pressure_down = float(care_config.get("sleep_pressure_down", 0.30))

    target_id, _ = most_needy_dependent_at_home(
        people=people,
        locations=locations,
    )

    if target_id is None:
        return people, household

    target = people[target_id]

    target.hunger = max(0.0, float(target.hunger) - hunger_down)
    target.fatigue = max(0.0, float(target.fatigue) - fatigue_down)
    target.sleep_pressure = max(
        0.0,
        float(target.sleep_pressure) - sleep_pressure_down,
    )

    household.care_events += 1
    household.last_caregiver_id = caregiver_id
    household.last_care_target_id = target_id

    return people, household