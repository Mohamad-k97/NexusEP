"""
ABBEY Phase 4 thermal architecture test.

Tests:
1. One zone, no gains, no HVAC -> temperature drifts toward outside.
2. One zone, heating active -> temperature rises.
3. Two zones, one hot and one cold -> temperatures move toward each other.
4. Window solar gain -> temperature rises during daytime.
5. No non-thermal building physics is calculated.

Expected:
    PHASE 4 THERMAL ARCHITECTURE OK ✅
"""

from datetime import datetime as DateTime
from types import SimpleNamespace

from nexusep.abbey.building.model import (
    BuildingModel,
    DwellingModel,
    ZoneModel,
)

from nexusep.abbey.building.physics.graph import (
    BuildingPhysicsGraph,
    BoundaryConnection,
    ZoneConnection,
)

from nexusep.abbey.building.physics.weather import WeatherState

from nexusep.abbey.building.physics.thermal import (
    ThermalModel,
    ThermalStepResult,
)


DT_MINUTES = 15.0


def make_zone(
    zone_id,
    initial_temp_c,
    external_wall_area_m2=20.0,
    internal_wall_area_m2=0.0,
    floor_area_m2=20.0,
):
    return ZoneModel(
        zone_id=zone_id,
        zone_name=zone_id,
        dwelling_id="dwelling_1",
        building_id="building_1",
        zone_scope="private",
        zone_use="generic",
        floor_area_m2=floor_area_m2,
        height_m=2.7,
        volume_m3=floor_area_m2 * 2.7,
        air_volume_m3=floor_area_m2 * 2.7,
        air_heat_capacity_j_k=30000.0,
        internal_heat_capacity_j_k=500000.0,
        external_wall_area_m2=external_wall_area_m2,
        internal_wall_area_m2=internal_wall_area_m2,
        u_value_external_wall_w_m2k=1.2,
        u_value_internal_wall_w_m2k=1.8,
        thermal_bridge_factor=1.0,
        default_infiltration_ach=0.0,
        initial_air_temperature_c=initial_temp_c,
        initial_mass_temperature_c=initial_temp_c,
        initial_temp_c=initial_temp_c,
        initial_co2_ppm=600.0,
    )


def make_building(zone_models):
    dwelling = DwellingModel(
        dwelling_id="dwelling_1",
        building_id="building_1",
        household_id="household_1",
        private_zone_ids=list(zone_models.keys()),
        zone_models=zone_models,
    )

    return BuildingModel(
        building_id="building_1",
        dwelling_ids=["dwelling_1"],
        dwellings={
            "dwelling_1": dwelling,
        },
    )


def make_zone_connection(
    connection_id,
    zone_a_id,
    zone_b_id,
    area_m2,
    u_value_w_m2k,
):
    """
    Compatibility helper.

    Your graph.py uses from_zone_id/to_zone_id.
    Some thermal code may expect zone_a_id/zone_b_id.
    We set both aliases safely.
    """

    try:
        connection = ZoneConnection(
            connection_id=connection_id,
            from_zone_id=zone_a_id,
            to_zone_id=zone_b_id,
            connection_type="internal_wall",
            area_m2=area_m2,
        )
    except TypeError:
        connection = ZoneConnection(
            connection_id=connection_id,
            zone_a_id=zone_a_id,
            zone_b_id=zone_b_id,
            connection_type="internal_wall",
            area_m2=area_m2,
        )

    connection.zone_a_id = zone_a_id
    connection.zone_b_id = zone_b_id
    connection.u_value_w_m2k = u_value_w_m2k

    return connection


def make_window_connection(
    connection_id,
    zone_id,
    area_m2,
    shgc=0.60,
):
    return BoundaryConnection(
        connection_id=connection_id,
        zone_id=zone_id,
        connection_type="window",
        area_m2=area_m2,
        orientation_deg=180.0,
        is_window=True,
        is_openable=True,
        open_fraction=0.0,
        solar_heat_gain_coefficient=shgc,
        frame_fraction=0.20,
        shading_factor=1.0,
        curtain_open=True,
        curtain_solar_reduction_factor=0.35,
    )


def make_graph(
    building,
    zone_connections=None,
    boundary_connections=None,
):
    return BuildingPhysicsGraph(
        building_model=building,
        zone_connections=zone_connections or {},
        boundary_connections=boundary_connections or {},
    )


def make_weather(
    outdoor_temperature_c,
    ghi=0.0,
    dni=0.0,
    dhi=0.0,
):
    return WeatherState(
        datetime=DateTime(2021, 1, 1, 12, 0, 0),
        outdoor_temperature_c=outdoor_temperature_c,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        direct_normal_radiation_w_m2=dni,
        diffuse_horizontal_radiation_w_m2=dhi,
        global_horizontal_radiation_w_m2=ghi,
        outdoor_illuminance_lux=0.0,
        sky_condition="clear",
        outdoor_co2_ppm=420.0,
        outdoor_noise_db=45.0,
    )


def make_heating_system_spec():
    return SimpleNamespace(
        has_heating=True,
        has_cooling=False,
        max_heating_power_w=1000.0,
        max_cooling_power_w=0.0,
    )


def make_heating_control_state():
    return SimpleNamespace(
        heating_setpoint_c=20.0,
        cooling_setpoint_c=26.0,
        thermostat_deadband_c=0.5,
    )


def assert_one_zone_drifts_toward_outside():
    zone = make_zone(
        zone_id="living_room",
        initial_temp_c=20.0,
        external_wall_area_m2=40.0,
    )

    building = make_building({
        "living_room": zone,
    })

    graph = make_graph(building)

    weather = make_weather(
        outdoor_temperature_c=0.0,
    )

    model = ThermalModel()
    thermal_state = model.make_initial_state(building)

    old_temp = thermal_state.get_zone_state("living_room").air_temperature_c

    result = model.step(
        building_model=building,
        physics_graph=graph,
        thermal_state=thermal_state,
        weather_state=weather,
        zone_system_specs={},
        zone_control_states={},
        internal_gains_by_zone={},
        dt_minutes=DT_MINUTES,
    )

    new_temp = (
        result
        .updated_thermal_state
        .get_zone_state("living_room")
        .air_temperature_c
    )

    assert isinstance(result, ThermalStepResult)
    assert new_temp < old_temp

    print("OK: one zone drifts toward outside")


def assert_heating_raises_temperature():
    zone = make_zone(
        zone_id="living_room",
        initial_temp_c=18.0,
        external_wall_area_m2=40.0,
    )

    building = make_building({
        "living_room": zone,
    })

    graph = make_graph(building)

    weather = make_weather(
        outdoor_temperature_c=0.0,
    )

    model = ThermalModel()
    thermal_state = model.make_initial_state(building)

    old_temp = thermal_state.get_zone_state("living_room").air_temperature_c

    result = model.step(
        building_model=building,
        physics_graph=graph,
        thermal_state=thermal_state,
        weather_state=weather,
        zone_system_specs={
            "living_room": make_heating_system_spec(),
        },
        zone_control_states={
            "living_room": make_heating_control_state(),
        },
        internal_gains_by_zone={},
        dt_minutes=DT_MINUTES,
    )

    new_temp = (
        result
        .updated_thermal_state
        .get_zone_state("living_room")
        .air_temperature_c
    )

    assert new_temp > old_temp
    assert result.total_heating_energy_wh() > 0.0
    assert result.total_cooling_energy_wh() == 0.0

    print("OK: heating raises temperature")


def assert_two_zones_move_toward_each_other():
    hot_zone = make_zone(
        zone_id="hot_room",
        initial_temp_c=30.0,
        external_wall_area_m2=0.0,
        internal_wall_area_m2=30.0,
    )

    cold_zone = make_zone(
        zone_id="cold_room",
        initial_temp_c=10.0,
        external_wall_area_m2=0.0,
        internal_wall_area_m2=30.0,
    )

    building = make_building({
        "hot_room": hot_zone,
        "cold_room": cold_zone,
    })

    connection = make_zone_connection(
        connection_id="hot_cold_wall",
        zone_a_id="hot_room",
        zone_b_id="cold_room",
        area_m2=30.0,
        u_value_w_m2k=5.0,
    )

    graph = make_graph(
        building=building,
        zone_connections={
            "hot_cold_wall": connection,
        },
    )

    weather = make_weather(
        outdoor_temperature_c=20.0,
    )

    model = ThermalModel()
    thermal_state = model.make_initial_state(building)

    old_hot = thermal_state.get_zone_state("hot_room").air_temperature_c
    old_cold = thermal_state.get_zone_state("cold_room").air_temperature_c
    old_difference = old_hot - old_cold

    result = model.step(
        building_model=building,
        physics_graph=graph,
        thermal_state=thermal_state,
        weather_state=weather,
        zone_system_specs={},
        zone_control_states={},
        internal_gains_by_zone={},
        dt_minutes=DT_MINUTES,
    )

    new_hot = (
        result
        .updated_thermal_state
        .get_zone_state("hot_room")
        .air_temperature_c
    )

    new_cold = (
        result
        .updated_thermal_state
        .get_zone_state("cold_room")
        .air_temperature_c
    )

    new_difference = new_hot - new_cold

    assert new_hot < old_hot
    assert new_cold > old_cold
    assert abs(new_difference) < abs(old_difference)

    print("OK: two zones move toward each other")


def assert_window_solar_gain_raises_temperature():
    zone = make_zone(
        zone_id="living_room",
        initial_temp_c=20.0,
        external_wall_area_m2=0.0,
    )

    building = make_building({
        "living_room": zone,
    })

    window = make_window_connection(
        connection_id="living_south_window",
        zone_id="living_room",
        area_m2=4.0,
        shgc=0.60,
    )

    graph = make_graph(
        building=building,
        boundary_connections={
            "living_south_window": window,
        },
    )

    weather = make_weather(
        outdoor_temperature_c=20.0,
        ghi=800.0,
        dni=900.0,
        dhi=120.0,
    )

    model = ThermalModel()
    thermal_state = model.make_initial_state(building)

    old_temp = thermal_state.get_zone_state("living_room").air_temperature_c

    result = model.step(
        building_model=building,
        physics_graph=graph,
        thermal_state=thermal_state,
        weather_state=weather,
        zone_system_specs={},
        zone_control_states={},
        internal_gains_by_zone={},
        dt_minutes=DT_MINUTES,
    )

    new_temp = (
        result
        .updated_thermal_state
        .get_zone_state("living_room")
        .air_temperature_c
    )

    assert result.solar_gain_result.total_solar_gain_w() > 0.0
    assert new_temp > old_temp

    print("OK: window solar gain raises temperature")


def assert_no_nonthermal_physics_calculated():
    zone = make_zone(
        zone_id="living_room",
        initial_temp_c=20.0,
        external_wall_area_m2=20.0,
    )

    building = make_building({
        "living_room": zone,
    })

    graph = make_graph(building)

    weather = make_weather(
        outdoor_temperature_c=10.0,
    )

    model = ThermalModel()
    thermal_state = model.make_initial_state(building)

    result = model.step(
        building_model=building,
        physics_graph=graph,
        thermal_state=thermal_state,
        weather_state=weather,
        zone_system_specs={},
        zone_control_states={},
        internal_gains_by_zone={},
        dt_minutes=DT_MINUTES,
    )

    state_dict = result.updated_thermal_state.to_dict()

    forbidden_terms = [
        "co2_ppm",
        "indoor_daylight",
        "indoor_noise",
        "humidity",
        "air_quality",
        "occupant_comfort",
    ]

    state_text = str(state_dict)

    for term in forbidden_terms:
        assert term not in state_text

    assert "air_temperature_c" in state_text
    assert "mass_temperature_c" in state_text

    print("OK: no non-thermal physics calculated")


def run_tests():
    assert_one_zone_drifts_toward_outside()
    assert_heating_raises_temperature()
    assert_two_zones_move_toward_each_other()
    assert_window_solar_gain_raises_temperature()
    assert_no_nonthermal_physics_calculated()

    print("")
    print("PHASE 4 THERMAL ARCHITECTURE OK ✅")


if __name__ == "__main__":
    run_tests()