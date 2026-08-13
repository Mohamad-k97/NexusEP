"""Verification that validation artifacts make their evidence category explicit."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
VALIDATION_CATEGORY = "verification"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _validation_reports() -> list[Path]:
    reports = []
    for directory in ("baseline", "validation", "verification"):
        reports.extend((REPOSITORY_ROOT / "docs" / directory).rglob("*.md"))
    reports.extend(
        (
            REPOSITORY_ROOT / "docs/architecture/conformance_report_v1.md",
            REPOSITORY_ROOT / "docs/architecture/initial_parity_report_v1.md",
        )
    )
    return sorted(reports)


@pytest.mark.parametrize("report_path", _validation_reports(), ids=lambda path: path.name)
def test_every_validation_report_declares_its_category(report_path: Path) -> None:
    opening = "\n".join(report_path.read_text(encoding="utf-8").splitlines()[:8])
    assert "Validation category:" in opening
