"""Compatibility entry point for the reconstructed Phase 17.7 tests."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/phase17/test_17_7_debug_outputs.py"))
