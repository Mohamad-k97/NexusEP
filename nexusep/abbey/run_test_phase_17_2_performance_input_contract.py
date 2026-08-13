"""Compatibility entry point for the recovered Phase 17.2 contract tests."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/phase17/test_17_2_performance_input_contract.py"))
