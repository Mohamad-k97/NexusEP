"""Legacy compatibility entry point for the relocated graph regression test."""

from tests.regression.test_physics_graph_structure import *  # noqa: F401,F403


if __name__ == "__main__":
    run_tests()
