"""Verify locally held, non-redistributable NREL SPA contract material."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spa_header", type=Path)
    parser.add_argument("spa_tester", type=Path)
    args = parser.parse_args()
    header = args.spa_header.read_text(encoding="utf-8", errors="replace")
    tester = args.spa_tester.read_text(encoding="utf-8", errors="replace")
    required_header_terms = ("zenith", "azimuth", "atmos_refract", "delta_t")
    required_tester_terms = ("50.111622", "194.340241", "spa_calculate")
    missing = [term for term in required_header_terms if term not in header]
    missing.extend(term for term in required_tester_terms if term not in tester)
    if missing:
        raise ValueError(f"NREL SPA contract material is missing terms: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
