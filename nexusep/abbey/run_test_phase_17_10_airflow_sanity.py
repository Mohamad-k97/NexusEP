"""Compatibility entry point for the relocated airflow regression tests."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/regression/test_airflow_sanity.py"))
