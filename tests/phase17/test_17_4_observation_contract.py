"""
ABBEY Phase 17.4 test.

Goal:
    Make sure engine-updated building states become agent-facing observations.

Run:
    python -m pytest tests/phase17/test_17_4_observation_contract.py

Provenance:
    adapted from surviving script `run_test_phase_17_4_observation_contract.py`
    at frozen HEAD 7d2729173146536771935ffa92eabaa3c4000c53.
"""

from pathlib import Path
import math

from nexusep.abbey.agents.states import (
    DwellingObservation,
    ZoneObservation,
)
from nexusep.abbey.agents.location import OccupantLocation
from nexusep.abbey.agents.perception import update_perception
from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.abbey.building import BuildingPhysicsPerformanceModel

from tests.phase16.test_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_graph,
    make_phase16_weather,
    make_phase16_performance_input,
    phase16_zone_ids,
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


LIVING_ZONE_ID = "dwelling_1_living_room"
KITCHEN_ZONE_ID = "dwelling_1_kitchen"


def assert_close(value, expected, tolerance, message):
    residual = abs(float(value) - float(expected))

    if residual > float(tolerance):
        raise AssertionError(
            message
            + " value="
            + str(value)
            + ", expected="
            + str(expected)
            + ", residual="
            + str(residual)
        )


def set_zone_state(
    building,
    zone_id,
    indoor_temp_c=20.0,
    co2_ppm=600.0,
    indoor_daylight=0.5,
    indoor_noise=0.2,
    relative_humidity_percent=50.0,
    humidity_ratio_kg_kg=0.008,
):
    state = building.get_zone_state(zone_id)

    building.set_zone_state(
        zone_id,
        state.copy(
            indoor_temp_c=float(indoor_temp_c),
            indoor_mass_temp_c=float(indoor_temp_c),
            co2_ppm=float(co2_ppm),
            indoor_daylight=float(indoor_daylight),
            indoor_noise=float(indoor_noise),
            indoor_relative_humidity_percent=float(relative_humidity_percent),
            indoor_humidity_ratio_kg_kg=float(humidity_ratio_kg_kg),
        ),
    )


def make_person_and_location(zone_id):
    people = {
        "person_1": {
            "person_id": "person_1",
        }
    }

    locations = {
        "person_1": {
            "is_home": True,
            "current_space_id": zone_id,
            "current_activity": "idle",
        }
    }

    return people, locations


def run_direct_observation_case(
    default_zone_id=LIVING_ZONE_ID,
    occupied_zone_id=KITCHEN_ZONE_ID,
):
    building = make_phase16_building()
    graph = make_phase16_graph(building)

    for zone_id in phase16_zone_ids(building):
        set_zone_state(
            building=building,
            zone_id=zone_id,
            indoor_temp_c=21.0,
            co2_ppm=600.0,
            indoor_daylight=0.4,
            indoor_noise=0.2,
            relative_humidity_percent=50.0,
            humidity_ratio_kg_kg=0.008,
        )

    set_zone_state(
        building=building,
        zone_id=default_zone_id,
        indoor_temp_c=23.0,
        co2_ppm=850.0,
        indoor_daylight=0.7,
        indoor_noise=0.3,
        relative_humidity_percent=48.0,
        humidity_ratio_kg_kg=0.0075,
    )

    people, locations = make_person_and_location(occupied_zone_id)

    weather = make_phase16_weather(
        outdoor_temperature_c=5.0,
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        relative_humidity_percent=60.0,
    )

    previous_observation = DwellingObservation(
        indoor_temp=20.0,
        outdoor_temp=10.0,
        co2_ppm=600.0,
        indoor_daylight=0.5,
        indoor_noise=0.2,
        default_zone_id=default_zone_id,
        zone_observations={
            default_zone_id: ZoneObservation(
                zone_id=default_zone_id,
                zone_name=default_zone_id,
                indoor_temp=20.0,
                co2_ppm=600.0,
                indoor_daylight=0.5,
                indoor_noise=0.2,
            )
        },
    )

    model = BuildingPhysicsPerformanceModel(
        building_model=building,
        physics_graph=graph,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
    )

    performance_input = make_phase16_performance_input(
        building=building,
        graph=graph,
        weather_state=weather,
        step=0,
        day=0,
        hour=0.0,
        locations=locations,
        people=people,
        chunk_records=[],
    )

    performance_input["observation"] = previous_observation

    result = model.step(
        performance_input=performance_input,
        dt_minutes=10.0,
    )

    return {
        "building": building,
        "graph": graph,
        "weather": weather,
        "model": model,
        "result": result,
        "people": people,
        "locations": locations,
        "previous_observation": previous_observation,
    }


def test_engine_updated_zone_states_become_zone_observations():
    out = run_direct_observation_case()
    building = out["building"]
    observation = out["result"].observation

    assert_true(
        len(observation.zone_observations) == len(phase16_zone_ids(building)),
        "Observation should contain one ZoneObservation per building zone.",
    )

    for zone_id in phase16_zone_ids(building):
        state = building.get_zone_state(zone_id)
        zone_obs = observation.get_zone(zone_id)

        assert_true(
            isinstance(zone_obs, ZoneObservation),
            "Observation for " + str(zone_id) + " should be ZoneObservation.",
        )

        assert_close(
            zone_obs.indoor_temp,
            state.indoor_temp_c,
            1e-9,
            "ZoneObservation indoor_temp should match BuildingModel state for "
            + str(zone_id),
        )

        assert_close(
            zone_obs.co2_ppm,
            state.co2_ppm,
            1e-9,
            "ZoneObservation co2_ppm should match BuildingModel state for "
            + str(zone_id),
        )

        assert_close(
            zone_obs.indoor_daylight,
            state.indoor_daylight,
            1e-9,
            "ZoneObservation indoor_daylight should match BuildingModel state for "
            + str(zone_id),
        )

        assert_close(
            zone_obs.indoor_noise,
            state.indoor_noise,
            1e-9,
            "ZoneObservation indoor_noise should match BuildingModel state for "
            + str(zone_id),
        )

        assert_close(
            zone_obs.indoor_relative_humidity_percent,
            state.indoor_relative_humidity_percent,
            1e-9,
            "ZoneObservation relative humidity should match BuildingModel state for "
            + str(zone_id),
        )

        assert_close(
            zone_obs.indoor_humidity_ratio_kg_kg,
            state.indoor_humidity_ratio_kg_kg,
            1e-12,
            "ZoneObservation humidity ratio should match BuildingModel state for "
            + str(zone_id),
        )

    print("PASS: test_engine_updated_zone_states_become_zone_observations")


def test_dwelling_observation_default_zone_remains_stable():
    out = run_direct_observation_case(
        default_zone_id=KITCHEN_ZONE_ID,
        occupied_zone_id=KITCHEN_ZONE_ID,
    )

    observation = out["result"].observation

    assert_true(
        observation.default_zone_id == KITCHEN_ZONE_ID,
        "Previous valid default_zone_id should remain stable.",
    )

    default_zone = observation.get_zone(observation.default_zone_id)

    assert_close(
        observation.indoor_temp,
        default_zone.indoor_temp,
        1e-9,
        "Dwelling scalar indoor_temp should match default zone.",
    )

    assert_close(
        observation.co2_ppm,
        default_zone.co2_ppm,
        1e-9,
        "Dwelling scalar co2_ppm should match default zone.",
    )

    print("PASS: test_dwelling_observation_default_zone_remains_stable")


def test_observation_contains_control_and_occupancy_fields():
    out = run_direct_observation_case()
    result = out["result"]
    observation = result.observation

    for zone_id, command in result.zone_control_commands.items():
        zone_obs = observation.get_zone(zone_id)

        assert_true(
            zone_obs.heating_on == bool(command.heating_on),
            "Observation heating_on should match command for " + str(zone_id),
        )

        assert_true(
            zone_obs.cooling_on == bool(command.cooling_on),
            "Observation cooling_on should match command for " + str(zone_id),
        )

        assert_true(
            zone_obs.lights_on == bool(command.lights_on),
            "Observation lights_on should match command for " + str(zone_id),
        )

        assert_true(
            zone_obs.window_open == bool(command.window_open),
            "Observation window_open should match command for " + str(zone_id),
        )

        assert_true(
            zone_obs.curtain_open == bool(command.curtain_open),
            "Observation curtain_open should match command for " + str(zone_id),
        )

        assert_true(
            hasattr(zone_obs, "occupied_person_ids"),
            "Observation should expose occupied_person_ids for " + str(zone_id),
        )

        assert_true(
            hasattr(zone_obs, "number_of_people"),
            "Observation should expose number_of_people for " + str(zone_id),
        )

    kitchen_obs = observation.get_zone(KITCHEN_ZONE_ID)

    assert_true(
        kitchen_obs.number_of_people == 1,
        "Occupied kitchen should expose number_of_people=1.",
    )

    assert_true(
        "person_1" in kitchen_obs.occupied_person_ids,
        "Occupied kitchen should expose person_1 in occupied_person_ids.",
    )

    print("PASS: test_observation_contains_control_and_occupancy_fields")


def test_observation_get_zone_resolves_simple_and_dwelling_aware_ids():
    out = run_direct_observation_case()
    observation = out["result"].observation

    living_dwelling = observation.get_zone("dwelling_1_living_room")
    living_simple = observation.get_zone("living_room")
    living_legacy = observation.get_zone("main_room")

    assert_true(
        living_dwelling.zone_id == LIVING_ZONE_ID,
        "Dwelling-aware living room lookup should resolve.",
    )

    assert_true(
        living_simple.zone_id == LIVING_ZONE_ID,
        "Simple living_room lookup should resolve dwelling-aware observation.",
    )

    assert_true(
        living_legacy.zone_id == LIVING_ZONE_ID,
        "Legacy main_room lookup should resolve dwelling-aware observation.",
    )

    kitchen_dwelling = observation.get_zone("dwelling_1_kitchen")
    kitchen_simple = observation.get_zone("kitchen")

    assert_true(
        kitchen_dwelling.zone_id == KITCHEN_ZONE_ID,
        "Dwelling-aware kitchen lookup should resolve.",
    )

    assert_true(
        kitchen_simple.zone_id == KITCHEN_ZONE_ID,
        "Simple kitchen lookup should resolve dwelling-aware observation.",
    )

    print("PASS: test_observation_get_zone_resolves_simple_and_dwelling_aware_ids")


def test_runner_observation_and_systems_are_updated_after_one_step():
    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.1,
        dt_minutes=1.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
    )

    sim.step()

    assert_true(
        sim.observation is not None,
        "After one step, sim.observation should not be None.",
    )

    assert_true(
        len(sim.observation.zone_observations) == len(sim.building_model.all_zone_ids()),
        "After one step, observation should contain all building zones.",
    )

    assert_true(
        sim.observation.default_zone_id in sim.observation.zone_observations,
        "Observation default_zone_id should be a valid zone_observations key.",
    )

    default_zone = sim.observation.get_zone(sim.observation.default_zone_id)
    default_controls = sim.systems.get_space_controls(
        sim.observation.default_zone_id
    )

    assert_true(
        default_controls.heating_on == default_zone.heating_on,
        "SystemState heating_on should match default ZoneObservation.",
    )

    assert_true(
        default_controls.cooling_on == default_zone.cooling_on,
        "SystemState cooling_on should match default ZoneObservation.",
    )

    assert_true(
        default_controls.mechanical_ventilation_on
        == default_zone.mechanical_ventilation_on,
        "SystemState mechanical_ventilation_on should match default ZoneObservation.",
    )

    assert_true(
        default_controls.lights_on == default_zone.lights_on,
        "SystemState lights_on should match default ZoneObservation.",
    )

    assert_true(
        default_controls.window_open == default_zone.window_open,
        "SystemState window_open should match default ZoneObservation.",
    )

    assert_true(
        default_controls.curtain_closed == (not default_zone.curtain_open),
        "SystemState curtain_closed should match inverse of ZoneObservation curtain_open.",
    )

    assert_true(
        sim.systems.default_space_id == sim.observation.default_zone_id,
        "SystemState default_space_id should match observation default_zone_id.",
    )

    print("PASS: test_runner_observation_and_systems_are_updated_after_one_step")


def test_agent_perception_reads_updated_observation_next_step():
    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.1,
        dt_minutes=1.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
    )

    sim.step()

    default_zone_id = sim.observation.default_zone_id

    sim.location = sim.location.copy(
        is_home=True,
        current_space_id=default_zone_id,
        current_space_role="idle",
        current_activity="idle",
    )

    sim.person = sim.person.copy(
        is_home=True,
        away_reason="none",
    )

    zone = sim.observation.get_zone(sim.location.current_space_id)
    state = sim.building_model.get_zone_state(default_zone_id)

    assert_close(
        zone.indoor_temp,
        state.indoor_temp_c,
        1e-9,
        "Agent-facing observation should expose engine-updated indoor temp.",
    )

    assert_close(
        zone.co2_ppm,
        state.co2_ppm,
        1e-9,
        "Agent-facing observation should expose engine-updated CO2.",
    )

    updated_person = update_perception(
        person=sim.person,
        observation=sim.observation,
        systems=sim.systems,
        location=sim.location,
        clock=sim.clock,
        config=sim.config,
    )

    assert_true(
        math.isfinite(float(updated_person.thermal_sensation)),
        "Agent perception should read updated observation and produce finite thermal_sensation.",
    )

    assert_true(
        0.0 <= float(updated_person.air_quality_discomfort) <= 1.0,
        "Agent perception should produce bounded air_quality_discomfort.",
    )

    assert_true(
        0.0 <= float(updated_person.visual_discomfort) <= 1.0,
        "Agent perception should produce bounded visual_discomfort.",
    )

    assert_true(
        0.0 <= float(updated_person.acoustic_discomfort) <= 1.0,
        "Agent perception should produce bounded acoustic_discomfort.",
    )

    print("PASS: test_agent_perception_reads_updated_observation_next_step")


def main():
    test_engine_updated_zone_states_become_zone_observations()
    test_dwelling_observation_default_zone_remains_stable()
    test_observation_contains_control_and_occupancy_fields()
    test_observation_get_zone_resolves_simple_and_dwelling_aware_ids()
    test_runner_observation_and_systems_are_updated_after_one_step()
    test_agent_perception_reads_updated_observation_next_step()

    print("Phase 17.4 observation contract tests passed.")


if __name__ == "__main__":
    main()
