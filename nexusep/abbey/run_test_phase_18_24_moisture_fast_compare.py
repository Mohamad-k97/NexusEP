"""Compatibility entry point for the Phase 18.24 pytest comparison."""

"""Compatibility entry point for the Phase 18.24 pytest comparison."""

from nexusep.abbey._pytest_compat import run_pytest_module


if __name__ == "__main__":
    raise SystemExit(
        run_pytest_module("tests/phase18/test_18_24_moisture_fast_compare.py")
    )


if __name__ == "__main__":
    main()
