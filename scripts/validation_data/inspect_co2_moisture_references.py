"""Verify exact locally held QICO2 and Annex 41 reference reports."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

REPORTS = {
    "qico2": {
        "sha256": "4bc74cb11f616d953436235e89d863f83d402c0d6407cceb927ab5364a8c051b",
        "byte_size": 2_931_696,
    },
    "annex41": {
        "sha256": "c56ea7aa8fdb2df7898d14b389557abb149640a7e1fe524ba5a45649c6c2c868",
        "byte_size": 2_661_112,
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
