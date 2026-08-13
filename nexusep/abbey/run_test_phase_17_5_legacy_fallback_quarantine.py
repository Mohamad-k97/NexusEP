"""Compatibility entry point for the reconstructed Phase 17.5 tests."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(run_pytest_module("tests/phase17/test_17_5_legacy_fallback_quarantine.py"))
