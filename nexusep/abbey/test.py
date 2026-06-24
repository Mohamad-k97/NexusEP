"""
ABBEY Phase 7 daylight / lighting / visual comfort architecture test.

Tests:
1. Outdoor daylight boundary reads WeatherState.
2. Window daylight parameters are extracted from graph boundary connections.
3. Indoor daylight rises with outdoor illuminance and window area.
4. Night / zero outdoor illuminance gives zero daylight.
5. Curtain / shading reduce daylight.
6. Artificial lighting off gives zero power.
7. Artificial lighting on gives lux, power, and energy.
8. Daylight + artificial lighting combine into indoor illuminance.
9. Visual comfort status is derived from illuminance target.
10. DaylightModel.step returns expected outputs.
11. No thermal / moisture / airflow solver is calculated here.

Expected:
    PHASE 7 DAYLIGHT LIGHTING ARCHITECTURE OK ✅
"""

from datetime import datetime as DateTime

from nexusep.abbey.building.model import (
    BuildingModel,
    DwellingModel,
    ZoneModel,
)

from nexusep.abbey.building.physics.weather import WeatherState

from nexusep.abbey.building.physics.daylight import (
    DEFAULT_VISUAL_COMFORT_TARGET_LUX,
    LIGHTING_CONTROL_MODE_MANUAL,
    VISUAL_COMFORT_STATUS_DARK,
    VISUAL_COMFORT_STATUS_UNDERLIT,
    VISUAL_COMFORT_STATUS_COMFORTABLE,
    VISUAL_COMFORT_STATUS_OVERLIT,
    DaylightModel,
    ZoneLightingControlInput,
    BuildingLightingControlInputs,
    make_outdoor_daylight_boundary_from_weather_state,
    make_building_window_daylight_parameters,
    calculate_building_indoor_daylight_result,
    calculate_building_lighting_from_controls,
    calculate_visual_comfort_from_light_state,
)


DT_MINUTES = 15.0
FLOOR_AREA_M2 = 20.0
ZONE_HEIGHT_M = 2.7


class FakeBoundaryConnection:
    def __init__(
        self,
        connection_id,
        zone_id,
        area_m2=5.0,
        orientation_deg=180.0,
        visible_transmittance=0.60,
        frame_fraction=0.20,
        shading_factor=1.00,
        curtain_open=True,
        curtain_daylight_reduction_factor=0.35,
    ):
        self.connection_id = connection_id
        self.zone_id = zone_id
        self.connection_type = "window"
        self.area_m2 = area_m2
        self.orientation_deg = orientation_deg

        self.window_visible_transmittance = visible_transmittance
        self.frame_fraction = frame_fraction
        self.shading_factor = shading_factor
        self.curtain_open = curtain_open
        self.curtain_daylight_reduction_factor = curtain_daylight_reduction_factor


class FakePhysicsGraph:
    def __init__(self, boundary_connections):
        self.boundary_connections = boundary_connections


def make_zone(
    zone_id,
    floor_area_m2=FLOOR_AREA_M2,
    daylight_utilization_factor=0.50,
    visual_comfort_target_lux=DEFAULT_VISUAL_COMFORT_TARGET_LUX,
):
    zone = ZoneModel(
        zone_id=zone_id,
        zone_name=zone_id,
        dwelling_id="dwelling_1",
        building_id="building_1",
        zone_scope="private",
        zone_use="generic",
        floor_area_m2=floor_area_m2,
        height_m=ZONE_HEIGHT_M,
        volume_m3=floor_area_m2 * ZONE_HEIGHT_M,
        air_volume_m3=floor_area_m2 * ZONE_HEIGHT_M,
        initial_temp_c=20.0,
    )

    # Phase 7 attributes. Attach after construction to avoid ZoneModel
    # constructor mismatch.
    zone.daylight_utilization_factor = daylight_utilization_factor
    zone.visual_comfort_target_lux = visual_comfort_target_lux
    zone.installed_lighting_lux = 500.0
    zone.lighting_power_density_w_m2 = 8.0

    return zone


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


def make_weather(
    outdoor_illuminance_lux=10000.0,
    sky_condition="clear",
):
    return WeatherState(
        datetime=DateTime(2021, 6, 21, 12, 0, 0),
        outdoor_temperature_c=25.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        direct_normal_radiation_w_m2=600.0,
        diffuse_horizontal_radiation_w_m2=120.0,
        global_horizontal_radiation_w_m2=700.0,
        outdoor_illuminance_lux=outdoor_illuminance_lux,
        sky_condition=sky_condition,
        outdoor_co2_ppm=420.0,
        outdoor_noise_db=45.0,
        relative_humidity_percent=50.0,
        atmospheric_pressure_pa=101325.0,
    )


def make_graph(
    zone_id="living_room",
    area_m2=5.0,
    curtain_open=True,
    shading_factor=1.0,
):
    window = FakeBoundaryConnection(
        connection_id="window_1",
        zone_id=zone_id,
        area_m2=area_m2,
        orientation_deg=180.0,
        visible_transmittance=0.60,
        frame_fraction=0.20,
        shading_factor=shading_factor,
        curtain_open=curtain_open,
        curtain_daylight_reduction_factor=0.35,
    )

    return FakePhysicsGraph(
        boundary_connections={
            "window_1": window,
        }
    )


def make_lighting_controls(
    zone_id="living_room",
    lights_on=True,
    dimming_fraction=1.0,
    requested_lux=300.0,
):
    return BuildingLightingControlInputs(
        controls_by_zone={
            zone_id: ZoneLightingControlInput(
                zone_id=zone_id,
                lights_on=lights_on,
                dimming_fraction=dimming_fraction,
                requested_artificial_lighting_lux=requested_lux,
                control_mode=LIGHTING_CONTROL_MODE_MANUAL,
            )
        }
    )


def assert_outdoor_daylight_boundary_reads_weather():
    boundary = make_outdoor_daylight_boundary_from_weather_state(
        make_weather(outdoor_illuminance_lux=12000.0)
    )

    assert boundary.outdoor_illuminance_lux == 12000.0
    assert boundary.has_daylight()

    print("OK: outdoor daylight boundary reads WeatherState")


def assert_window_daylight_parameters_from_graph():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})
    graph = make_graph("living_room", area_m2=5.0)

    parameters = make_building_window_daylight_parameters(
        physics_graph=graph,
        building_model=building,
    )

    zone_params = parameters.get_zone_window_parameters("living_room")

    assert zone_params.window_count() == 1
    assert zone_params.total_effective_daylight_area_m2() > 0.0

    print("OK: window daylight parameters extracted from graph")


def assert_indoor_daylight_rises_with_outdoor_illuminance():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})
    graph = make_graph("living_room", area_m2=5.0)

    window_params = make_building_window_daylight_parameters(
        physics_graph=graph,
        building_model=building,
    )

    low_boundary = make_outdoor_daylight_boundary_from_weather_state(
        make_weather(outdoor_illuminance_lux=5000.0)
    )

    high_boundary = make_outdoor_daylight_boundary_from_weather_state(
        make_weather(outdoor_illuminance_lux=15000.0)
    )

    low_result = calculate_building_indoor_daylight_result(
        building_model=building,
        building_window_daylight_parameters=window_params,
        outdoor_daylight_boundary=low_boundary,
    )

    high_result = calculate_building_indoor_daylight_result(
        building_model=building,
        building_window_daylight_parameters=window_params,
        outdoor_daylight_boundary=high_boundary,
    )

    low_lux = low_result.get_zone_result("living_room").daylight_illuminance_lux
    high_lux = high_result.get_zone_result("living_room").daylight_illuminance_lux

    assert high_lux > low_lux

    print("OK: indoor daylight rises with outdoor illuminance")


def assert_zero_outdoor_illuminance_gives_zero_daylight():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})
    graph = make_graph("living_room", area_m2=5.0)

    daylight_model = DaylightModel()

    result = daylight_model.step(
        building_model=building,
        physics_graph=graph,
        light_state=daylight_model.make_initial_state(building),
        weather_state=make_weather(outdoor_illuminance_lux=0.0, sky_condition="night"),
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=False,
            dimming_fraction=0.0,
            requested_lux=0.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    daylight_lux = result.daylight_illuminance_by_zone_lux()["living_room"]

    assert daylight_lux == 0.0

    print("OK: zero outdoor illuminance gives zero daylight")


def assert_curtain_and_shading_reduce_daylight():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})

    open_graph = make_graph(
        zone_id="living_room",
        area_m2=5.0,
        curtain_open=True,
        shading_factor=1.0,
    )

    shaded_graph = make_graph(
        zone_id="living_room",
        area_m2=5.0,
        curtain_open=False,
        shading_factor=0.5,
    )

    daylight_model = DaylightModel()

    open_result = daylight_model.step(
        building_model=building,
        physics_graph=open_graph,
        light_state=daylight_model.make_initial_state(building),
        weather_state=make_weather(outdoor_illuminance_lux=10000.0),
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=False,
            dimming_fraction=0.0,
            requested_lux=0.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    shaded_result = daylight_model.step(
        building_model=building,
        physics_graph=shaded_graph,
        light_state=daylight_model.make_initial_state(building),
        weather_state=make_weather(outdoor_illuminance_lux=10000.0),
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=False,
            dimming_fraction=0.0,
            requested_lux=0.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    open_lux = open_result.daylight_illuminance_by_zone_lux()["living_room"]
    shaded_lux = shaded_result.daylight_illuminance_by_zone_lux()["living_room"]

    assert shaded_lux < open_lux

    print("OK: curtain and shading reduce daylight")


def assert_lighting_off_gives_zero_power():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})

    lighting_result = calculate_building_lighting_from_controls(
        building_model=building,
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=False,
            dimming_fraction=0.0,
            requested_lux=0.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    assert lighting_result.lighting_power_by_zone_w()["living_room"] == 0.0
    assert lighting_result.lighting_energy_by_zone_wh()["living_room"] == 0.0

    print("OK: artificial lighting off gives zero power")


def assert_lighting_on_gives_lux_power_energy():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})

    lighting_result = calculate_building_lighting_from_controls(
        building_model=building,
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=True,
            dimming_fraction=1.0,
            requested_lux=300.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    zone_result = lighting_result.get_zone_result("living_room")

    assert zone_result.artificial_lighting_illuminance_lux == 300.0
    assert zone_result.lighting_power_w > 0.0
    assert zone_result.lighting_energy_wh > 0.0

    print("OK: artificial lighting on gives lux, power, and energy")


def assert_daylight_and_artificial_lighting_combine():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})
    graph = make_graph("living_room", area_m2=5.0)

    daylight_model = DaylightModel()

    result = daylight_model.step(
        building_model=building,
        physics_graph=graph,
        light_state=daylight_model.make_initial_state(building),
        weather_state=make_weather(outdoor_illuminance_lux=10000.0),
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=True,
            dimming_fraction=1.0,
            requested_lux=300.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    state = result.updated_light_state.get_zone_state("living_room")

    assert state.indoor_illuminance_lux == (
        state.daylight_illuminance_lux
        + state.artificial_lighting_illuminance_lux
    )

    print("OK: daylight and artificial lighting combine into indoor illuminance")


def assert_visual_comfort_statuses():
    dark_state = make_zone("dark_room")
    underlit_state = make_zone("underlit_room")
    comfortable_state = make_zone("comfortable_room")
    overlit_state = make_zone("overlit_room")

    building = make_building({
        "dark_room": dark_state,
        "underlit_room": underlit_state,
        "comfortable_room": comfortable_state,
        "overlit_room": overlit_state,
    })

    from nexusep.abbey.building.physics.daylight import (
        ZoneLightState,
        BuildingLightState,
    )

    light_state = BuildingLightState(
        zone_states={
            "dark_room": ZoneLightState(
                zone_id="dark_room",
                indoor_illuminance_lux=10.0,
                visual_comfort_target_lux=300.0,
            ),
            "underlit_room": ZoneLightState(
                zone_id="underlit_room",
                indoor_illuminance_lux=100.0,
                visual_comfort_target_lux=300.0,
            ),
            "comfortable_room": ZoneLightState(
                zone_id="comfortable_room",
                indoor_illuminance_lux=300.0,
                visual_comfort_target_lux=300.0,
            ),
            "overlit_room": ZoneLightState(
                zone_id="overlit_room",
                indoor_illuminance_lux=1000.0,
                visual_comfort_target_lux=300.0,
            ),
        }
    )

    comfort_result = calculate_visual_comfort_from_light_state(
        building_model=building,
        building_light_state=light_state,
    )

    statuses = comfort_result.visual_comfort_status_by_zone()

    assert statuses["dark_room"] == VISUAL_COMFORT_STATUS_DARK
    assert statuses["underlit_room"] == VISUAL_COMFORT_STATUS_UNDERLIT
    assert statuses["comfortable_room"] == VISUAL_COMFORT_STATUS_COMFORTABLE
    assert statuses["overlit_room"] == VISUAL_COMFORT_STATUS_OVERLIT

    print("OK: visual comfort statuses are derived from illuminance target")


def assert_daylight_model_step_outputs():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})
    graph = make_graph("living_room", area_m2=5.0)

    daylight_model = DaylightModel()

    result = daylight_model.step(
        building_model=building,
        physics_graph=graph,
        light_state=daylight_model.make_initial_state(building),
        weather_state=make_weather(outdoor_illuminance_lux=10000.0),
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=True,
            dimming_fraction=1.0,
            requested_lux=300.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    assert "living_room" in result.indoor_illuminance_by_zone_lux()
    assert "living_room" in result.visual_comfort_status_by_zone()
    assert "living_room" in result.lighting_power_by_zone_w()
    assert len(result.debug_records) == 1

    print("OK: DaylightModel.step returns expected outputs")


def assert_no_other_physics_solvers_calculated():
    zone = make_zone("living_room")
    building = make_building({"living_room": zone})
    graph = make_graph("living_room", area_m2=5.0)

    daylight_model = DaylightModel()

    result = daylight_model.step(
        building_model=building,
        physics_graph=graph,
        light_state=daylight_model.make_initial_state(building),
        weather_state=make_weather(outdoor_illuminance_lux=10000.0),
        lighting_control_inputs=make_lighting_controls(
            zone_id="living_room",
            lights_on=True,
            dimming_fraction=1.0,
            requested_lux=300.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    result_text = str(result.to_dict())

    forbidden_terms = [
        "updated_thermal_state",
        "mass_temperature_c",
        "heating_energy_wh",
        "cooling_energy_wh",
        "co2_ppm",
        "humidity_ratio",
        "relative_humidity",
        "airflow_network",
        "interzone_airflow",
        "outdoor_airflows_by_zone",
    ]

    for term in forbidden_terms:
        assert term not in result_text

    assert "indoor_illuminance_lux" in result_text
    assert "lighting_power_w" in result_text
    assert "visual_comfort_status" in result_text

    print("OK: no thermal, moisture, CO2, or airflow solver calculated")


def run_tests():
    assert_outdoor_daylight_boundary_reads_weather()
    assert_window_daylight_parameters_from_graph()
    assert_indoor_daylight_rises_with_outdoor_illuminance()
    assert_zero_outdoor_illuminance_gives_zero_daylight()
    assert_curtain_and_shading_reduce_daylight()
    assert_lighting_off_gives_zero_power()
    assert_lighting_on_gives_lux_power_energy()
    assert_daylight_and_artificial_lighting_combine()
    assert_visual_comfort_statuses()
    assert_daylight_model_step_outputs()
    assert_no_other_physics_solvers_calculated()

    print("")
    print("PHASE 7 DAYLIGHT LIGHTING ARCHITECTURE OK ✅")


if __name__ == "__main__":
    run_tests()