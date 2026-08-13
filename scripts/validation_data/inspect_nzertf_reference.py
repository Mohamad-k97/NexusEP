"""Inspect the official NZERTF publication and dataset checksum inventory.

This command registers source metadata only. It does not download measurement
channels, calibrate NexusEP, or inspect the blind-validation values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

REQUIRED_HOURLY_CHANNELS = (
    "Metadata-hour.csv",
    "HVAC-hour.csv",
    "IndEnv-hour.csv",
    "OutEnv-hour.csv",
    "Load-hour.csv",
    "Vent-hour.csv",
    "Elec-hour.csv",
)
YEAR_PROTOCOL = {
    "2014-data-files": {
        "role": "calibration",
        "period_start": "2013-07-01",
        "period_end_exclusive": "2014-07-01",
        "data_doi": "10.18434/T4/1503134",
    },
    "2015-data-files": {
        "role": "blind_validation",
        "period_start": "2015-02-01",
        "period_end_exclusive": "2016-02-01",
        "data_doi": "10.18434/T46W2X",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inspect_pdf(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    if not payload.startswith(b"%PDF-"):
        raise ValueError(f"not a PDF: {path}")
    if b"%%EOF" not in payload[-1024:]:
        raise ValueError(f"PDF has no terminal EOF marker: {path}")
    return {"path": str(path), "byte_size": len(payload)}


def _read_checksum_inventory(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = ["#file", "bytes", "md5hash", "sha256hash"]
        if reader.fieldnames != expected:
            raise ValueError(
                f"unexpected NZERTF checksum columns: {reader.fieldnames!r}"
            )
        rows = {row["#file"]: row for row in reader}

    for url, row in rows.items():
        if int(row["bytes"]) <= 0:
            raise ValueError(f"invalid byte size for {url}")
        if re.fullmatch(r"[0-9a-f]{32}", row["md5hash"]) is None:
            raise ValueError(f"invalid MD5 for {url}")
        if re.fullmatch(r"[0-9a-f]{64}", row["sha256hash"]) is None:
            raise ValueError(f"invalid SHA-256 for {url}")
    return rows


def inspect_reference(
    pdf_path: Path,
    checksum_path: Path,
    year1_metadata_path: Path,
    year2_metadata_path: Path,
) -> dict[str, object]:
    pdf = _inspect_pdf(pdf_path)
    rows = _read_checksum_inventory(checksum_path)
    years: dict[str, object] = {}
    for directory, protocol in YEAR_PROTOCOL.items():
        selected = []
        for filename in REQUIRED_HOURLY_CHANNELS:
            url = (
                "https://s3.amazonaws.com/nist-netzero/"
                f"{directory}/{filename}"
            )
            if url not in rows:
                raise ValueError(f"official checksum inventory lacks {url}")
            row = rows[url]
            selected.append(
                {
                    "url": url,
                    "byte_size": int(row["bytes"]),
                    "sha256": row["sha256hash"],
                }
            )
        years[directory] = {**protocol, "required_hourly_files": selected}

    metadata_status = {}
    for directory, path in (
        ("2014-data-files", year1_metadata_path),
        ("2015-data-files", year2_metadata_path),
    ):
        url = (
            "https://s3.amazonaws.com/nist-netzero/"
            f"{directory}/Metadata-hour.csv"
        )
        expected = rows[url]
        actual_sha256 = _sha256(path)
        actual_size = path.stat().st_size
        metadata_status[directory] = {
            "path": str(path),
            "actual_byte_size": actual_size,
            "actual_sha256": actual_sha256,
            "inventory_byte_size": int(expected["bytes"]),
            "inventory_sha256": expected["sha256hash"],
            "matches_inventory": (
                actual_size == int(expected["bytes"])
                and actual_sha256 == expected["sha256hash"]
            ),
        }

    if metadata_status["2014-data-files"]["matches_inventory"] is not True:
        raise ValueError("Year 1 metadata does not match the official inventory")
    if metadata_status["2015-data-files"]["matches_inventory"] is not False:
        raise ValueError(
            "Expected registered Year 2 metadata/inventory discrepancy changed; "
            "review the source before updating provenance"
        )

    return {
        "validation_category": "calibration_protocol_only",
        "publication": pdf,
        "checksum_inventory": {
            "path": str(checksum_path),
            "entry_count": len(rows),
        },
        "years": years,
        "downloaded_metadata_status": metadata_status,
        "result_claimed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("checksums", type=Path)
    parser.add_argument("year1_metadata", type=Path)
    parser.add_argument("year2_metadata", type=Path)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            inspect_reference(
                args.pdf,
                args.checksums,
                args.year1_metadata,
                args.year2_metadata,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
