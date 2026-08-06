"""
ABBEY Phase 17.2 test.

Goal:
    Formalize building-performance input contract:
    weather, states, occupancy, actions, controls, and systems reach the engine.

Run:
    python -m pytest tests/phase17/test_17_2_performance_input_contract.py

Provenance:
    adapted from surviving script
    `run_test_phase_17_2_performance_input_contract.py` at frozen HEAD
    7d2729173146536771935ffa92eabaa3c4000c53.
"""

from pathlib import Path
from datetime import datetime

from nexusep.abbey.building import (
    BuildingPhysicsPerformanceModel,
)
from nexusep.abbey.building.physics.weather import WeatherState
from nexusep.abbey.simulation.runner import AbbeySimulation

from tests.phase16.test_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_graph,
    make_phase16_performance_input,
    assert_true,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "nexusep"
    / "data"
    / "abbey"
    / "config"
    / "abbey_config.jsonc"
)


TARGET_ZONE_ID = "dwelling_1_kitchen"


def make_explicit_weather():
    return WeatherState(
        datetime=datetime(2026, 1, 1, 8, 0, 0),
        outdoor_temperature_c=3.5,
        wind_speed_m_s=2.0,
        wind_direction_deg=180.0,
        direct_normal_radiation_w_m2=450.0,
        diffuse_horizontal_radiation_w_m2=80.0,
        global_horizontal_radiation_w_m2=380.0,
        outdoor_illuminance_lux=42000.0,
        outdoor_co2_ppm=415.0,
        outdoor_noise_db=47.0,
        relative_humidity_percent=65.0,
        atmospheric_pressure_pa=101000.0,
        sky_condition="clear",
    )


def make_person_and_location():
    people = {
        "person_1": {
            "person_id": "person_1",
        }
    }

    locations = {
        "person_1": {
            "is_home": True,
            "current_space_id": TARGET_ZONE_ID,
            "current_activity": "cooking",
        }
    }

    return people, locations


def make_cooking_chunk():
    return {
        "chunk_index": 0,
        "minutes": 10.0,
        "power_breakdown": [
            {
                "name": "cook",
                "actor_id": "person_1",
                "target_space_id": TARGET_ZONE_ID,
                "target_zone_role": "kitchen",
                "minutes": 10.0,
                "power_w": 1000.0,
            }
        ],
    }


def run_contract_case(
    weather_state=None,
    observation=None,
    people=None,
    locations=None,
    chunk_records=None,
):
    building = make_phase16_building()
    graph = make_phase16_graph(building)

    model = BuildingPhysicsPerformanceModel(
        building_model=building,
        physics_graph=graph,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
    )

    performance_input = make_phase16_performance_input(
        building=building,
        graph=graph,
        weather_state=weather_state,
        step=0,
        day=0,
        hour=8.0,
        locations=locations or {},
        people=people or {},
        chunk_records=chunk_records or [],
    )

    if observation is not None:
        performance_input["observation"] = observation

    if weather_state is None:
        performance_input.pop("weather_state", None)

    result = model.step(
        performance_input=performance_input,
        dt_minutes=10.0,
    )

    return {
        "building": building,
        "graph": graph,
        "model": model,
        "result": result,
    }


def test_explicit_weather_state_is_passed_through_unchanged():
    weather = make_explicit_weather()

    out = run_contract_case(
        weather_state=weather,
    )

    result = out["result"]

    assert_true(
        result.weather_state is weather,
        "BuildingPerformanceStepResult should keep the explicit WeatherState object.",
    )

    assert_true(
        result.weather_source == "weather_state_explicit",
        "Explicit weather should use weather_source='weather_state_explicit'.",
    )

    assert_true(
        result.physics_engine_result.step_input.weather_state is weather,
        "BuildingPhysicsStepInput should receive the exact explicit WeatherState object.",
    )

    building_record = result.building_record

    assert_true(
        building_record["weather_source"] == "weather_state_explicit",
        "Building record should expose explicit weather source.",
    )

    assert_true(
        float(building_record["weather_outdoor_temperature_c"]) == 3.5,
        "Building record should expose explicit outdoor temperature.",
    )

    print("PASS: test_explicit_weather_state_is_passed_through_unchanged")


def test_missing_weather_creates_safe_synthetic_weather():
    out = run_contract_case(
        weather_state=None,
    )

    result = out["result"]
    weather_state = result.weather_state

    assert_true(
        weather_state is not None,
        "Missing weather should create safe synthetic WeatherState.",
    )

    assert_true(
        result.weather_source in [
            "weather_from_observation",
            "weather_default_synthetic",
        ],
        "Missing explicit weather should use a labelled fallback weather source.",
    )

    assert_true(
        result.physics_engine_result.step_input.weather_state is weather_state,
        "Synthetic WeatherState should be passed into BuildingPhysicsStepInput.",
    )

    assert_true(
        hasattr(weather_state, "outdoor_temperature_c"),
        "Synthetic weather should expose outdoor_temperature_c.",
    )

    assert_true(
        hasattr(weather_state, "relative_humidity_percent"),
        "Synthetic weather should expose relative_humidity_percent.",
    )

    print("PASS: test_missing_weather_creates_safe_synthetic_weather")


def test_people_and_locations_reach_internal_sources():
    weather = make_explicit_weather()
    people, locations = make_person_and_location()

    out = run_contract_case(
        weather_state=weather,
        people=people,
        locations=locations,
        chunk_records=[],
    )

    result = out["result"]
    step_input = result.physics_engine_result.step_input

    assert_true(
        step_input.people == people,
        "BuildingPhysicsStepInput should receive people.",
    )

    assert_true(
        step_input.locations == locations,
        "BuildingPhysicsStepInput should receive locations.",
    )

    assert_true(
        result.internal_source_result is not None,
        "Internal source result should exist.",
    )

    assert_true(
        len(result.internal_source_result.records) > 0,
        "People/locations should create occupant internal source records.",
    )

    zone_records = [
        row for row in result.zone_records
        if row.get("zone_id") == TARGET_ZONE_ID
    ]

    assert_true(
        len(zone_records) == 1,
        "Target zone should have one zone record.",
    )

    row = zone_records[0]

    assert_true(
        float(row.get("internal_average_sensible_heat_w", 0.0)) > 0.0,
        "Target zone should receive sensible heat from occupant.",
    )

    print("PASS: test_people_and_locations_reach_internal_sources")


def test_chunk_records_reach_internal_sources():
    weather = make_explicit_weather()
    people, locations = make_person_and_location()
    cooking_chunk = make_cooking_chunk()

    out = run_contract_case(
        weather_state=weather,
        people=people,
        locations=locations,
        chunk_records=[cooking_chunk],
    )

    result = out["result"]
    step_input = result.physics_engine_result.step_input

    assert_true(
        step_input.chunk_records == [cooking_chunk],
        "BuildingPhysicsStepInput should receive chunk_records.",
    )

    assert_true(
        result.internal_source_result is not None,
        "Internal source result should exist.",
    )

    zone_records = [
        row for row in result.zone_records
        if row.get("zone_id") == TARGET_ZONE_ID
    ]

    row = zone_records[0]

    assert_true(
        float(row.get("appliance_energy_wh", 0.0)) > 0.0,
        "Cooking chunk should create appliance energy.",
    )

    assert_true(
        float(row.get("internal_electricity_wh", 0.0)) > 0.0,
        "Cooking chunk should create internal electricity.",
    )

    print("PASS: test_chunk_records_reach_internal_sources")


def test_controls_and_systems_reach_building_physics_step_input():
    weather = make_explicit_weather()

    out = run_contract_case(
        weather_state=weather,
    )

    result = out["result"]
    step_input = result.physics_engine_result.step_input

    zone_ids = out["building"].all_zone_ids()

    assert_true(
        len(step_input.zone_control_commands) == len(zone_ids),
        "BuildingPhysicsStepInput should receive one ZoneControlCommand per zone.",
    )

    assert_true(
        len(step_input.zone_system_specs) == len(zone_ids),
        "BuildingPhysicsStepInput should receive one ZoneSystemSpec per zone.",
    )

    first_zone = zone_ids[0]

    assert_true(
        first_zone in step_input.zone_control_commands,
        "First zone missing from zone_control_commands.",
    )

    assert_true(
        first_zone in step_input.zone_system_specs,
        "First zone missing from zone_system_specs.",
    )

    print("PASS: test_controls_and_systems_reach_building_physics_step_input")


class StaticWeatherProvider:
    def __init__(self, weather_state):
        self.weather_state = weather_state
        self.requested_steps = []

    def get_state_by_step(self, step_index):
        self.requested_steps.append(int(step_index))
        return self.weather_state


def test_runner_passes_weather_state_when_provider_available():
    weather = make_explicit_weather()
    provider = StaticWeatherProvider(weather)

    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.1,
        dt_minutes=1.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
        weather_provider=provider,
    )

    assert_true(
        sim.weather_provider is provider,
        "Runner should store weather_provider passed to initialize().",
    )

    assert_true(
        sim.weather_state is None,
        "Runner static weather_state should be None in provider test.",
    )

    sim.step()

    assert_true(
        provider.requested_steps == [0],
        "Runner should request weather for clock step 0.",
    )

    assert_true(
        len(sim.building_records) > 0,
        "Runner should produce building record.",
    )

    building_record = sim.building_records[-1]

    assert_true(
        building_record["weather_source"] == "weather_state_explicit",
        "Runner-provided weather should be labelled explicit.",
    )

    assert_true(
        float(building_record["weather_outdoor_temperature_c"]) == 3.5,
        "Runner-provided weather should reach building record.",
    )

    print("PASS: test_runner_passes_weather_state_when_provider_available")


def main():
    test_explicit_weather_state_is_passed_through_unchanged()
    test_missing_weather_creates_safe_synthetic_weather()
    test_people_and_locations_reach_internal_sources()
    test_chunk_records_reach_internal_sources()
    test_controls_and_systems_reach_building_physics_step_input()
    test_runner_passes_weather_state_when_provider_available()

    print("Phase 17.2 performance input contract tests passed.")


if __name__ == "__main__":
    main()
