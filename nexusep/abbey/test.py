"""
ABBEY Phase 5 airflow / CO2 architecture test.

Tests:
1. 1 zone, no people, outdoor ventilation -> CO2 moves toward outdoor baseline.
2. 1 zone, people inside, no ventilation -> CO2 rises.
3. 1 zone, people + ventilation -> CO2 rises slower.
4. 2 zones with open door -> CO2 mixes between zones.
5. Window open + wind -> outdoor airflow increases.
6. Wind direction affects window airflow.
7. CO2 never goes negative / below physical lower bound.
8. No thermal solver is calculated here.

Expected:
    PHASE 5 AIRFLOW CO2 ARCHITECTURE OK ✅
"""

from datetime import datetime as DateTime

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

from nexusep.abbey.building.physics.airflow import (
    AirCO2Model,
    AirCO2StepResult,
    BuildingAirState,
    BuildingAirflowControlInputs,
    DoorOpeningInput,
    WindowOpeningInput,
    ZoneAirState,
    ZoneOccupancyInput,
    calculate_building_window_outdoor_airflows,
)


DT_MINUTES = 15.0


def make_zone(
    zone_id,
    initial_co2_ppm=600.0,
    air_volume_m3=50.0,
    infiltration_ach=0.0,
    mechanical_available=False,
    mechanical_flow_m3_h=0.0,
):
    return ZoneModel(
        zone_id=zone_id,
        zone_name=zone_id,
        dwelling_id="dwelling_1",
        building_id="building_1",
        zone_scope="private",
        zone_use="generic",
        floor_area_m2=air_volume_m3 / 2.7,
        height_m=2.7,
        volume_m3=air_volume_m3,
        air_volume_m3=air_volume_m3,
        default_infiltration_ach=infiltration_ach,
        mechanical_ventilation_available=mechanical_available,
        mechanical_ventilation_flow_m3_h=mechanical_flow_m3_h,
        co2_initial_ppm=initial_co2_ppm,
        initial_co2_ppm=initial_co2_ppm,
        initial_temp_c=20.0,
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
    outdoor_co2_ppm=420.0,
    wind_speed_m_s=0.0,
    wind_direction_deg=0.0,
):
    return WeatherState(
        datetime=DateTime(2021, 1, 1, 12, 0, 0),
        outdoor_temperature_c=20.0,
        wind_speed_m_s=wind_speed_m_s,
        wind_direction_deg=wind_direction_deg,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        sky_condition="clear",
        outdoor_co2_ppm=outdoor_co2_ppm,
        outdoor_noise_db=45.0,
    )


def make_window_connection(
    connection_id,
    zone_id,
    orientation_deg=180.0,
    area_m2=2.0,
    max_opening_area_m2=1.0,
):
    return BoundaryConnection(
        connection_id=connection_id,
        zone_id=zone_id,
        connection_type="window",
        area_m2=area_m2,
        orientation_deg=orientation_deg,
        is_window=True,
        is_openable=True,
        open_fraction=0.0,
        max_opening_area_m2=max_opening_area_m2,
        discharge_coefficient=0.60,
    )


def make_zone_connection(
    connection_id,
    zone_a_id,
    zone_b_id,
    max_opening_area_m2=2.0,
    base_airflow_m3_h=0.0,
):
    """
    Compatibility helper.

    Current graph versions may use:
        from_zone_id / to_zone_id

    Some code paths may look for:
        zone_a_id / zone_b_id

    We set both safely.
    """

    try:
        connection = ZoneConnection(
            connection_id=connection_id,
            from_zone_id=zone_a_id,
            to_zone_id=zone_b_id,
            connection_type="door",
            area_m2=max_opening_area_m2,
            max_opening_area_m2=max_opening_area_m2,
            discharge_coefficient=0.60,
            base_airflow_m3_h=base_airflow_m3_h,
        )
    except TypeError:
        connection = ZoneConnection(
            connection_id=connection_id,
            zone_a_id=zone_a_id,
            zone_b_id=zone_b_id,
            connection_type="door",
            area_m2=max_opening_area_m2,
        )

        connection.max_opening_area_m2 = max_opening_area_m2
        connection.discharge_coefficient = 0.60
        connection.base_airflow_m3_h = base_airflow_m3_h

    connection.zone_a_id = zone_a_id
    connection.zone_b_id = zone_b_id

    return connection


def make_controls(
    occupancy_by_zone=None,
    window_openings=None,
    door_openings=None,
):
    return BuildingAirflowControlInputs(
        occupancy_by_zone=occupancy_by_zone or {},
        window_openings=window_openings or {},
        door_openings=door_openings or {},
    )


def assert_ventilation_moves_co2_toward_outdoor_baseline():
    zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=1200.0,
        infiltration_ach=2.0,
    )

    building = make_building({
        "living_room": zone,
    })

    graph = make_graph(building)
    weather = make_weather(outdoor_co2_ppm=420.0)

    model = AirCO2Model()
    air_state = model.make_initial_state(building)

    old_co2 = air_state.get_zone_state("living_room").co2_ppm

    result = model.step(
        building_model=building,
        physics_graph=graph,
        air_state=air_state,
        weather_state=weather,
        airflow_control_inputs=make_controls(),
        dt_minutes=DT_MINUTES,
    )

    new_co2 = result.updated_air_state.get_zone_state("living_room").co2_ppm

    assert isinstance(result, AirCO2StepResult)
    assert new_co2 < old_co2
    assert new_co2 > 420.0

    print("OK: ventilation moves CO2 toward outdoor baseline")


def assert_people_no_ventilation_co2_rises():
    zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=600.0,
        infiltration_ach=0.0,
    )

    building = make_building({
        "living_room": zone,
    })

    graph = make_graph(building)
    weather = make_weather(outdoor_co2_ppm=420.0)

    controls = make_controls(
        occupancy_by_zone={
            "living_room": ZoneOccupancyInput(
                zone_id="living_room",
                number_of_people=1.0,
            )
        }
    )

    model = AirCO2Model()
    air_state = model.make_initial_state(building)

    old_co2 = air_state.get_zone_state("living_room").co2_ppm

    result = model.step(
        building_model=building,
        physics_graph=graph,
        air_state=air_state,
        weather_state=weather,
        airflow_control_inputs=controls,
        dt_minutes=DT_MINUTES,
    )

    new_co2 = result.updated_air_state.get_zone_state("living_room").co2_ppm

    assert new_co2 > old_co2

    print("OK: people inside with no ventilation raise CO2")


def assert_people_with_ventilation_rises_slower():
    no_vent_zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=600.0,
        infiltration_ach=0.0,
    )

    vent_zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=600.0,
        infiltration_ach=0.5,
    )

    no_vent_building = make_building({
        "living_room": no_vent_zone,
    })

    vent_building = make_building({
        "living_room": vent_zone,
    })

    no_vent_graph = make_graph(no_vent_building)
    vent_graph = make_graph(vent_building)

    weather = make_weather(outdoor_co2_ppm=420.0)

    controls = make_controls(
        occupancy_by_zone={
            "living_room": ZoneOccupancyInput(
                zone_id="living_room",
                number_of_people=1.0,
            )
        }
    )

    model = AirCO2Model()

    no_vent_state = model.make_initial_state(no_vent_building)
    vent_state = model.make_initial_state(vent_building)

    no_vent_result = model.step(
        building_model=no_vent_building,
        physics_graph=no_vent_graph,
        air_state=no_vent_state,
        weather_state=weather,
        airflow_control_inputs=controls,
        dt_minutes=DT_MINUTES,
    )

    vent_result = model.step(
        building_model=vent_building,
        physics_graph=vent_graph,
        air_state=vent_state,
        weather_state=weather,
        airflow_control_inputs=controls,
        dt_minutes=DT_MINUTES,
    )

    no_vent_co2 = (
        no_vent_result
        .updated_air_state
        .get_zone_state("living_room")
        .co2_ppm
    )

    vent_co2 = (
        vent_result
        .updated_air_state
        .get_zone_state("living_room")
        .co2_ppm
    )

    assert no_vent_co2 > vent_co2
    assert vent_co2 > 600.0

    print("OK: people plus ventilation raises CO2 slower")


def assert_two_zones_open_door_mix_co2():
    high_zone = make_zone(
        zone_id="high_co2_room",
        initial_co2_ppm=1600.0,
        infiltration_ach=0.0,
    )

    low_zone = make_zone(
        zone_id="low_co2_room",
        initial_co2_ppm=500.0,
        infiltration_ach=0.0,
    )

    building = make_building({
        "high_co2_room": high_zone,
        "low_co2_room": low_zone,
    })

    connection = make_zone_connection(
        connection_id="door_between_rooms",
        zone_a_id="high_co2_room",
        zone_b_id="low_co2_room",
        max_opening_area_m2=4.0,
        base_airflow_m3_h=0.0,
    )

    graph = make_graph(
        building=building,
        zone_connections={
            "door_between_rooms": connection,
        },
    )

    weather = make_weather(outdoor_co2_ppm=420.0)

    controls = make_controls(
        door_openings={
            "door_between_rooms": DoorOpeningInput(
                zone_connection_id="door_between_rooms",
                zone_a_id="high_co2_room",
                zone_b_id="low_co2_room",
                opening_fraction=1.0,
            )
        }
    )

    model = AirCO2Model()
    air_state = model.make_initial_state(building)

    old_high = air_state.get_zone_state("high_co2_room").co2_ppm
    old_low = air_state.get_zone_state("low_co2_room").co2_ppm
    old_difference = old_high - old_low

    result = model.step(
        building_model=building,
        physics_graph=graph,
        air_state=air_state,
        weather_state=weather,
        airflow_control_inputs=controls,
        dt_minutes=DT_MINUTES,
    )

    new_high = result.updated_air_state.get_zone_state("high_co2_room").co2_ppm
    new_low = result.updated_air_state.get_zone_state("low_co2_room").co2_ppm
    new_difference = new_high - new_low

    assert new_high < old_high
    assert new_low > old_low
    assert abs(new_difference) < abs(old_difference)
    assert result.airflow_network.all_interzone_records_symmetric()

    print("OK: two zones with open door mix CO2")


def assert_window_open_wind_increases_outdoor_airflow():
    zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=800.0,
        infiltration_ach=0.0,
    )

    building = make_building({
        "living_room": zone,
    })

    window = make_window_connection(
        connection_id="south_window",
        zone_id="living_room",
        orientation_deg=180.0,
        max_opening_area_m2=1.5,
    )

    graph = make_graph(
        building=building,
        boundary_connections={
            "south_window": window,
        },
    )

    weather = make_weather(
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=4.0,
        wind_direction_deg=180.0,
    )

    closed_controls = make_controls(
        window_openings={
            "south_window": WindowOpeningInput(
                boundary_connection_id="south_window",
                zone_id="living_room",
                opening_fraction=0.0,
            )
        }
    )

    open_controls = make_controls(
        window_openings={
            "south_window": WindowOpeningInput(
                boundary_connection_id="south_window",
                zone_id="living_room",
                opening_fraction=1.0,
            )
        }
    )

    closed_flow = calculate_building_window_outdoor_airflows(
        physics_graph=graph,
        weather_state=weather,
        airflow_control_inputs=closed_controls,
    )

    open_flow = calculate_building_window_outdoor_airflows(
        physics_graph=graph,
        weather_state=weather,
        airflow_control_inputs=open_controls,
    )

    assert closed_flow.total_airflow_m3_h() == 0.0
    assert open_flow.total_airflow_m3_h() > closed_flow.total_airflow_m3_h()

    print("OK: window open plus wind increases outdoor airflow")


def assert_wind_direction_affects_window_airflow():
    zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=800.0,
        infiltration_ach=0.0,
    )

    building = make_building({
        "living_room": zone,
    })

    window = make_window_connection(
        connection_id="south_window",
        zone_id="living_room",
        orientation_deg=180.0,
        max_opening_area_m2=1.5,
    )

    graph = make_graph(
        building=building,
        boundary_connections={
            "south_window": window,
        },
    )

    controls = make_controls(
        window_openings={
            "south_window": WindowOpeningInput(
                boundary_connection_id="south_window",
                zone_id="living_room",
                opening_fraction=1.0,
            )
        }
    )

    aligned_weather = make_weather(
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=4.0,
        wind_direction_deg=180.0,
    )

    perpendicular_weather = make_weather(
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=4.0,
        wind_direction_deg=90.0,
    )

    aligned_flow = calculate_building_window_outdoor_airflows(
        physics_graph=graph,
        weather_state=aligned_weather,
        airflow_control_inputs=controls,
    )

    perpendicular_flow = calculate_building_window_outdoor_airflows(
        physics_graph=graph,
        weather_state=perpendicular_weather,
        airflow_control_inputs=controls,
    )

    assert aligned_flow.total_airflow_m3_h() > perpendicular_flow.total_airflow_m3_h()

    print("OK: wind direction affects window airflow")


def assert_co2_never_goes_negative():
    state = ZoneAirState(
        zone_id="bad_room",
        co2_ppm=-100.0,
        air_volume_m3=50.0,
    )

    assert state.co2_ppm >= 300.0

    building_state = BuildingAirState(
        zone_states={
            "bad_room": state,
        }
    )

    assert building_state.get_zone_state("bad_room").co2_ppm >= 300.0

    print("OK: CO2 is physically bounded")


def assert_no_thermal_solver_calculated():
    zone = make_zone(
        zone_id="living_room",
        initial_co2_ppm=800.0,
        infiltration_ach=1.0,
    )

    building = make_building({
        "living_room": zone,
    })

    graph = make_graph(building)
    weather = make_weather(outdoor_co2_ppm=420.0)

    model = AirCO2Model()
    air_state = model.make_initial_state(building)

    result = model.step(
        building_model=building,
        physics_graph=graph,
        air_state=air_state,
        weather_state=weather,
        airflow_control_inputs=make_controls(),
        dt_minutes=DT_MINUTES,
    )

    result_text = str(result.to_dict())

    forbidden_terms = [
        "air_temperature_c",
        "mass_temperature_c",
        "thermal_state",
        "heating_energy_wh",
        "cooling_energy_wh",
        "hvac_gain_w",
        "radiative_gain_w",
        "convective_gain_w",
    ]

    for term in forbidden_terms:
        assert term not in result_text

    assert "co2_ppm" in result_text
    assert "air_volume_m3" in result_text

    print("OK: no thermal solver calculated")


def run_tests():
    assert_ventilation_moves_co2_toward_outdoor_baseline()
    assert_people_no_ventilation_co2_rises()
    assert_people_with_ventilation_rises_slower()
    assert_two_zones_open_door_mix_co2()
    assert_window_open_wind_increases_outdoor_airflow()
    assert_wind_direction_affects_window_airflow()
    assert_co2_never_goes_negative()
    assert_no_thermal_solver_calculated()

    print("")
    print("PHASE 5 AIRFLOW CO2 ARCHITECTURE OK ✅")


if __name__ == "__main__":
    run_tests()