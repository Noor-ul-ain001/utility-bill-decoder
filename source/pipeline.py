"""Orchestration shared by the CLI (main.py) and the API (api.py).

* ``process_bill`` - read one bill (with on-disk cache) and never raise.
* ``run_batch``    - fill level1.csv / level2.csv from the templates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import answerer
import config
import csv_io
import extractor
import llm
from schema import empty_level1

log = logging.getLogger(__name__)

CACHE_VERSION = 1
Progress = Callable[[str], None]


@dataclass
class BillResult:
    """Outcome of reading one bill; ``error`` is set when extraction failed."""

    bill_id: str
    image_path: Path | None
    extraction: extractor.Extraction | None = None
    error: str | None = None
    from_cache: bool = False

    @property
    def level1(self) -> dict:
        return self.extraction.level1 if self.extraction else empty_level1()

    @property
    def warnings(self) -> list:
        return self.extraction.warnings if self.extraction else []

    def context(self) -> answerer.BillContext | None:
        if not self.extraction:
            return None
        e = self.extraction
        return answerer.build_context(e.level1, e.extended, e.history, self.image_path)


@dataclass
class BatchSummary:
    processed: int = 0
    warnings: int = 0
    failures: int = 0
    failed_bills: list[str] = field(default_factory=list)
    bills: list[dict] = field(default_factory=list)
    level1_path: Path | None = None
    level2_path: Path | None = None

    def as_dict(self) -> dict:
        return {
            "processed": self.processed,
            "warnings": self.warnings,
            "failures": self.failures,
            "failed_bills": self.failed_bills,
            "bills": self.bills,
        }


# --------------------------------------------------------------------------- #
# Files and cache                                                              #
# --------------------------------------------------------------------------- #
def find_bill_image(bills_dir: Path, bill_id: str) -> Path | None:
    """Locate ``bill_id`` with any supported extension (case-insensitive)."""
    for ext in config.IMAGE_EXTENSIONS:
        for candidate in (bills_dir / f"{bill_id}{ext}", bills_dir / f"{bill_id}{ext.upper()}"):
            if candidate.is_file():
                return candidate
    return None


def list_bill_images(bills_dir: Path) -> list[Path]:
    if not bills_dir.is_dir():
        return []
    return sorted(p for p in bills_dir.iterdir() if p.suffix.lower() in config.IMAGE_EXTENSIONS)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cache_identity() -> dict:
    return {"version": CACHE_VERSION, "model": f"{config.MODEL_PROVIDER}:{config.MODEL_NAME}"}


def _load_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cached_extraction(cache_file: Path, image_hash: str, bill_id: str) -> extractor.Extraction | None:
    """Return the cached extraction if it was made from the same image with the same model."""
    data = _load_json(cache_file)
    if not data or data.get("identity") != _cache_identity() or data.get("image_sha256") != image_hash:
        return None
    return extractor.from_extended(data["extended"], bill_id, data.get("attempts", 1))


def save_extraction(cache_file: Path, image_hash: str, extraction: extractor.Extraction) -> None:
    _save_json(cache_file, {
        "identity": _cache_identity(),
        "image_sha256": image_hash,
        "attempts": extraction.attempts,
        "extended": extraction.extended,
        "level1": extraction.level1,
        "validation": [c.as_dict() for c in extraction.checks],
    })


# --------------------------------------------------------------------------- #
# Single bill                                                                  #
# --------------------------------------------------------------------------- #
def process_bill(image_path: Path | None, bill_id: str, cache_dir: Path | None, use_cache: bool = True) -> BillResult:
    """Extract one bill. Errors are captured in the result instead of raised."""
    result = BillResult(bill_id=bill_id, image_path=image_path)
    if image_path is None:
        result.error = "bill image not found"
        return result
    try:
        data = image_path.read_bytes()
        image_hash = sha256(data)
        cache_file = cache_dir / f"{bill_id}.json" if cache_dir else None
        if cache_file and use_cache:
            cached = load_cached_extraction(cache_file, image_hash, bill_id)
            if cached:
                result.extraction, result.from_cache = cached, True
                return result
        result.extraction = extractor.extract_bill(image_path, bill_id)
        if cache_file:
            save_extraction(cache_file, image_hash, result.extraction)
    except (llm.LLMError, OSError, ValueError) as exc:
        result.error = str(exc)
        log.error("%s: extraction failed: %s", bill_id, exc)
    return result


def answers_for_bill(result: BillResult, questions: list[tuple[str, str]], cache_dir: Path | None,
                     use_cache: bool = True) -> dict[str, str]:
    """Level 2 answers for one bill, cached by question set so reruns cost nothing."""
    ctx = result.context()
    if ctx is None:
        return {qid: config.FALLBACK_ANSWER for qid, _ in questions}

    key = sha256(json.dumps([questions, result.level1, _cache_identity()], sort_keys=True).encode())
    cache_file = cache_dir / f"{result.bill_id}.answers.json" if cache_dir else None
    if cache_file and use_cache:
        cached = _load_json(cache_file)
        if cached and cached.get("key") == key:
            return cached["answers"]

    answers = answerer.answer_batch(ctx, questions)
    if cache_file and all(a != config.FALLBACK_ANSWER for a in answers.values()):
        _save_json(cache_file, {"key": key, "answers": answers})
    return answers


# --------------------------------------------------------------------------- #
# Batch                                                                        #
# --------------------------------------------------------------------------- #
def run_batch(
    bills_dir: Path,
    csv_dir: Path,
    out_dir: Path,
    *,
    only: set[str] | None = None,
    use_cache: bool = True,
    level: str = "all",
    progress: Progress = print,
) -> BatchSummary:
    """Fill the CSV templates in ``csv_dir`` and write them to ``out_dir``.

    ``only`` limits model calls to those bill ids; other rows keep any answers
    already present in a previous output file (or get the fallback).
    """
    if not bills_dir.is_dir():
        raise FileNotFoundError(f"Bills folder not found: {bills_dir}")
    cache_dir = out_dir / "cache"
    summary = BatchSummary()

    l1_fields, l1_rows = csv_io.read_template(csv_dir / "level1.csv")
    l2_fields, l2_rows = (csv_io.read_template(csv_dir / "level2.csv") if level in ("2", "all") else ([], []))

    # Bill ids in template order (level1 first, then any extra ids found only in level2).
    bill_ids: list[str] = []
    for row in l1_rows + l2_rows:
        if row["bill_id"] not in bill_ids:
            bill_ids.append(row["bill_id"])
    targets = [b for b in bill_ids if not only or b in only]

    results: dict[str, BillResult] = {}
    for index, bill_id in enumerate(targets, start=1):
        image = find_bill_image(bills_dir, bill_id)
        progress(f"[{index}/{len(targets)}] {bill_id}: reading bill…")
        res = process_bill(image, bill_id, cache_dir, use_cache)
        results[bill_id] = res
        summary.processed += 1
        summary.bills.append({
            "bill_id": bill_id,
            "ok": res.error is None,
            "error": res.error,
            "from_cache": res.from_cache,
            "checks_passed": len(res.extraction.checks) - len(res.warnings) if res.extraction else 0,
            "checks_total": len(res.extraction.checks) if res.extraction else 0,
            "provider": res.level1["provider"],
            "payable_within_due_date": res.level1["payable_within_due_date"],
        })
        if res.error:
            summary.failures += 1
            summary.failed_bills.append(bill_id)
            progress(f"    FAILED: {res.error} (writing all-null Level 1 JSON)")
            continue
        source = "cache" if res.from_cache else f"model, {res.extraction.attempts} read(s)"
        progress(f"    ok ({source}); {len(res.extraction.checks) - len(res.warnings)}/{len(res.extraction.checks)} checks passed")
        for check in res.warnings:
            summary.warnings += 1
            progress(f"    warning: {check.check} - {check.detail}")

    # ---- Level 1 ----
    previous_l1 = _previous_output(out_dir / "level1.csv")
    for row in l1_rows:
        bill_id = row["bill_id"]
        if bill_id in results:
            row["json"] = csv_io.level1_cell(results[bill_id].level1)
        else:
            row["json"] = previous_l1.get((bill_id,), {}).get("json") or csv_io.level1_cell(empty_level1())
    if level in ("1", "all"):
        summary.level1_path = out_dir / "level1.csv"
        csv_io.write_rows(summary.level1_path, l1_fields, l1_rows)
        progress(f"Wrote {summary.level1_path} ({len(l1_rows)} rows)")

    # ---- Level 2 ----
    if level in ("2", "all"):
        previous_l2 = _previous_output(out_dir / "level2.csv", ("bill_id", "question_id"))
        by_bill: dict[str, list[tuple[str, str]]] = {}
        for row in l2_rows:
            by_bill.setdefault(row["bill_id"], []).append((row["question_id"], row["question"]))
        answers: dict[str, dict[str, str]] = {}
        for bill_id, questions in by_bill.items():
            if bill_id not in results:
                continue
            progress(f"{bill_id}: answering {len(questions)} questions…")
            answers[bill_id] = answers_for_bill(results[bill_id], questions, cache_dir, use_cache)
        for row in l2_rows:
            key = (row["bill_id"], row["question_id"])
            answer = answers.get(row["bill_id"], {}).get(row["question_id"])
            row["answer"] = answer or previous_l2.get(key, {}).get("answer") or config.FALLBACK_ANSWER
        summary.level2_path = out_dir / "level2.csv"
        csv_io.write_rows(summary.level2_path, l2_fields, l2_rows)
        progress(f"Wrote {summary.level2_path} ({len(l2_rows)} rows)")

    return summary


def _previous_output(path: Path, key_fields: tuple[str, ...] = ("bill_id",)) -> dict[tuple, dict]:
    """Rows of an earlier output file, so ``--only`` runs keep other bills' results."""
    if not path.is_file():
        return {}
    try:
        _, rows = csv_io.read_template(path)
    except (OSError, ValueError):
        return {}
    return {tuple(row.get(k, "") for k in key_fields): row for row in rows}
