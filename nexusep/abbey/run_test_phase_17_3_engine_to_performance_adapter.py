"""Compatibility entry point for the reconstructed Phase 17.3 tests."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/phase17/test_17_3_engine_to_performance_adapter.py"))
