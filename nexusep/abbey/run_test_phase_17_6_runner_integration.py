"""Compatibility entry point for the reconstructed Phase 17.6 tests."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/phase17/test_17_6_runner_integration.py"))
