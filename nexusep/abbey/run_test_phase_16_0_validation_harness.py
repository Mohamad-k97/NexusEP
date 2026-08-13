"""Compatibility entry point for the relocated Phase 16.0 pytest module."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/phase16/test_16_0_validation_harness.py"))
