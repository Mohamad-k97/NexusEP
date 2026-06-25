from types import SimpleNamespace

from nexusep.abbey.building.factory import make_default_family_building
from nexusep.abbey.building.performance import SimpleBuildingPerformanceModel
from nexusep.abbey.building.systems import ZoneControlState


class DummyLocation:
    def __init__(self, occupant_id, zone_id):
        self.occupant_id = occupant_id
        self.building_id = "dummy_building_1"
        self.dwelling_id = "dwelling_1"
        self.is_home = True
        self.current_space_id = zone_id
        self.current_space_role = "idle"
        self.current_activity = "idle"
        self.away_reason = "none"


def make_weather(outdoor_temp_c):
    return SimpleNamespace(
        datetime=None,
        outdoor_temperature_c=float(outdoor_temp_c),
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        global_horizontal_radiation_w_m2=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        relative_humidity_percent=50.0,
        atmospheric_pressure_pa=101325.0,
    )


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_false(value, message):
    if value:
        raise AssertionError(message)


def get_living_zone_id(building):
    preferred = "dwelling_1_living_room"

    if preferred in building.all_zone_ids():
        return preferred

    return building.all_zone_ids()[0]


def test_engine_path_is_default_and_no_fallback_used():
    building = make_default_family_building()
    zone_id = get_living_zone_id(building)
    dwelling = building.dwellings["dwelling_1"]

    old_state = building.get_zone_state(zone_id)

    building.set_zone_state(
        zone_id,
        old_state.copy(
            indoor_temp_c=18.0,
            indoor_mass_temp_c=18.0,
            co2_ppm=700.0,
        ),
    )

    dwelling.system_specs[zone_id] = dwelling.system_specs[zone_id].copy(
        has_heating=True,
        heating_capacity_w=3000.0,
    )

    dwelling.control_states[zone_id] = ZoneControlState(
        zone_id=zone_id,
        dwelling_id="dwelling_1",
        building_id="dummy_building_1",
        heating_mode="manual",
        manual_heating_on=True,
        heating_setpoint_c=20.0,
        cooling_mode="off",
        cooling_setpoint_c=26.0,
        ventilation_mode="off",
    )

    model = SimpleBuildingPerformanceModel(
        building_model=building,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
    )

    result = model.step(
        performance_input={
            "step": 0,
            "day": 0,
            "hour": 0.0,
            "outdoor_temp_c": 18.0,
            "locations": {
                "person_1": DummyLocation("person_1", zone_id),
            },
            "people": {},
            "chunk_records": [],
            "role_to_zone_id": {},
            "weather_state": make_weather(18.0),
        },
        dt_minutes=15.0,
    )

    assert_true(result.physics_engine_active, "Engine should be active.")
    assert_false(result.legacy_fallback_used, "Fallback should not be used.")
    assert_true(
        result.performance_path == "engine",
        "Performance path should be engine.",
    )

    building_record = result.building_record

    assert_false(
        building_record.get("legacy_fallback_used", True),
        "Building record should expose fallback_used=False.",
    )

    for row in result.zone_records:
        assert_false(
            row.get("legacy_fallback_used", True),
            "Zone record should expose fallback_used=False.",
        )

    print("PASS: test_engine_path_is_default_and_no_fallback_used")


def test_explicit_legacy_mode_is_labeled():
    building = make_default_family_building()
    zone_id = get_living_zone_id(building)

    model = SimpleBuildingPerformanceModel(
        building_model=building,
        use_physics_engine=False,
        allow_legacy_physics_fallback=True,
    )

    result = model.step(
        performance_input={
            "step": 0,
            "day": 0,
            "hour": 0.0,
            "outdoor_temp_c": 18.0,
            "locations": {
                "person_1": DummyLocation("person_1", zone_id),
            },
            "people": {},
            "chunk_records": [],
            "role_to_zone_id": {},
        },
        dt_minutes=15.0,
    )

    assert_false(result.physics_engine_active, "Engine should be inactive.")
    assert_true(result.legacy_fallback_used, "Fallback should be marked as used.")
    assert_true(
        result.performance_path == "legacy_fallback_explicit",
        "Explicit legacy mode should be labeled.",
    )

    assert_true(
        result.building_record.get("legacy_fallback_used", False),
        "Building record should expose fallback_used=True.",
    )

    print("PASS: test_explicit_legacy_mode_is_labeled")


if __name__ == "__main__":
    test_engine_path_is_default_and_no_fallback_used()
    test_explicit_legacy_mode_is_labeled()
    print("Phase 10.13 legacy-path quarantine tests passed.")