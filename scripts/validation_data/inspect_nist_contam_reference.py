"""Verify exact locally held NIST AIRNET/CONTAM reference reports."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

REPORTS = {
    "airnet": {
        "sha256": "1d5c8763238302d41aa44adc3c9e716cb0854e0d2df21560a9f7d67b70e0978f",
        "byte_size": 3_890_544,
    },
    "contam": {
        "sha256": "ccdca593a0b30da45bca32cadea73ba709212b08765e2b2247a36dc6d495be30",
        "byte_size": 6_985_102,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=sorted(REPORTS))
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    expected = REPORTS[args.profile]
    if not args.pdf.is_file():
        raise FileNotFoundError(args.pdf)
    if args.pdf.stat().st_size != expected["byte_size"]:
        raise ValueError(
            f"unexpected {args.profile} byte size: {args.pdf.stat().st_size}"
        )
    if args.pdf.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"not a PDF file: {args.pdf}")
    actual_sha256 = _sha256(args.pdf)
    if actual_sha256 != expected["sha256"]:
        raise ValueError(
            f"unexpected {args.profile} SHA-256: {actual_sha256}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
