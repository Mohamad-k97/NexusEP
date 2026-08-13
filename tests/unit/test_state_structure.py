"""Structural state protections for Phase 3.2."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from nexusep.abbey.agents.states import PersonState

pytestmark = pytest.mark.unit
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _is_dataclass_decorator(decorator: ast.expr) -> bool:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return (isinstance(target, ast.Name) and target.id == "dataclass") or (
        isinstance(target, ast.Attribute) and target.attr == "dataclass"
    )


def test_production_dataclasses_do_not_redeclare_fields() -> None:
    duplicates: list[str] = []
    for path in (REPOSITORY_ROOT / "nexusep").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not any(
                _is_dataclass_decorator(item) for item in node.decorator_list
            ):
                continue
            first_line_by_name: dict[str, int] = {}
            for statement in node.body:
                if not (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                ):
                    continue
                name = statement.target.id
                if name in first_line_by_name:
                    duplicates.append(
                        f"{path.relative_to(REPOSITORY_ROOT)}:{statement.lineno} "
                        f"{node.name}.{name} first declared at "
                        f"line {first_line_by_name[name]}"
                    )
                first_line_by_name[name] = statement.lineno
    assert duplicates == []


def test_person_state_field_ownership_and_defaults_are_unambiguous() -> None:
    names = [item.name for item in fields(PersonState)]
    assert len(names) == len(set(names))
    state = PersonState()
    assert state.household_id == "household_1"
    assert state.can_cook is True
    assert state.has_job is False


def test_person_state_serialization_round_trip() -> None:
    original = PersonState(
        occupant_id="resident_maria",
        household_id="home_north",
        current_zone_id="zone-kitchen-west",
        has_job=True,
        can_cook=False,
        hunger=0.73,
    )
    restored = PersonState(**original.to_dict())
    assert restored == original
