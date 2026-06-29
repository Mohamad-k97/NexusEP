"""
ABBEY Phase 16.0 validation harness.

Goal:
    deterministic helpers used by all Phase 16 sanity tests.

Run:
    python run_test_phase_16_0_validation_harness.py
"""

from datetime import datetime
import copy

import pandas as pd

from nexusep.abbey.building.factory import (
    make_default_family_building,
    make_default_family_physics_graph,
)
from nexusep.abbey.building.performance import (
    SimpleBuildingPerformanceModel,
)
from nexusep.abbey.building.physics.weather import WeatherState
from nexusep.abbey.building.outputs import (
    OUTPUT_MODE_STANDARD,
    validate_building_output_dataframes,
)


# ============================================================
# BASIC ASSERTIONS
# ============================================================

def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_close_enough(value, expected, tolerance, message):
    residual = abs(float(value) - float(expected))

    if residual > float(tolerance):
        raise AssertionError(
            message
            + " Got "
            + str(value)
            + ", expected "
            + str(expected)
            + ", tolerance "
            + str(tolerance)
        )


def assert_direction(
    before,
    after,
    direction,
    message,
    tolerance=1e-9,
):
    before = float(before)
    after = float(after)
    tolerance = float(tolerance)
    direction = str(direction).strip().lower()

    if direction in ("increase", "increases", "greater", "up"):
        ok = after > before + tolerance

    elif direction in ("decrease", "decreases", "less", "down"):
        ok = after < before - tolerance

    elif direction in ("nondecrease", "non_decrease", "same_or_up"):
        ok = after >= before - tolerance

    elif direction in ("nonincrease", "non_increase", "same_or_down"):
        ok = after <= before + tolerance

    else:
        raise ValueError("Unknown direction: " + str(direction))

    if not ok:
        raise AssertionError(
            message
            + " Direction check failed. before="
            + str(before)
            + ", after="
            + str(after)
            + ", expected="
            + direction
        )


def assert_validation_ok(
    zone_df,
    dwelling_df,
    building_df,
    mode=OUTPUT_MODE_STANDARD,
    tolerance_wh=1e-6,
):
    validation = validate_building_output_dataframes(
        zone_df=zone_df,
        dwelling_df=dwelling_df,
        building_df=building_df,
        mode=mode,
        tolerance_wh=tolerance_wh,
    )

    if not validation["ok"]:
        raise AssertionError(
            "Output validation failed:\n"
            + "errors="
            + str(validation.get("errors", []))
            + "\nmissing_columns="
            + str(validation.get("missing_columns", []))
            + "\nnon_finite_columns="
            + str(validation.get("non_finite_columns", {}))
            + "\nout_of_range_columns="
            + str(validation.get("out_of_range_columns", {}))
            + "\nenergy_checks="
            + str(validation.get("energy_checks", {}))
        )

    return validation


# ============================================================
# PHASE 16 FACTORY HELPERS
# ============================================================

def make_phase16_building():
    """
    Deterministic default Phase 16 building.

    Keep this boring:
        one building
        one dwelling
        default private zones
    """
    return make_default_family_building()


def make_phase16_graph(building=None):
    if building is None:
        building = make_phase16_building()

    return make_default_family_physics_graph(
        building_model=building,
    )


def make_phase16_weather(
    outdoor_temperature_c=10.0,
    outdoor_co2_ppm=420.0,
    wind_speed_m_s=0.2,
    wind_direction_deg=0.0,
    direct_normal_radiation_w_m2=0.0,
    diffuse_horizontal_radiation_w_m2=0.0,
    global_horizontal_radiation_w_m2=0.0,
    outdoor_illuminance_lux=0.0,
    relative_humidity_percent=50.0,
    outdoor_noise_db=45.0,
    dt=None,
):
    if dt is None:
        dt = datetime(2026, 1, 1, 12, 0, 0)

    return WeatherState(
        datetime=dt,
        outdoor_temperature_c=float(outdoor_temperature_c),
        wind_speed_m_s=float(wind_speed_m_s),
        wind_direction_deg=float(wind_direction_deg),
        direct_normal_radiation_w_m2=float(direct_normal_radiation_w_m2),
        diffuse_horizontal_radiation_w_m2=float(diffuse_horizontal_radiation_w_m2),
        global_horizontal_radiation_w_m2=float(global_horizontal_radiation_w_m2),
        outdoor_illuminance_lux=float(outdoor_illuminance_lux),
        outdoor_co2_ppm=float(outdoor_co2_ppm),
        outdoor_noise_db=float(outdoor_noise_db),
        relative_humidity_percent=float(relative_humidity_percent),
        atmospheric_pressure_pa=101325.0,
        sky_condition="synthetic",
    )


def phase16_zone_ids(building):
    if hasattr(building, "all_zone_ids"):
        return list(building.all_zone_ids())

    if hasattr(building, "all_zone_models"):
        return list(building.all_zone_models().keys())

    raise AttributeError("Building object has no all_zone_ids/all_zone_models helper.")


def phase16_first_zone_id(building):
    zone_ids = phase16_zone_ids(building)

    if not zone_ids:
        raise ValueError("Phase 16 building has no zones.")

    return zone_ids[0]


def make_phase16_role_to_zone_id(building):
    out = {}

    for zone_id in phase16_zone_ids(building):
        text = str(zone_id)

        if text.startswith("dwelling_1_"):
            role = text.replace("dwelling_1_", "", 1)
        else:
            role = text

        out[role] = zone_id
        out[zone_id] = zone_id

    return out


def make_phase16_person(
    person_id,
):
    """
    Minimal person row.

    Internal-source code can accept richer people later.
    For 16.0 smoke tests, this only needs a stable ID.
    """
    return {
        "person_id": person_id,
    }


def make_phase16_location(
    zone_id,
    is_home=True,
):
    """
    Dict form is intentional.

    performance._map_occupancy_by_zone(...) accepts both object and dict style.
    """
    return {
        "is_home": bool(is_home),
        "current_space_id": zone_id,
    }


def make_phase16_performance_input(
    building,
    graph=None,
    weather_state=None,
    step=0,
    day=0,
    hour=0.0,
    locations=None,
    people=None,
    chunk_records=None,
    role_to_zone_id=None,
    outdoor_temp_c=None,
    outdoor_co2_ppm=None,
):
    if graph is None:
        graph = make_phase16_graph(building)

    if weather_state is None:
        weather_state = make_phase16_weather()

    if locations is None:
        locations = {}

    if people is None:
        people = {}

    if chunk_records is None:
        chunk_records = []

    if role_to_zone_id is None:
        role_to_zone_id = make_phase16_role_to_zone_id(building)

    if outdoor_temp_c is None:
        outdoor_temp_c = weather_state.outdoor_temperature_c

    if outdoor_co2_ppm is None:
        outdoor_co2_ppm = weather_state.outdoor_co2_ppm

    return {
        "step": step,
        "day": day,
        "hour": hour,
        "observation": None,
        "locations": locations,
        "people": people,
        "chunk_records": chunk_records,
        "role_to_zone_id": role_to_zone_id,
        "physics_graph": graph,
        "weather_state": weather_state,
        "outdoor_temp_c": outdoor_temp_c,
        "outdoor_co2_ppm": outdoor_co2_ppm,
    }


# ============================================================
# PHASE 16 RUNNER HELPER
# ============================================================

def run_phase16_case(
    building=None,
    graph=None,
    weather_state=None,
    dt_minutes=10.0,
    number_of_steps=1,
    use_physics_engine=True,
    allow_legacy_physics_fallback=False,
    locations=None,
    people=None,
    chunk_records=None,
    validate_outputs=True,
    validation_mode=OUTPUT_MODE_STANDARD,
):
    if building is None:
        building = make_phase16_building()
    else:
        building = copy.deepcopy(building)

    if graph is None and use_physics_engine:
        graph = make_phase16_graph(building)

    if weather_state is None:
        weather_state = make_phase16_weather()

    model = SimpleBuildingPerformanceModel(
        building_model=building,
        physics_graph=graph,
        use_physics_engine=use_physics_engine,
        allow_legacy_physics_fallback=allow_legacy_physics_fallback,
    )

    if locations is None:
        locations = {}

    if people is None:
        people = {}

    if chunk_records is None:
        chunk_records = []

    results = []

    for step in range(int(number_of_steps)):
        hour = float(step) * float(dt_minutes) / 60.0

        performance_input = make_phase16_performance_input(
            building=building,
            graph=graph,
            weather_state=weather_state,
            step=step,
            day=0,
            hour=hour,
            locations=locations,
            people=people,
            chunk_records=chunk_records,
        )

        result = model.step(
            performance_input=performance_input,
            dt_minutes=dt_minutes,
        )

        results.append(result)

    zone_rows = []
    dwelling_rows = []
    building_rows = []

    for result in results:
        zone_rows.extend(result.zone_records)
        dwelling_rows.extend(result.dwelling_records)
        building_rows.append(result.building_record)

    zone_df = pd.DataFrame(zone_rows)
    dwelling_df = pd.DataFrame(dwelling_rows)
    building_df = pd.DataFrame(building_rows)

    validation = None

    if validate_outputs:
        validation = assert_validation_ok(
            zone_df=zone_df,
            dwelling_df=dwelling_df,
            building_df=building_df,
            mode=validation_mode,
        )

    return {
        "building": building,
        "graph": graph,
        "weather_state": weather_state,
        "model": model,
        "results": results,
        "last_result": results[-1],
        "zone_df": zone_df,
        "dwelling_df": dwelling_df,
        "building_df": building_df,
        "validation": validation,
    }


# ============================================================
# SMOKE TESTS
# ============================================================

def test_make_phase16_building_and_graph():
    building = make_phase16_building()
    graph = make_phase16_graph(building)

    zone_ids = phase16_zone_ids(building)

    assert_true(
        len(zone_ids) > 0,
        "Phase 16 building should have zones.",
    )

    assert_true(
        graph is not None,
        "Phase 16 graph should not be None.",
    )

    print("PASS: test_make_phase16_building_and_graph")


def test_make_phase16_weather():
    weather = make_phase16_weather(
        outdoor_temperature_c=7.5,
        outdoor_co2_ppm=415.0,
        relative_humidity_percent=55.0,
    )

    assert_close_enough(
        weather.outdoor_temperature_c,
        7.5,
        1e-9,
        "Weather outdoor temperature mismatch.",
    )

    assert_close_enough(
        weather.outdoor_co2_ppm,
        415.0,
        1e-9,
        "Weather outdoor CO2 mismatch.",
    )

    print("PASS: test_make_phase16_weather")


def test_make_phase16_performance_input():
    building = make_phase16_building()
    graph = make_phase16_graph(building)
    weather = make_phase16_weather()

    first_zone = phase16_first_zone_id(building)

    people = {
        "person_1": make_phase16_person("person_1"),
    }

    locations = {
        "person_1": make_phase16_location(first_zone),
    }

    performance_input = make_phase16_performance_input(
        building=building,
        graph=graph,
        weather_state=weather,
        step=3,
        day=0,
        hour=0.5,
        locations=locations,
        people=people,
    )

    assert_true(
        performance_input["step"] == 3,
        "Performance input step mismatch.",
    )

    assert_true(
        performance_input["locations"]["person_1"]["current_space_id"] == first_zone,
        "Performance input location mismatch.",
    )

    assert_true(
        performance_input["weather_state"] is weather,
        "Performance input should keep the provided weather state.",
    )

    print("PASS: test_make_phase16_performance_input")


def test_run_phase16_case_engine_smoke():
    out = run_phase16_case(
        dt_minutes=10.0,
        number_of_steps=2,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        validate_outputs=True,
        validation_mode=OUTPUT_MODE_STANDARD,
    )

    zone_df = out["zone_df"]
    dwelling_df = out["dwelling_df"]
    building_df = out["building_df"]

    assert_true(
        not zone_df.empty,
        "Engine smoke zone dataframe should not be empty.",
    )

    assert_true(
        not dwelling_df.empty,
        "Engine smoke dwelling dataframe should not be empty.",
    )

    assert_true(
        not building_df.empty,
        "Engine smoke building dataframe should not be empty.",
    )

    for column in [
        "indoor_relative_humidity_percent",
        "indoor_humidity_ratio_kg_kg",
        "physics_path",
        "total_energy_wh",
    ]:
        assert_true(
            column in zone_df.columns,
            "Engine smoke zone_df missing " + column,
        )

    physics_paths = set(
        str(value)
        for value in zone_df["physics_path"].dropna().unique()
    )

    assert_true(
        physics_paths == set(["engine"]),
        "Engine smoke unexpected physics_path values: " + str(physics_paths),
    )

    print("PASS: test_run_phase16_case_engine_smoke")


def test_run_phase16_case_legacy_smoke():
    out = run_phase16_case(
        dt_minutes=10.0,
        number_of_steps=2,
        use_physics_engine=False,
        allow_legacy_physics_fallback=True,
        validate_outputs=True,
        validation_mode=OUTPUT_MODE_STANDARD,
    )

    zone_df = out["zone_df"]

    assert_true(
        not zone_df.empty,
        "Legacy smoke zone dataframe should not be empty.",
    )

    assert_true(
        "physics_path" in zone_df.columns,
        "Legacy smoke zone_df missing physics_path.",
    )

    physics_paths = set(
        str(value)
        for value in zone_df["physics_path"].dropna().unique()
    )

    assert_true(
        physics_paths == set(["legacy_fallback_explicit"]),
        "Legacy smoke unexpected physics_path values: " + str(physics_paths),
    )

    print("PASS: test_run_phase16_case_legacy_smoke")


def test_assert_direction_helper():
    assert_direction(
        before=1.0,
        after=2.0,
        direction="increase",
        message="Increase helper should pass.",
    )

    assert_direction(
        before=2.0,
        after=1.0,
        direction="decrease",
        message="Decrease helper should pass.",
    )

    print("PASS: test_assert_direction_helper")


if __name__ == "__main__":
    test_make_phase16_building_and_graph()
    test_make_phase16_weather()
    test_make_phase16_performance_input()
    test_run_phase16_case_engine_smoke()
    test_run_phase16_case_legacy_smoke()
    test_assert_direction_helper()

    print("Phase 16.0 validation harness tests passed.")