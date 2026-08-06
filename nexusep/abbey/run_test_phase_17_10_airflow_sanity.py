"""Compatibility entry point for the relocated airflow regression tests."""

from tests.regression.test_airflow_sanity import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
