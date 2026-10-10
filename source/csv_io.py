"""CSV templates in, completed CSVs out (GUIDE section 7.2).

The csv module handles quoting: cells containing commas, quotes or newlines are
quoted, and quotes inside the Level 1 JSON are doubled automatically.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def read_template(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (column names, rows) exactly as in the template, preserving row order."""
    if not path.is_file():
        raise FileNotFoundError(f"CSV template not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV template has no header: {path}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write UTF-8 CSV with minimal quoting; atomic so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def level1_cell(level1: dict) -> str:
    """Single-line JSON for the level1.csv ``json`` column."""
    return json.dumps(level1, ensure_ascii=False, separators=(",", ":"))
