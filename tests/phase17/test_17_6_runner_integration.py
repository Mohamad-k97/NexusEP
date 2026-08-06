"""Phase 17.6 runner-integration contract.

Provenance: reconstructed from ``AbbeySimulation`` integration points, the
surviving Phase 17.1/17.2/17.4 tests, and v0.4 runner assertions. The original
June 29 script was not recovered; its filename later held a Phase 18 scorer
comparison.
"""

from pathlib import Path

from nexusep.abbey.building import BuildingPhysicsPerformanceModel
from nexusep.abbey.simulation.runner import AbbeySimulation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "nexusep" / "data" / "abbey" / "config" / "abbey_config.jsonc"


def make_short_simulation():
    return AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.1,
        dt_minutes=1.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
    )


def test_runner_initializes_the_engine_backed_model_and_graph():
    sim = make_short_simulation()

    assert isinstance(sim.building_performance_model, BuildingPhysicsPerformanceModel)
    assert sim.building_model is not None
    assert sim.building_physics_graph is not None
    assert sim.building_performance_model.physics_graph is sim.building_physics_graph
    assert sim.building_performance_model.allow_legacy_physics_fallback is False


def test_one_runner_step_stores_engine_outputs_across_public_collections():
    sim = make_short_simulation()
    zone_count = len(sim.building_model.all_zone_models())

    sim.step()

    assert len(sim.building_zone_records) == zone_count
    assert len(sim.building_dwelling_records) > 0
    assert len(sim.building_records) == 1
    assert sim.last_internal_source_result is not None
    assert all(row["physics_engine_active"] is True for row in sim.building_zone_records)
    assert all(row["legacy_fallback_used"] is False for row in sim.building_zone_records)
    assert sim.building_records[-1]["performance_path"] == "engine"
    assert sim.building_records[-1]["legacy_fallback_used"] is False


def test_active_building_engine_does_not_call_the_old_dummy_model():
    sim = make_short_simulation()

    class ForbiddenLegacyModel:
        def step(self, *args, **kwargs):
            raise AssertionError("legacy performance model was called")

    sim.performance_model = ForbiddenLegacyModel()
    sim.step()

    assert sim.building_records[-1]["performance_path"] == "engine"


def main():
    test_runner_initializes_the_engine_backed_model_and_graph()
    test_one_runner_step_stores_engine_outputs_across_public_collections()
    test_active_building_engine_does_not_call_the_old_dummy_model()
    print("Phase 17.6 runner integration tests passed.")


if __name__ == "__main__":
    main()
