"""Check that a retrieved NSRDB API guide documents the PSM download contract."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_documentation", type=Path)
    args = parser.parse_args()
    text = args.raw_documentation.read_text(encoding="utf-8", errors="replace").lower()
    required = (
        "psm",
        "global horizontal irradiance",
        "direct normal irradiance",
        "diffuse horizontal irradiance",
    )
    missing = [term for term in required if term not in text]
    if missing:
        raise ValueError(f"NSRDB API guide is missing contract terms: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
