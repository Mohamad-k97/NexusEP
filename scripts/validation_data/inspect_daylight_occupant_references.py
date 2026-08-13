"""Inspect retrieved Phase 4.21-4.24 reference metadata without claiming results."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_file(path: Path) -> dict[str, str | int]:
    payload = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-2048:]:
            raise ValueError(f"incomplete PDF: {path}")
        file_type = "pdf"
    elif suffix in {".html", ".htm"}:
        lower = payload[:8192].lower()
        if b"<html" not in lower and b"<!doctype html" not in lower:
            raise ValueError(f"not recognizable HTML: {path}")
        file_type = "html"
    elif suffix == ".json":
        json.loads(payload)
        file_type = "json"
    else:
        raise ValueError(f"unsupported reference file type: {path}")
    return {
        "path": path.as_posix(),
        "type": file_type,
        "byte_size": len(payload),
        "sha256": _sha256(path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                "validation_category": "source_registration_only",
                "source_id": args.source_id,
                "files": [inspect_file(path) for path in args.files],
                "scientific_result_claimed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
