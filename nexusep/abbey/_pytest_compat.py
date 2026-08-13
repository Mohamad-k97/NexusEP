"""Thin compatibility support for historical ``python -m`` test commands."""

from __future__ import annotations

from pathlib import Path


def run_pytest_module(relative_test_path: str) -> int:
    """Run one migrated pytest module without keeping a second test runner."""

    import pytest

    repository_root = Path(__file__).resolve().parents[2]
    return pytest.main([str(repository_root / relative_test_path), "-q"])


__all__ = ["run_pytest_module"]
