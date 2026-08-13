"""Phase 17.3 engine-to-performance adapter contract.

Provenance: reconstructed from the Phase 17.3 adapter docstrings and public
fields in ``BuildingPhysicsPerformanceModel``. The original June 29 script was
not recovered from Git, IDE backups, archives, or compiled caches.
"""

from nexusep.abbey.building import BuildingPhysicsPerformanceModel
from nexusep.abbey.building.performance import (
    BUILDING_PERFORMANCE_PATH_ENGINE,
    BuildingPerformanceStepResult,
)
from tests.phase16.test_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_graph,
    make_phase16_performance_input,
    make_phase16_weather,
)


def make_adapter_case():
    building = make_phase16_building()
    graph = make_phase16_graph(building)
    weather = make_phase16_weather(
        outdoor_temperature_c=4.0,
        outdoor_co2_ppm=418.0,
        wind_speed_m_s=2.0,
        global_horizontal_radiation_w_m2=180.0,
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
        step=3,
        day=0,
        hour=9.5,
        people={},
        locations={},
        chunk_records=[],
    )
    result = model.step(performance_input=performance_input, dt_minutes=10.0)
    return building, model, result


def test_engine_result_is_adapted_without_replacing_engine_payloads():
    _, model, result = make_adapter_case()

    assert isinstance(result, BuildingPerformanceStepResult)
    assert result.physics_engine_active is True
    assert result.performance_path == BUILDING_PERFORMANCE_PATH_ENGINE
    assert result.legacy_fallback_used is False
    assert result.legacy_fallback_reason is None
    assert result.physics_engine_error is None
    assert result.physics_engine_result is model.last_physics_engine_result
    assert result.physics_engine_result is not None
    assert result.internal_source_result is result.physics_engine_result.internal_source_result
    assert result.physics_inputs == (result.physics_engine_result.physics_inputs or {})


def test_adapter_produces_one_public_record_per_engine_zone():
    building, _, result = make_adapter_case()

    expected_zone_ids = set(building.all_zone_models())
    public_by_zone = {row["zone_id"]: row for row in result.zone_records}
    engine_by_zone = {
        row["zone_id"]: row for row in result.physics_engine_result.zone_records
    }

    assert set(public_by_zone) == expected_zone_ids
    assert set(engine_by_zone) == expected_zone_ids

    for zone_id in expected_zone_ids:
        public_row = public_by_zone[zone_id]
        state = building.get_zone_state(zone_id)

        assert public_row["physics_engine_active"] is True
        assert public_row["performance_path"] == BUILDING_PERFORMANCE_PATH_ENGINE
        assert public_row["legacy_fallback_used"] is False
        assert public_row["physics_engine_source"] == result.physics_engine_result.source
        assert float(public_row["indoor_temp_c"]) == float(state.indoor_temp_c)
        assert float(public_row["co2_ppm"]) == float(state.co2_ppm)


def test_adapter_building_status_matches_step_result():
    _, _, result = make_adapter_case()
    record = result.building_record

    assert record["physics_engine_active"] is result.physics_engine_active
    assert record["performance_path"] == result.performance_path
    assert record["legacy_fallback_used"] is result.legacy_fallback_used
    assert record["legacy_fallback_reason"] is result.legacy_fallback_reason
    assert record["physics_engine_source"] == result.physics_engine_result.source
