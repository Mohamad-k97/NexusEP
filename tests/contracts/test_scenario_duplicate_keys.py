"""Canonical documents must never silently overwrite duplicate keys."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexusep.scenarios.loader import load_scenario
from nexusep.scenarios.validation import ScenarioValidationError

pytestmark = pytest.mark.contract


def test_scenario_loader_rejects_duplicate_nested_key(tmp_path: Path) -> None:
    path = tmp_path / "scenario.jsonc"
    path.write_text(
        """{
          "schema_version": "1.0.0",
          "metadata": {"name": "first", "name": "second"}
        }""",
        encoding="utf-8",
    )
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(path)
    assert captured.value.issues[0].path == "/metadata/name"
    assert captured.value.issues[0].error_type == "duplicate_json_key"
    assert str(path) in captured.value.issues[0].message
