"""
ABBEY Phase 17.1 test.

Goal:
    Rename the public building performance model without breaking old imports.

Run:
    python -m pytest tests/phase17/test_17_1_model_rename.py

Provenance:
    adapted from surviving script `run_test_phase_17_1_model_rename.py` at
    frozen HEAD 7d2729173146536771935ffa92eabaa3c4000c53.
"""

from pathlib import Path

from nexusep.abbey.building import (
    BuildingPhysicsPerformanceModel,
    SimpleBuildingPerformanceModel,
    BuildingPerformanceStepResult,
)

from nexusep.abbey.building.performance import (
    BuildingPhysicsPerformanceModel as DirectBuildingPhysicsPerformanceModel,
    SimpleBuildingPerformanceModel as DirectSimpleBuildingPerformanceModel,
)

from nexusep.abbey.simulation.runner import AbbeySimulation

from tests.phase16.test_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_graph,
    make_phase16_weather,
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


def test_building_package_imports_work():
    assert_true(
        BuildingPhysicsPerformanceModel is not None,
        "BuildingPhysicsPerformanceModel import from nexusep.abbey.building failed.",
    )

    assert_true(
        SimpleBuildingPerformanceModel is not None,
        "SimpleBuildingPerformanceModel compatibility import failed.",
    )

    assert_true(
        BuildingPhysicsPerformanceModel is SimpleBuildingPerformanceModel,
        "SimpleBuildingPerformanceModel should be a compatibility alias.",
    )

    print("PASS: test_building_package_imports_work")


def test_direct_performance_imports_work():
    assert_true(
        DirectBuildingPhysicsPerformanceModel is not None,
        "Direct BuildingPhysicsPerformanceModel import failed.",
    )

    assert_true(
        DirectSimpleBuildingPerformanceModel is not None,
        "Direct SimpleBuildingPerformanceModel import failed.",
    )

    assert_true(
        DirectBuildingPhysicsPerformanceModel is DirectSimpleBuildingPerformanceModel,
        "Direct old/new performance imports should resolve to the same class.",
    )

    print("PASS: test_direct_performance_imports_work")


def run_one_step_with_model_class(model_class):
    building = make_phase16_building()
    graph = make_phase16_graph(building)
    weather = make_phase16_weather(
        outdoor_temperature_c=10.0,
        outdoor_co2_ppm=420.0,
        relative_humidity_percent=50.0,
    )

    model = model_class(
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
        locations={},
        people={},
        chunk_records=[],
    )

    result = model.step(
        performance_input=performance_input,
        dt_minutes=10.0,
    )

    return result


def assert_valid_engine_result(result, label):
    assert_true(
        isinstance(result, BuildingPerformanceStepResult),
        label + " should return BuildingPerformanceStepResult.",
    )

    assert_true(
        result.physics_engine_active,
        label + " should activate physics engine.",
    )

    assert_true(
        result.physics_engine_result is not None,
        label + " should expose physics_engine_result.",
    )

    assert_true(
        not result.legacy_fallback_used,
        label + " should not use legacy fallback.",
    )

    assert_true(
        result.performance_path == "engine",
        label + " should use performance_path='engine'.",
    )

    assert_true(
        len(result.zone_records) > 0,
        label + " should return zone records.",
    )

    assert_true(
        len(result.dwelling_records) > 0,
        label + " should return dwelling records.",
    )

    assert_true(
        bool(result.building_record),
        label + " should return building record.",
    )


def test_new_model_returns_building_performance_step_result():
    result = run_one_step_with_model_class(
        BuildingPhysicsPerformanceModel
    )

    assert_valid_engine_result(
        result=result,
        label="BuildingPhysicsPerformanceModel",
    )

    print("PASS: test_new_model_returns_building_performance_step_result")


def test_old_model_name_still_returns_building_performance_step_result():
    result = run_one_step_with_model_class(
        SimpleBuildingPerformanceModel
    )

    assert_valid_engine_result(
        result=result,
        label="SimpleBuildingPerformanceModel alias",
    )

    print("PASS: test_old_model_name_still_returns_building_performance_step_result")


def test_runner_initializes_with_new_model_by_default():
    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.1,
        dt_minutes=1.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
    )

    assert_true(
        sim.building_performance_model is not None,
        "Runner should initialize building_performance_model.",
    )

    assert_true(
        isinstance(sim.building_performance_model, BuildingPhysicsPerformanceModel),
        "Runner should prefer BuildingPhysicsPerformanceModel.",
    )

    assert_true(
        sim.building_model is not None,
        "Runner should initialize building_model.",
    )

    assert_true(
        sim.building_physics_graph is not None,
        "Runner should initialize building_physics_graph.",
    )

    print("PASS: test_runner_initializes_with_new_model_by_default")


def test_runner_one_step_external_call_style_still_works():
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
        len(sim.building_zone_records) > 0,
        "Runner one-step should produce building zone records.",
    )

    assert_true(
        len(sim.building_dwelling_records) > 0,
        "Runner one-step should produce building dwelling records.",
    )

    assert_true(
        len(sim.building_records) > 0,
        "Runner one-step should produce building records.",
    )

    zone_record = sim.building_zone_records[-1]

    assert_true(
        zone_record.get("physics_engine_active") is True,
        "Runner one-step should use active physics engine.",
    )

    assert_true(
        zone_record.get("physics_path") == "engine",
        "Runner one-step should use physics_path='engine'.",
    )

    assert_true(
        zone_record.get("legacy_fallback_used") is False,
        "Runner one-step should not use legacy fallback.",
    )

    print("PASS: test_runner_one_step_external_call_style_still_works")


def main():
    test_building_package_imports_work()
    test_direct_performance_imports_work()
    test_new_model_returns_building_performance_step_result()
    test_old_model_name_still_returns_building_performance_step_result()
    test_runner_initializes_with_new_model_by_default()
    test_runner_one_step_external_call_style_still_works()

    print("Phase 17.1 model rename tests passed.")


if __name__ == "__main__":
    main()
