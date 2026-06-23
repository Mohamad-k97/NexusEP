"""
ABBEY household laundry dynamics.

Dirty clothes are a household stock, not an individual PersonState variable.
"""

from typing import Any, Dict, Mapping

from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.agents.states import PersonState, SimulationClock
from nexusep.abbey.household.state import HouseholdState
from nexusep.abbey.dynamics.smooth_update import smooth_bounded_update


AbbeyConfig = Mapping[str, Any]


def _washing_machine_active(chunk_records: list) -> bool:
    """
    Return True if run_washing_machine is active in this timestep.
    """

    for chunk in chunk_records:
        if chunk.get("chunk_label") == "run_washing_machine":
            return True

        for item in chunk.get("power_breakdown", []):
            if item.get("name") == "run_washing_machine":
                return True

    return False


def _person_dirty_clothes_generation(
    person: PersonState,
    location: OccupantLocation,
    config: AbbeyConfig,
) -> float:
    """
    Dirty-clothes generation pressure contribution from one occupant.
    """

    cfg = config.get("household_dirty_clothes", {})

    base_multiplier = float(cfg.get("base_multiplier", 1.0))
    home_multiplier = float(cfg.get("home_multiplier", 1.10))
    work_school_multiplier = float(cfg.get("work_or_school_multiplier", 1.20))
    sickness_multiplier = float(cfg.get("sickness_multiplier", 0.50))

    generation = float(person.laundry_generation_rate) * base_multiplier

    if location.is_home:
        generation *= home_multiplier

    if location.away_reason in ("work", "school"):
        generation *= work_school_multiplier

    generation *= 1.0 + sickness_multiplier * float(person.sickness_severity)

    return generation


def household_dirty_clothes_up_pressure(
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
    config: AbbeyConfig,
) -> float:
    """
    Sum dirty-clothes generation from all occupants.
    """

    total = 0.0

    for occupant_id, person in people.items():
        location = locations.get(occupant_id)

        if location is None:
            continue

        total += _person_dirty_clothes_generation(
            person=person,
            location=location,
            config=config,
        )

    return total


def update_household_dirty_clothes(
    household: HouseholdState,
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
    clock: SimulationClock,
    config: AbbeyConfig,
    chunk_records: list,
) -> HouseholdState:
    """
    Update household dirty clothes.

    Growth:
        sum of all occupant laundry generation rates.

    Reduction:
        washing machine active during this timestep.
    """

    cfg = config.get("household_dirty_clothes", {})

    up = household_dirty_clothes_up_pressure(
        people=people,
        locations=locations,
        config=config,
    )

    down = 0.0

    if _washing_machine_active(chunk_records):
        down += float(cfg.get("washing_machine_down", 1.25))

    new_dirty_clothes = smooth_bounded_update(
        x=household.dirty_clothes,
        up=up,
        down=down,
        dt_hours=clock.dt_hours,
    )

    return household.copy(dirty_clothes=new_dirty_clothes)