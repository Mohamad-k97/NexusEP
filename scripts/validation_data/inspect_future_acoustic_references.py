"""Inspect future acoustic references without treating them as current evidence."""

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


def inspect_ptb(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    required = (
        "The Room Acoustics Absorption Coefficient Database",
        "More than 2000 data sets are available",
        "Excel 97 file with absorption data",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise ValueError(f"PTB overview lacks expected markers: {missing}")
    return {
        "source_id": "ptb-absorption-database-overview",
        "path": path.as_posix(),
        "byte_size": path.stat().st_size,
        "sha256": _sha256(path),
        "dataset_downloaded": False,
        "scientific_result_claimed": False,
    }


def inspect_motus(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("doi") != "10.5281/zenodo.4923187":
        raise ValueError("unexpected Motus DOI")
    metadata = payload.get("metadata", {})
    if metadata.get("version") != "1.0":
        raise ValueError("unexpected Motus version")
    if metadata.get("license", {}).get("id") != "cc-by-4.0":
        raise ValueError("unexpected Motus license")
    files = payload.get("files", [])
    if len(files) != 7:
        raise ValueError("unexpected Motus file inventory")
    return {
        "source_id": "aalto-motus-1-0-metadata",
        "path": path.as_posix(),
        "byte_size": path.stat().st_size,
        "sha256": _sha256(path),
        "doi": payload["doi"],
        "version": metadata["version"],
        "license": metadata["license"]["id"],
        "file_count": len(files),
        "total_dataset_bytes": sum(int(item["size"]) for item in files),
        "dataset_downloaded": False,
        "scientific_result_claimed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("ptb", "motus"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    result = inspect_ptb(args.path) if args.kind == "ptb" else inspect_motus(args.path)
    print(json.dumps({"validation_category": "future_source_gate", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
