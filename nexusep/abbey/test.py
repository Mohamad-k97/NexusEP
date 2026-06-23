"""
ABBEY Phase 6 moisture / humidity architecture test.

Tests:
1. 1 zone, dry indoor air + humid outdoor ventilation -> indoor humidity rises.
2. 1 zone, humid indoor air + dry outdoor ventilation -> indoor humidity falls.
3. 1 zone, people moisture + no ventilation -> humidity rises.
4. 1 zone, people moisture + ventilation -> humidity rises slower.
5. 2 zones with open door -> humidity ratios move toward each other.
6. RH is derived from temperature and humidity ratio.
7. Humidity ratio never goes negative.
8. No thermal solver is calculated here.
9. No airflow solver is recalculated here if airflow network is passed in.

Expected:
    PHASE 6 HUMIDITY ARCHITECTURE OK ✅
"""

from datetime import datetime as DateTime

from nexusep.abbey.building.model import (
    BuildingModel,
    DwellingModel,
    ZoneModel,
)

from nexusep.abbey.building.physics.weather import WeatherState

from nexusep.abbey.building.physics.airflow import (
    BuildingAirflowNetwork,
    ZoneOutdoorAirflowRecord,
    InterzoneAirflowLink,
    InterzoneAirflowRecord,
)

from nexusep.abbey.building.physics.moisture import (
    DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H,
    DEFAULT_ATMOSPHERIC_PRESSURE_PA,
    MOISTURE_AIR_DENSITY_KG_M3,
    MOISTURE_SOURCE_PEOPLE,
    MoistureModel,
    ZoneMoistureState,
    BuildingMoistureSourceInputs,
    ZoneMoistureSourceInput,
    humidity_ratio_from_rh,
    relative_humidity_from_humidity_ratio,
)


DT_MINUTES = 15.0
ZONE_VOLUME_M3 = 50.0
ZONE_TEMPERATURE_C = 20.0
PRESSURE_PA = DEFAULT_ATMOSPHERIC_PRESSURE_PA


class FakeThermalZoneState:
    def __init__(self, zone_id, air_temperature_c):
        self.zone_id = zone_id
        self.air_temperature_c = air_temperature_c


class FakeThermalState:
    def __init__(self, temperatures_by_zone):
        self.zone_states = {
            zone_id: FakeThermalZoneState(
                zone_id=zone_id,
                air_temperature_c=temperature_c,
            )
            for zone_id, temperature_c in temperatures_by_zone.items()
        }

    def has_zone(self, zone_id):
        return zone_id in self.zone_states

    def get_zone_state(self, zone_id):
        return self.zone_states[zone_id]


class SuppliedAirflowNetwork:
    """
    Minimal duck-typed airflow network.

    Used to prove moisture.py reads an already-supplied airflow network
    and does not need to recalculate airflow.
    """

    def __init__(self, outdoor_airflows_by_zone, interzone_airflow_links=None):
        self.outdoor_airflows_by_zone = outdoor_airflows_by_zone
        self.interzone_airflow_links = interzone_airflow_links or {}

    def interzone_links_for_zone(self, zone_id):
        out = []

        for link in self.interzone_airflow_links.values():
            if link.zone_a_id == zone_id or link.zone_b_id == zone_id:
                out.append(link)

        return out


def make_zone(
    zone_id,
    initial_rh_percent=50.0,
    air_volume_m3=ZONE_VOLUME_M3,
):
    zone = ZoneModel(
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
        initial_temp_c=ZONE_TEMPERATURE_C,
    )

    # Moisture Phase 6 attributes.
    # ZoneModel may not define these in its constructor, so attach them here.
    zone.initial_relative_humidity_percent = initial_rh_percent
    zone.relative_humidity_percent = initial_rh_percent
    zone.initial_rh_percent = initial_rh_percent

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
    outdoor_rh_percent=50.0,
    outdoor_temperature_c=ZONE_TEMPERATURE_C,
):
    return WeatherState(
        datetime=DateTime(2021, 1, 1, 12, 0, 0),
        outdoor_temperature_c=outdoor_temperature_c,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        sky_condition="clear",
        outdoor_co2_ppm=420.0,
        outdoor_noise_db=45.0,
        relative_humidity_percent=outdoor_rh_percent,
        atmospheric_pressure_pa=PRESSURE_PA,
    )


def make_thermal_state(zone_ids, temperature_c=ZONE_TEMPERATURE_C):
    return FakeThermalState({
        zone_id: temperature_c
        for zone_id in zone_ids
    })


def make_moisture_state(zone_id, rh_percent, temperature_c=ZONE_TEMPERATURE_C):
    humidity_ratio = humidity_ratio_from_rh(
        relative_humidity_percent=rh_percent,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=PRESSURE_PA,
    )

    derived_rh = relative_humidity_from_humidity_ratio(
        humidity_ratio_kg_kg=humidity_ratio,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=PRESSURE_PA,
    )

    return ZoneMoistureState(
        zone_id=zone_id,
        humidity_ratio_kg_kg=humidity_ratio,
        relative_humidity_percent=derived_rh,
    )


def make_network_with_outdoor_flow(zone_id, outdoor_flow_m3_h):
    return BuildingAirflowNetwork(
        outdoor_airflows_by_zone={
            zone_id: ZoneOutdoorAirflowRecord(
                zone_id=zone_id,
                infiltration_flow_m3_h=outdoor_flow_m3_h,
                mechanical_ventilation_flow_m3_h=0.0,
                window_airflow_m3_h=0.0,
            )
        },
        interzone_airflow_links={},
        interzone_airflow_records={},
    )


def make_network_no_flow(zone_id):
    return make_network_with_outdoor_flow(
        zone_id=zone_id,
        outdoor_flow_m3_h=0.0,
    )


def make_people_sources(zone_id, number_of_people=1.0):
    return BuildingMoistureSourceInputs(
        sources_by_zone={
            zone_id: [
                ZoneMoistureSourceInput(
                    zone_id=zone_id,
                    moisture_generation_kg_h=(
                        number_of_people
                        * DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H
                    ),
                    source_type=MOISTURE_SOURCE_PEOPLE,
                )
            ]
        }
    )


def make_empty_sources():
    return BuildingMoistureSourceInputs(
        sources_by_zone={},
    )


def assert_dry_indoor_humid_outdoor_ventilation_raises_humidity():
    zone = make_zone(
        zone_id="living_room",
        initial_rh_percent=30.0,
    )

    building = make_building({
        "living_room": zone,
    })

    moisture_model = MoistureModel()

    moisture_state = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    old_w = moisture_state.get_zone_state("living_room").humidity_ratio_kg_kg

    result = moisture_model.step(
        building_model=building,
        moisture_state=moisture_state,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=make_network_with_outdoor_flow(
            zone_id="living_room",
            outdoor_flow_m3_h=100.0,
        ),
        weather_state=make_weather(outdoor_rh_percent=80.0),
        moisture_source_inputs=make_empty_sources(),
        dt_minutes=DT_MINUTES,
    )

    new_w = (
        result
        .updated_moisture_state
        .get_zone_state("living_room")
        .humidity_ratio_kg_kg
    )

    assert new_w > old_w

    print("OK: dry indoor air plus humid outdoor ventilation raises humidity")


def assert_humid_indoor_dry_outdoor_ventilation_lowers_humidity():
    zone = make_zone(
        zone_id="living_room",
        initial_rh_percent=80.0,
    )

    building = make_building({
        "living_room": zone,
    })

    moisture_model = MoistureModel()

    moisture_state = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    old_w = moisture_state.get_zone_state("living_room").humidity_ratio_kg_kg

    result = moisture_model.step(
        building_model=building,
        moisture_state=moisture_state,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=make_network_with_outdoor_flow(
            zone_id="living_room",
            outdoor_flow_m3_h=100.0,
        ),
        weather_state=make_weather(outdoor_rh_percent=30.0),
        moisture_source_inputs=make_empty_sources(),
        dt_minutes=DT_MINUTES,
    )

    new_w = (
        result
        .updated_moisture_state
        .get_zone_state("living_room")
        .humidity_ratio_kg_kg
    )

    assert new_w < old_w

    print("OK: humid indoor air plus dry outdoor ventilation lowers humidity")


def assert_people_moisture_no_ventilation_raises_humidity():
    zone = make_zone(
        zone_id="living_room",
        initial_rh_percent=45.0,
    )

    building = make_building({
        "living_room": zone,
    })

    moisture_model = MoistureModel()

    moisture_state = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    old_w = moisture_state.get_zone_state("living_room").humidity_ratio_kg_kg

    result = moisture_model.step(
        building_model=building,
        moisture_state=moisture_state,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=make_network_no_flow("living_room"),
        weather_state=make_weather(outdoor_rh_percent=45.0),
        moisture_source_inputs=make_people_sources(
            zone_id="living_room",
            number_of_people=1.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    new_w = (
        result
        .updated_moisture_state
        .get_zone_state("living_room")
        .humidity_ratio_kg_kg
    )

    assert new_w > old_w

    print("OK: people moisture with no ventilation raises humidity")


def assert_people_moisture_with_ventilation_rises_slower():
    zone = make_zone(
        zone_id="living_room",
        initial_rh_percent=45.0,
    )

    building = make_building({
        "living_room": zone,
    })

    moisture_model = MoistureModel()

    initial_state_no_vent = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    initial_state_vent = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    no_vent_result = moisture_model.step(
        building_model=building,
        moisture_state=initial_state_no_vent,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=make_network_no_flow("living_room"),
        weather_state=make_weather(outdoor_rh_percent=45.0),
        moisture_source_inputs=make_people_sources(
            zone_id="living_room",
            number_of_people=1.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    vent_result = moisture_model.step(
        building_model=building,
        moisture_state=initial_state_vent,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=make_network_with_outdoor_flow(
            zone_id="living_room",
            outdoor_flow_m3_h=25.0,
        ),
        weather_state=make_weather(outdoor_rh_percent=45.0),
        moisture_source_inputs=make_people_sources(
            zone_id="living_room",
            number_of_people=1.0,
        ),
        dt_minutes=DT_MINUTES,
    )

    no_vent_w = (
        no_vent_result
        .updated_moisture_state
        .get_zone_state("living_room")
        .humidity_ratio_kg_kg
    )

    vent_w = (
        vent_result
        .updated_moisture_state
        .get_zone_state("living_room")
        .humidity_ratio_kg_kg
    )

    initial_w = (
        initial_state_no_vent
        .get_zone_state("living_room")
        .humidity_ratio_kg_kg
    )

    assert no_vent_w > vent_w
    assert vent_w > initial_w

    print("OK: people moisture plus ventilation raises humidity slower")


def assert_two_zones_open_door_mix_humidity():
    high_zone = make_zone(
        zone_id="humid_room",
        initial_rh_percent=80.0,
    )

    low_zone = make_zone(
        zone_id="dry_room",
        initial_rh_percent=30.0,
    )

    building = make_building({
        "humid_room": high_zone,
        "dry_room": low_zone,
    })

    moisture_model = MoistureModel()

    moisture_state = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["humid_room", "dry_room"]),
    )

    old_high = moisture_state.get_zone_state("humid_room").humidity_ratio_kg_kg
    old_low = moisture_state.get_zone_state("dry_room").humidity_ratio_kg_kg
    old_difference = old_high - old_low

    link = InterzoneAirflowLink(
        link_id="door_between_rooms",
        zone_connection_id="door_between_rooms",
        zone_a_id="humid_room",
        zone_b_id="dry_room",
        connection_type="door",
        base_airflow_m3_h=0.0,
        max_opening_area_m2=4.0,
        discharge_coefficient=0.60,
        opening_fraction=1.0,
        assumed_mixing_air_speed_m_s=0.20,
    )

    record = InterzoneAirflowRecord(
        link_id=link.link_id,
        zone_connection_id=link.zone_connection_id,
        zone_a_id=link.zone_a_id,
        zone_b_id=link.zone_b_id,
        flow_a_to_b_m3_h=link.mixing_flow_m3_h,
        flow_b_to_a_m3_h=link.mixing_flow_m3_h,
    )

    network = BuildingAirflowNetwork(
        outdoor_airflows_by_zone={
            "humid_room": ZoneOutdoorAirflowRecord(zone_id="humid_room"),
            "dry_room": ZoneOutdoorAirflowRecord(zone_id="dry_room"),
        },
        interzone_airflow_links={
            link.link_id: link,
        },
        interzone_airflow_records={
            record.link_id: record,
        },
    )

    result = moisture_model.step(
        building_model=building,
        moisture_state=moisture_state,
        thermal_state=make_thermal_state(["humid_room", "dry_room"]),
        airflow_network=network,
        weather_state=make_weather(outdoor_rh_percent=50.0),
        moisture_source_inputs=make_empty_sources(),
        dt_minutes=DT_MINUTES,
    )

    new_high = (
        result
        .updated_moisture_state
        .get_zone_state("humid_room")
        .humidity_ratio_kg_kg
    )

    new_low = (
        result
        .updated_moisture_state
        .get_zone_state("dry_room")
        .humidity_ratio_kg_kg
    )

    new_difference = new_high - new_low

    assert new_high < old_high
    assert new_low > old_low
    assert abs(new_difference) < abs(old_difference)

    print("OK: two zones with open door mix humidity ratios")


def assert_rh_is_derived_from_temperature_and_humidity_ratio():
    humidity_ratio = humidity_ratio_from_rh(
        relative_humidity_percent=50.0,
        temperature_c=20.0,
        atmospheric_pressure_pa=PRESSURE_PA,
    )

    rh_at_20 = relative_humidity_from_humidity_ratio(
        humidity_ratio_kg_kg=humidity_ratio,
        temperature_c=20.0,
        atmospheric_pressure_pa=PRESSURE_PA,
    )

    rh_at_25 = relative_humidity_from_humidity_ratio(
        humidity_ratio_kg_kg=humidity_ratio,
        temperature_c=25.0,
        atmospheric_pressure_pa=PRESSURE_PA,
    )

    assert abs(rh_at_20 - 50.0) < 0.5
    assert rh_at_25 < rh_at_20

    print("OK: RH is derived from temperature and humidity ratio")


def assert_humidity_ratio_never_negative():
    state = ZoneMoistureState(
        zone_id="bad_room",
        humidity_ratio_kg_kg=-0.01,
        relative_humidity_percent=50.0,
    )

    assert state.humidity_ratio_kg_kg >= 0.0

    print("OK: humidity ratio is physically bounded")


def assert_no_thermal_solver_calculated():
    zone = make_zone(
        zone_id="living_room",
        initial_rh_percent=45.0,
    )

    building = make_building({
        "living_room": zone,
    })

    moisture_model = MoistureModel()

    moisture_state = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    result = moisture_model.step(
        building_model=building,
        moisture_state=moisture_state,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=make_network_with_outdoor_flow(
            zone_id="living_room",
            outdoor_flow_m3_h=25.0,
        ),
        weather_state=make_weather(outdoor_rh_percent=50.0),
        moisture_source_inputs=make_empty_sources(),
        dt_minutes=DT_MINUTES,
    )

    result_text = str(result.to_dict())

    forbidden_terms = [
        "updated_thermal_state",
        "mass_temperature_c",
        "heating_energy_wh",
        "cooling_energy_wh",
        "hvac_gain_w",
        "radiative_gain_w",
        "convective_gain_w",
    ]

    for term in forbidden_terms:
        assert term not in result_text

    assert "humidity_ratio" in result_text
    assert "relative_humidity" in result_text

    print("OK: no thermal solver calculated")


def assert_no_airflow_solver_recalculated_when_network_passed():
    zone = make_zone(
        zone_id="living_room",
        initial_rh_percent=45.0,
    )

    building = make_building({
        "living_room": zone,
    })

    moisture_model = MoistureModel()

    moisture_state = moisture_model.make_initial_state(
        building_model=building,
        thermal_state=make_thermal_state(["living_room"]),
    )

    supplied_flow_m3_h = 42.0

    supplied_network = SuppliedAirflowNetwork(
        outdoor_airflows_by_zone={
            "living_room": ZoneOutdoorAirflowRecord(
                zone_id="living_room",
                infiltration_flow_m3_h=supplied_flow_m3_h,
            )
        },
        interzone_airflow_links={},
    )

    result = moisture_model.step(
        building_model=building,
        moisture_state=moisture_state,
        thermal_state=make_thermal_state(["living_room"]),
        airflow_network=supplied_network,
        weather_state=make_weather(outdoor_rh_percent=50.0),
        moisture_source_inputs=make_empty_sources(),
        dt_minutes=DT_MINUTES,
    )

    expected_mass_flow_kg_s = (
        MOISTURE_AIR_DENSITY_KG_M3
        * supplied_flow_m3_h
        / 3600.0
    )

    actual_mass_flow_kg_s = (
        result
        .moisture_transport_result
        .total_dry_air_mass_flow_kg_s_by_zone()["living_room"]
    )

    assert abs(actual_mass_flow_kg_s - expected_mass_flow_kg_s) < 1e-9

    print("OK: supplied airflow network is used without recalculating airflow")


def run_tests():
    assert_dry_indoor_humid_outdoor_ventilation_raises_humidity()
    assert_humid_indoor_dry_outdoor_ventilation_lowers_humidity()
    assert_people_moisture_no_ventilation_raises_humidity()
    assert_people_moisture_with_ventilation_rises_slower()
    assert_two_zones_open_door_mix_humidity()
    assert_rh_is_derived_from_temperature_and_humidity_ratio()
    assert_humidity_ratio_never_negative()
    assert_no_thermal_solver_calculated()
    assert_no_airflow_solver_recalculated_when_network_passed()

    print("")
    print("PHASE 6 HUMIDITY ARCHITECTURE OK ✅")


if __name__ == "__main__":
    run_tests()