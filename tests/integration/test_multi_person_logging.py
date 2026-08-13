"""Verification of exact multi-person logging cardinality and occupancy."""

from __future__ import annotations

import json

import pytest

from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import (
    DwellingObservation,
    ExecutionState,
    PersonState,
    SimulationClock,
    SystemState,
    ZoneObservation,
)
from nexusep.abbey.household.state import HouseholdState
from nexusep.abbey.simulation.logger import SimulationLogger
from nexusep.abbey.systems import CooldownState

pytestmark = pytest.mark.integration
VALIDATION_CATEGORY = "verification"


@pytest.mark.parametrize(
    "location_by_person",
    [
        {"resident_maria": "zone-west", "resident_zoe": "zone-west"},
        {"resident_maria": "zone-west", "resident_zoe": "zone-east"},
        {"resident_maria": "zone-west", "resident_zoe": "outside"},
        {"resident_maria": "zone-east", "resident_zoe": "zone-west"},
    ],
)
def test_multi_person_rows_and_zone_occupancy_reconcile_exactly(
    location_by_person: dict[str, str],
) -> None:
    people = {
        occupant_id: PersonState(occupant_id=occupant_id)
        for occupant_id in location_by_person
    }
    locations = {
        occupant_id: OccupantLocation(
            occupant_id=occupant_id,
            dwelling_id="home_north",
            building_id="building_alpha",
            is_home=zone_id != "outside",
            current_space_id=zone_id,
        )
        for occupant_id, zone_id in location_by_person.items()
    }
    observation = DwellingObservation(
        default_zone_id="zone-west",
        zone_observations={
            zone_id: ZoneObservation(zone_id=zone_id, zone_name=zone_id)
            for zone_id in ("zone-west", "zone-east")
        },
    )
    primary_id = "resident_maria"
    logger = SimulationLogger()
    logger.record_step(
        clock=SimulationClock(step=4, hour=1.0, dt_hours=0.25),
        person=people[primary_id],
        location=locations[primary_id],
        assignment=SpaceAssignment(
            occupant_id=primary_id,
            dwelling_id="home_north",
            building_id="building_alpha",
            default_space_id="zone-west",
            role_to_space_id={"idle": "zone-west"},
        ),
        household=HouseholdState(
            household_id="home_north", occupant_ids=sorted(people)
        ),
        cooldowns=CooldownState(),
        observation=observation,
        systems=SystemState(default_space_id="zone-west"),
        execution=ExecutionState(),
        chunk_records=[],
        people=people,
        locations=locations,
    )

    assert len(logger.records) == 1
    assert len(logger.person_records) == len(people)
    assert len(logger.zone_records) == len(observation.zone_observations)
    person_locations = {
        row["occupant_id"]: row["location_current_space_id"]
        for row in logger.person_records
    }
    assert person_locations == location_by_person
    for row in logger.zone_records:
        ids = json.loads(row["occupied_person_ids"])
        expected = sorted(
            occupant_id
            for occupant_id, zone_id in location_by_person.items()
            if zone_id == row["zone_id"]
        )
        assert ids == expected
        assert row["number_of_people"] == len(ids)
