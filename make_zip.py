"""Build submission.zip and verify it against the WTQ submission checklist.

Usage (from the project root):
    python make_zip.py

Layout produced (GUIDE section 7):
    output/level1.csv, output/level2.csv, source/..., demo/... (if present)
"""

from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ZIP_PATH = ROOT / "submission.zip"
MAX_BYTES = 15 * 1024 * 1024
EXPECTED_ROWS = {"level1.csv": 10, "level2.csv": 120}
LEVEL1_KEYS = [
    "provider", "tariff", "sanctioned_load_kw", "bill_month", "reading_date", "issue_date",
    "due_date", "previous_reading", "current_reading", "units_consumed", "charges",
    "total_charges", "taxes", "total_taxes", "current_bill", "arrears",
    "payable_within_due_date", "payable_after_due_date",
]

EXCLUDED_DIRS = {".venv", "venv", "__pycache__", "node_modules", "dist", "cache", ".git", ".idea", ".vscode", ".pytest_cache"}
EXCLUDED_FILES = {".env"}
EXCLUDED_SUFFIXES = {".pyc", ".log", ".tmp"}
REQUIRED_SOURCE = ["README.md", ".env.example", "requirements.txt", "main.py",
                   "web/package.json", "web/package-lock.json"]
# Only Gemini may be used; refuse to package leftover development backends.
FORBIDDEN_SOURCE = re.compile(r"api\.groq\.com|llm_groq_dev|openai\.com|anthropic", re.IGNORECASE)
KEY_PATTERN = re.compile(r"(AIza[0-9A-Za-z_\-]{30,}|AQ\.[0-9A-Za-z_\-]{30,}|gsk_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z]{20,})")


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def source_files() -> list[Path]:
    files = []
    for path in sorted((ROOT / "source").rglob("*")):
        rel = path.relative_to(ROOT / "source")
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDED_FILES or path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def check_csv(path: Path) -> None:
    if not path.is_file():
        fail(f"{path.relative_to(ROOT)} is missing; run the CLI first")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = EXPECTED_ROWS[path.name]
    if len(rows) != expected:
        fail(f"{path.name} has {len(rows)} rows, expected {expected}")
    column = "json" if path.name == "level1.csv" else "answer"
    empty = [r.get("bill_id", "?") for r in rows if not (r.get(column) or "").strip()]
    if empty:
        fail(f"{path.name} has empty '{column}' cells for: {', '.join(sorted(set(empty)))}")
    if column == "json":
        for row in rows:
            try:
                obj = json.loads(row["json"])
            except json.JSONDecodeError as exc:
                fail(f"level1.csv {row['bill_id']}: invalid JSON ({exc})")
            if list(obj) != LEVEL1_KEYS:
                fail(f"level1.csv {row['bill_id']}: keys differ from GUIDE 5.1")
    print(f"ok   {path.name}: {len(rows)} rows, no empty {column} cells")


def main() -> None:
    for name in EXPECTED_ROWS:
        check_csv(ROOT / "output" / name)

    files = source_files()
    rels = {f.relative_to(ROOT / "source").as_posix() for f in files}
    for required in REQUIRED_SOURCE:
        if required not in rels:
            fail(f"source/{required} is missing")

    for path in files:
        rel = path.relative_to(ROOT / "source").as_posix()
        if path.suffix not in {".py", ".ts", ".tsx", ".json", ".md", ".example", ".txt"} and not path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # README legitimately names the AI coding tools; the lockfile is third-party metadata.
        if path.name not in {"README.md", "package-lock.json"} and FORBIDDEN_SOURCE.search(text):
            fail(f"source/{rel} references a non-Gemini model provider")
        if KEY_PATTERN.search(text):
            fail(f"source/{rel} appears to contain a real API key")

    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in EXPECTED_ROWS:
            zf.write(ROOT / "output" / name, f"output/{name}")
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())
        demo = ROOT / "demo"
        if demo.is_dir():
            for path in sorted(demo.iterdir()):
                if path.is_file():
                    zf.write(path, f"demo/{path.name}")

    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
    if any(Path(n).name == ".env" for n in names):
        ZIP_PATH.unlink()
        fail("a .env file ended up in the ZIP")
    size = ZIP_PATH.stat().st_size
    if size > MAX_BYTES:
        fail(f"submission.zip is {size / 1024 / 1024:.1f} MB (limit 15 MB)")

    print(f"ok   {len(names)} files, {size / 1024 / 1024:.2f} MB, no .env included")
    print(f"Built {ZIP_PATH.relative_to(ROOT)}. Open it and check the folders before uploading.")


if __name__ == "__main__":
    main()
