"""Inspect the pinned EnergyPlus 25.1 reference files without executing them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def inspect_reference(
    executable: Path,
    idd: Path,
    license_path: Path,
    weather: Path,
) -> dict[str, object]:
    executable_bytes = executable.read_bytes()
    if not executable_bytes.startswith(b"MZ"):
        raise ValueError("EnergyPlus executable does not have a Windows PE signature")

    idd_text = idd.read_text(encoding="utf-8", errors="replace")
    if "EnergyPlus" not in idd_text or "25.1" not in idd_text[:1000]:
        raise ValueError("IDD does not identify EnergyPlus 25.1")

    license_text = license_path.read_text(encoding="utf-8", errors="replace")
    if "Redistribution and use in source and binary forms" not in license_text:
        raise ValueError("EnergyPlus BSD redistribution clause was not found")

    weather_header = weather.open("rb").readline().decode("utf-8", errors="replace")
    if not weather_header.startswith("LOCATION,") or ",724666," not in weather_header:
        raise ValueError("unexpected EnergyPlus comparison weather file")

    return {
        "validation_category": "comparative_validation_source",
        "energyplus_version": "25.1.0-68a4a7c774",
        "executable_byte_size": len(executable_bytes),
        "idd_byte_size": idd.stat().st_size,
        "license": "BSD-3-Clause",
        "weather_location": "Golden-NREL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("idd", type=Path)
    parser.add_argument("license", type=Path)
    parser.add_argument("weather", type=Path)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            inspect_reference(
                args.executable,
                args.idd,
                args.license,
                args.weather,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
