"""Phase 17.5 legacy-fallback quarantine contract.

Provenance: reconstructed from the surviving model flags, path constants,
fallback branch, and runner defaults. The original June 29 script was not
recovered; the frozen Phase 17.5 filename held a Phase 18 moisture experiment.
"""

import pytest

from nexusep.abbey.building import BuildingPhysicsPerformanceModel
from nexusep.abbey.building.performance import (
    BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_AFTER_ENGINE_ERROR,
    BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_EXPLICIT,
)
from tests.phase16.test_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_graph,
    make_phase16_performance_input,
    make_phase16_weather,
)


def make_model_and_input(*, use_engine=True, allow_fallback=False):
    building = make_phase16_building()
    graph = make_phase16_graph(building)
    model = BuildingPhysicsPerformanceModel(
        building_model=building,
        physics_graph=graph,
        use_physics_engine=use_engine,
        allow_legacy_physics_fallback=allow_fallback,
    )
    performance_input = make_phase16_performance_input(
        building=building,
        graph=graph,
        weather_state=make_phase16_weather(),
        people={},
        locations={},
        chunk_records=[],
    )
    return model, performance_input


def test_engine_errors_propagate_when_fallback_is_not_explicitly_allowed(monkeypatch):
    model, performance_input = make_model_and_input(
        use_engine=True,
        allow_fallback=False,
    )

    def fail_engine(*args, **kwargs):
        raise RuntimeError("phase17-engine-failure")

    monkeypatch.setattr(model, "_run_physics_engine", fail_engine)

    with pytest.raises(RuntimeError, match="phase17-engine-failure"):
        model.step(performance_input=performance_input, dt_minutes=10.0)


def test_disabling_engine_marks_the_explicit_legacy_path():
    model, performance_input = make_model_and_input(
        use_engine=False,
        allow_fallback=False,
    )
    result = model.step(performance_input=performance_input, dt_minutes=10.0)

    assert result.physics_engine_active is False
    assert result.physics_engine_result is None
    assert result.performance_path == BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_EXPLICIT
    assert result.legacy_fallback_used is True
    assert result.legacy_fallback_reason == "use_physics_engine_false"
    assert all(row["legacy_fallback_used"] is True for row in result.zone_records)


def test_opt_in_failover_records_engine_error_and_quarantined_path(monkeypatch):
    model, performance_input = make_model_and_input(
        use_engine=True,
        allow_fallback=True,
    )

    def fail_engine(*args, **kwargs):
        raise RuntimeError("phase17-opt-in-failure")

    monkeypatch.setattr(model, "_run_physics_engine", fail_engine)
    result = model.step(performance_input=performance_input, dt_minutes=10.0)

    assert result.physics_engine_active is False
    assert result.performance_path == BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_AFTER_ENGINE_ERROR
    assert result.legacy_fallback_used is True
    assert "phase17-opt-in-failure" in result.legacy_fallback_reason
    assert result.legacy_fallback_exception_category == "RuntimeError"
    assert result.physics_engine_error == result.legacy_fallback_reason
    assert result.building_record["legacy_fallback_used"] is True
    assert result.building_record["legacy_fallback_exception_category"] == "RuntimeError"
    assert all(row["legacy_fallback_used"] is True for row in result.zone_records)
    assert all(
        row["legacy_fallback_exception_category"] == "RuntimeError"
        for row in result.zone_records
    )
    assert all(row["legacy_fallback_used"] is True for row in result.dwelling_records)
    assert result.physics_engine_result is None
