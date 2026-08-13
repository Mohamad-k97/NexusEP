"""Executable comparative validation against EnergyPlus Ideal Loads 25.1."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validation_data.compare_energyplus_ideal_loads import compare

pytestmark = [pytest.mark.integration]
VALIDATION_CATEGORY = "comparative validation"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ENERGYPLUS_ROOT = Path("C:/EnergyPlusV25-1-0")


def test_supported_ideal_load_quantities_match_energyplus(tmp_path: Path) -> None:
    executable = ENERGYPLUS_ROOT / "energyplus.exe"
    weather = (
        ENERGYPLUS_ROOT
        / "WeatherData"
        / "USA_CO_Golden-NREL.724666_TMY3.epw"
    )
    if not executable.is_file() or not weather.is_file():
        pytest.skip("EnergyPlus 25.1 reference installation is not available")

    result = compare(
        energyplus_exe=executable,
        input_file=(
            REPOSITORY_ROOT
            / "data/validation/fixtures/energyplus-ideal-loads-25.1.0"
            / "energyplus_ideal_loads.idf"
        ),
        weather_file=weather,
        output_directory=tmp_path / "energyplus-output",
    )

    assert result["passed"] is True
    assert result["hour_count"] == 24
    assert result["energyplus_version"] == "EnergyPlus, Version 25.1.0-68a4a7c774"
