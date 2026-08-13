"""Strict legacy configuration parsing tests for Phase 3.3."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexusep.abbey.utils.config_loader import load_jsonc, validate_abbey_config
from nexusep.jsonc import DuplicateJSONKeyError, loads_strict_json

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "expected_path"),
    [
        ('{"same": 1, "same": 2}', "$.same"),
        ('{"outer": {"same": 1, "same": 2}}', "$.outer.same"),
        (
            '{"actions": {"cook": {"power_w": 1, "power_w": 2}}}',
            "$.actions.cook.power_w",
        ),
    ],
)
def test_duplicate_keys_are_rejected_with_source_and_nested_path(
    text: str, expected_path: str
) -> None:
    with pytest.raises(DuplicateJSONKeyError) as captured:
        loads_strict_json(text, source="config.jsonc", jsonc=True)
    assert expected_path in str(captured.value)
    assert "config.jsonc" in str(captured.value)


def test_comments_cannot_create_false_duplicate_keys() -> None:
    result = loads_strict_json(
        '{"actual": 1, // "actual": 2\n "nested": {/* "key": 1 */ "key": 2}}',
        source="comments.jsonc",
        jsonc=True,
    )
    assert result == {"actual": 1, "nested": {"key": 2}}


def test_double_slash_inside_valid_jsonc_string_is_preserved() -> None:
    result = loads_strict_json(
        '{"url": "https://example.invalid/a//b"}',
        source="strings.jsonc",
        jsonc=True,
    )
    assert result["url"] == "https://example.invalid/a//b"


def test_load_jsonc_reports_duplicate_path_and_source(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonc"
    path.write_text('{"hunger": {"cook_down": 1, "cook_down": 2}}')
    with pytest.raises(ValueError, match=r"\$\.hunger\.cook_down") as captured:
        load_jsonc(path)
    assert str(path) in str(captured.value)


def test_config_validation_rejects_unknown_top_level_and_action_fields() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "nexusep"
        / "data"
        / "abbey"
        / "config"
        / "abbey_config.jsonc"
    )
    valid = load_jsonc(config_path)
    unknown_section = json.loads(json.dumps(valid))
    unknown_section["typo_section"] = {}
    with pytest.raises(KeyError, match="typo_section"):
        validate_abbey_config(unknown_section)

    unknown_action_field = json.loads(json.dumps(valid))
    unknown_action_field["actions"]["cook"]["powre_w"] = 1
    with pytest.raises(KeyError, match="powre_w"):
        validate_abbey_config(unknown_action_field)


def test_config_validation_reports_missing_keys_without_debug_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(KeyError, match="hunger"):
        validate_abbey_config({})
    assert capsys.readouterr().out == ""
