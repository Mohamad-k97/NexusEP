"""Global suite taxonomy and validation-category enforcement."""

from __future__ import annotations

import pytest

LANE_MARKERS = {"unit", "contract", "integration", "annual", "benchmark"}
PHASE17_CONTRACT_MODULES = {
    "test_17_1_model_rename.py",
    "test_17_2_performance_input_contract.py",
    "test_17_3_engine_to_performance_adapter.py",
    "test_17_4_observation_contract.py",
    "test_17_5_legacy_fallback_quarantine.py",
}


def _lane_for_path(path: str) -> str:
    normalized = "/" + path.replace("\\", "/").lower().lstrip("/")
    if (
        "/tests/phase17/" in normalized
        and normalized.rsplit("/", 1)[-1] in PHASE17_CONTRACT_MODULES
    ):
        return "contract"
    if "/tests/unit/" in normalized or "/tests/regression/" in normalized:
        return "unit"
    if any(
        segment in normalized
        for segment in (
            "/tests/contracts/",
            "/tests/adapters/",
            "/tests/conformance/",
            "/tests/scenarios/",
        )
    ):
        return "contract"
    if "/tests/annual/" in normalized:
        return "annual"
    if "/tests/benchmarks/" in normalized:
        return "benchmark"
    return "integration"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every collected test exactly one execution lane and claim category."""

    for item in items:
        existing = {
            marker.name for marker in item.iter_markers() if marker.name in LANE_MARKERS
        }
        if len(existing) > 1:
            raise pytest.UsageError(
                f"{item.nodeid} belongs to multiple test lanes: {sorted(existing)}"
            )
        if not existing:
            lane = _lane_for_path(str(item.path))
            item.add_marker(getattr(pytest.mark, lane))
        else:
            lane = next(iter(existing))
        if lane == "annual":
            item.add_marker(pytest.mark.slow)
        item.user_properties.append(("validation_category", "verification"))
        item.user_properties.append(("execution_lane", lane))
