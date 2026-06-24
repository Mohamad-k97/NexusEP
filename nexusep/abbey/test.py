"""
ABBEY Phase 9.14 real AbbeySimulation integration test.

Run:

    python -m nexusep.abbey.run_test_internal_sources_phase_9_14

This test uses the real AbbeySimulation class.
It injects controlled chunk_records only to avoid depending on the decision engine
choosing cook/shower/laundry/laptop in one timestep.
"""

from pathlib import Path

from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    ZoneObservation,
    SystemState,
    ExecutionState,
)
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.household import HouseholdState
from nexusep.abbey.systems import CooldownState

from nexusep.abbey.building.factory import (
    make_default_family_building,
    default_family_space_role_map,
)
from nexusep.abbey.building.performance import SimpleBuildingPerformanceModel

from nexusep.abbey.building.physics.internal_sources import (
    INTERNAL_SOURCE_KIND_PERSON,
    INTERNAL_SOURCE_KIND_APPLIANCE,
    INTERNAL_SOURCE_KIND_ACTIVITY,
    INTERNAL_SOURCE_KIND_LIGHTING,
    INTERNAL_SOURCE_KIND_HVAC,
)


def find_config_path():
    here = Path(__file__).resolve()

    candidates = [
        here.parents[2] / "nexusep" / "data" / "abbey" / "config" / "abbey_config.jsonc",
        here.parents[1] / "data" / "abbey" / "config" / "abbey_config.jsonc",
        Path.cwd() / "nexusep" / "data" / "abbey" / "config" / "abbey_config.jsonc",
        Path.cwd() / "data" / "abbey" / "config" / "abbey_config.jsonc",
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find abbey_config.jsonc. Checked:\n"
        + "\n".join(str(path) for path in candidates)
    )


def simple_zone_id(zone_id):
    zone_id = str(zone_id)

    prefix = "dwelling_1_"

    if zone_id.startswith(prefix):
        return zone_id[len(prefix):]

    return zone_id


def make_observation(building_model):
    zone_observations = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        zone_observations[zone_id] = ZoneObservation(
            zone_id=zone_id,
            zone_name=getattr(zone_model, "zone_name", zone_id),
            indoor_temp=20.0,
            co2_ppm=600.0,
            indoor_daylight=0.5,
            indoor_noise=0.2,
        )

        # Also add simple aliases so the agent/action side can still resolve
        # spaces like "living_room", "kitchen", "bathroom", etc.
        alias = simple_zone_id(zone_id)

        if alias not in zone_observations:
            zone_observations[alias] = ZoneObservation(
                zone_id=alias,
                zone_name=alias,
                indoor_temp=20.0,
                co2_ppm=600.0,
                indoor_daylight=0.5,
                indoor_noise=0.2,
            )

    return DwellingObservation(
        indoor_temp=20.0,
        outdoor_temp=10.0,
        co2_ppm=600.0,
        indoor_daylight=0.5,
        indoor_noise=0.2,
        electricity_tariff=0.25,
        default_zone_id="living_room",
        zone_observations=zone_observations,
    )


def make_people():
    return {
        "person_1": PersonState(
            occupant_id="person_1",
            household_id="household_1",
            can_act=True,
            can_cook=True,
            authority_weight=1.0,
            has_job=False,
            has_school=False,
            age_group="adult",
            care_dependency=0.0,
            laundry_generation_rate=0.012,
            idle_movement_profile="normal",
            mobility_tendency=1.0,
            hunger=0.25,
            fatigue=0.10,
            sleep_pressure=0.10,
            sickness_severity=0.0,
            is_home=True,
            is_sleeping=False,
            away_reason="none",
            base_laziness=0.20,
            money_sensitivity=0.40,
            comfort_sensitivity=0.70,
            future_awareness=0.60,
            current_zone_id="living_room",
            default_zone_id="living_room",
            assigned_idle_zone_id="living_room",
            assigned_sleep_zone_id="bedroom_1",
            assigned_work_zone_id="office",
            is_main_cook=True,
            cooking_priority=1,
        )
    }


def make_locations():
    return {
        "person_1": OccupantLocation(
            occupant_id="person_1",
            dwelling_id="dwelling_1",
            building_id="dummy_building_1",
            is_home=True,
            current_space_id="living_room",
            current_space_role="living_room",
            current_activity="idle",
            away_reason="none",
            minutes_since_last_space_change=999.0,
        )
    }


def make_assignments():
    return {
        "person_1": SpaceAssignment(
            occupant_id="person_1",
            dwelling_id="dwelling_1",
            building_id="dummy_building_1",
            default_space_id="living_room",
            role_to_space_id={
                "idle": "living_room",
                "living_room": "living_room",
                "sleep": "bedroom_1",
                "bedroom": "bedroom_1",
                "work": "office",
                "schoolwork": "office",
                "kitchen": "kitchen",
                "bathroom": "bathroom",
                "laundry": "laundry",
                "entrance": "entrance",
                "door": "entrance",
                "care": "living_room",
                "outside": "outside",
            },
        )
    }


def make_household():
    return HouseholdState(
        household_id="household_1",
        occupant_ids=["person_1"],
        main_cook_id="person_1",
        cooking_priority_by_occupant={"person_1": 1},
        laundry_priority_by_occupant={"person_1": 1},
    )


def make_manual_chunk_records():
    return [
        {
            "total_power_w": 1560.0,
            "total_energy_wh": 1060.0,
            "power_breakdown": [
                {
                    "name": "turn_lights_on",
                    "actor_id": "person_1",
                    "target_space_id": "dwelling_1_living_room",
                    "target_zone_role": "living_room",
                    "minutes": 1.0,
                    "power_w": 0.0,
                    "energy_wh": 0.0,
                },
                {
                    "name": "turn_heating_on",
                    "actor_id": "person_1",
                    "target_space_id": "dwelling_1_living_room",
                    "target_zone_role": "living_room",
                    "minutes": 1.0,
                    "power_w": 0.0,
                    "energy_wh": 0.0,
                },
                {
                    "name": "cook",
                    "actor_id": "person_1",
                    "target_space_id": "",
                    "target_zone_role": "kitchen",
                    "minutes": 30.0,
                    "power_w": 1000.0,
                    "energy_wh": 500.0,
                },
                {
                    "name": "shower",
                    "actor_id": "person_1",
                    "target_space_id": "",
                    "target_zone_role": "bathroom",
                    "minutes": 10.0,
                    "power_w": 0.0,
                    "energy_wh": 0.0,
                },
                {
                    "name": "run_washing_machine",
                    "actor_id": "person_1",
                    "target_space_id": "",
                    "target_zone_role": "laundry",
                    "minutes": 60.0,
                    "power_w": 500.0,
                    "energy_wh": 500.0,
                },
                {
                    "name": "use_laptop",
                    "actor_id": "person_1",
                    "target_space_id": "",
                    "target_zone_role": "work",
                    "minutes": 60.0,
                    "power_w": 60.0,
                    "energy_wh": 60.0,
                },
            ],
        }
    ]


def require_phase_9_13_runner_patches(sim):
    required_attrs = [
        "building_internal_source_records",
        "building_internal_source_zone_records",
        "building_internal_source_building_records",
        "last_internal_source_result",
    ]

    required_methods = [
        "_store_building_internal_source_outputs",
        "building_internal_source_records_to_dataframe",
        "building_internal_source_zone_records_to_dataframe",
        "building_internal_source_building_records_to_dataframe",
    ]

    missing = []

    for name in required_attrs:
        if not hasattr(sim, name):
            missing.append(name)

    for name in required_methods:
        if not hasattr(sim, name):
            missing.append(name + "()")

    if missing:
        raise AssertionError(
            "Missing Phase 9.13 runner patches:\n"
            + "\n".join(" - " + name for name in missing)
        )


def make_real_sim():
    config_path = find_config_path()

    building_model = make_default_family_building()
    building_performance_model = SimpleBuildingPerformanceModel(
        building_model=building_model,
    )

    sim = AbbeySimulation.initialize(
        config_path=config_path,
        duration_hours=2.0,
        dt_minutes=60.0,
        people=make_people(),
        locations=make_locations(),
        assignments=make_assignments(),
        household=make_household(),
        observation=make_observation(building_model),
        systems=SystemState(default_space_id="living_room"),
        execution=ExecutionState(),
        cooldowns=CooldownState(),
        use_household_execution=False,
        building_model=building_model,
        building_performance_model=building_performance_model,
        use_building_performance=True,
        random_seed=42,
    )

    require_phase_9_13_runner_patches(sim)

    return sim


def assert_action_source(source_df, action_name, expected_zone_id):
    rows = source_df[source_df["action_name"] == action_name]

    assert not rows.empty, "Missing internal source action row: " + action_name

    actual_zone_ids = set(rows["zone_id"].astype(str).tolist())

    assert expected_zone_id in actual_zone_ids, (
        "Action "
        + action_name
        + " did not resolve to "
        + expected_zone_id
        + ". Got: "
        + str(actual_zone_ids)
    )


def main():
    sim = make_real_sim()

    chunk_records = make_manual_chunk_records()

    sim._run_building_performance_if_enabled(
        chunk_records=chunk_records,
        action_energy_wh={
            # Must be ignored after 9.12.
            "fake_legacy_energy": 999999.0,
        },
    )

    assert sim.last_internal_source_result is not None

    source_df = sim.building_internal_source_records_to_dataframe()
    zone_df = sim.building_internal_source_zone_records_to_dataframe()
    building_df = sim.building_internal_source_building_records_to_dataframe()
    building_zone_df = sim.building_zone_records_to_dataframe()
    building_main_df = sim.building_records_to_dataframe()

    assert not source_df.empty
    assert not zone_df.empty
    assert not building_df.empty
    assert not building_zone_df.empty
    assert not building_main_df.empty

    assert_action_source(source_df, "cook", "dwelling_1_kitchen")
    assert_action_source(source_df, "shower", "dwelling_1_bathroom")
    assert_action_source(source_df, "run_washing_machine", "dwelling_1_laundry")
    assert_action_source(source_df, "use_laptop", "dwelling_1_office")

    source_kinds = set(source_df["source_kind"].astype(str).tolist())

    assert INTERNAL_SOURCE_KIND_PERSON in source_kinds
    assert INTERNAL_SOURCE_KIND_APPLIANCE in source_kinds
    assert INTERNAL_SOURCE_KIND_ACTIVITY in source_kinds

    # These two depend on the Phase 9.11 control bridge wiring.
    assert INTERNAL_SOURCE_KIND_LIGHTING in source_kinds, (
        "No lighting source was logged. "
        "Check turn_lights_on -> control bridge -> ZoneControlCommand -> internal_sources."
    )

    assert INTERNAL_SOURCE_KIND_HVAC in source_kinds, (
        "No HVAC source was logged. "
        "Check turn_heating_on -> control bridge -> ZoneControlCommand -> internal_sources."
    )

    kitchen_zone_rows = zone_df[zone_df["zone_id"] == "dwelling_1_kitchen"]
    bathroom_zone_rows = zone_df[zone_df["zone_id"] == "dwelling_1_bathroom"]
    laundry_zone_rows = zone_df[zone_df["zone_id"] == "dwelling_1_laundry"]
    living_zone_rows = zone_df[zone_df["zone_id"] == "dwelling_1_living_room"]

    assert not kitchen_zone_rows.empty
    assert not bathroom_zone_rows.empty
    assert not laundry_zone_rows.empty
    assert not living_zone_rows.empty

    assert kitchen_zone_rows.iloc[-1]["average_sensible_heat_w"] > 0.0
    assert kitchen_zone_rows.iloc[-1]["average_moisture_generation_kg_h"] > 0.0

    assert bathroom_zone_rows.iloc[-1]["average_moisture_generation_kg_h"] > 0.0
    assert laundry_zone_rows.iloc[-1]["average_sensible_heat_w"] > 0.0
    assert living_zone_rows.iloc[-1]["average_co2_generation_m3_h"] > 0.0

    latest_building_row = building_df.iloc[-1]

    assert latest_building_row["record_count"] > 0
    assert latest_building_row["total_electricity_wh"] > 0.0
    assert latest_building_row["total_average_sensible_heat_w"] != 0.0
    assert latest_building_row["total_co2_generation_m3_h"] > 0.0
    assert latest_building_row["total_moisture_generation_kg"] > 0.0

    latest_kitchen_performance = building_zone_df[
        building_zone_df["zone_id"] == "dwelling_1_kitchen"
    ].iloc[-1]

    assert "internal_average_sensible_heat_w" in building_zone_df.columns
    assert "internal_average_moisture_generation_kg_h" in building_zone_df.columns
    assert latest_kitchen_performance["internal_average_sensible_heat_w"] > 0.0
    assert latest_kitchen_performance["internal_average_moisture_generation_kg_h"] > 0.0

    # Now run one actual sim.step(), not manually injected.
    # This checks the full runner logger path does not break.
    logger_records_before = len(sim.logger.records)

    sim.step()

    assert len(sim.logger.records) == logger_records_before + 1

    latest_logger_record = sim.logger.records[-1]

    assert "internal_source_record_count" in latest_logger_record
    assert latest_logger_record["internal_source_record_count"] > 0

    assert len(sim.building_internal_source_records) > len(source_df)
    assert len(sim.building_internal_source_zone_records) > len(zone_df)
    assert len(sim.building_internal_source_building_records) > len(building_df)

    print("OK: real AbbeySimulation initializes with building performance enabled")
    print("OK: real runner building-performance hook accepts execution chunk_records")
    print("OK: internal source result is stored on sim.last_internal_source_result")
    print("OK: long internal source records are logged")
    print("OK: zone internal source aggregates are logged")
    print("OK: building internal source aggregates are logged")
    print("OK: cook resolves to kitchen")
    print("OK: shower resolves to bathroom")
    print("OK: washing machine resolves to laundry")
    print("OK: laptop resolves to office")
    print("OK: people source is present")
    print("OK: appliance source is present")
    print("OK: activity source is present")
    print("OK: lighting source is present")
    print("OK: HVAC source is present")
    print("OK: building zone records include internal-source diagnostics")
    print("OK: one real sim.step() runs and logger receives internal-source summary")
    print("")
    print("PHASE 9.14 REAL ABBEYSIMULATION TIMESTEP INTEGRATION TEST OK ✅")


if __name__ == "__main__":
    main()