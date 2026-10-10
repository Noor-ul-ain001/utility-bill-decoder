"""Bill image -> extended JSON -> normalized Level 1 JSON.

Flow:
1. One model call transcribes the bill into ``ExtendedBill`` (printed strings).
2. ``normalize`` converts it to Level 1; ``validate`` runs consistency checks.
3. If two or more checks fail, the model re-reads the bill once with the failed
   checks listed; the reading that passes more checks is kept.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import llm
import normalize
import prompts
import validate
from schema import ExtendedBill

log = logging.getLogger(__name__)

REEXTRACT_THRESHOLD = 2  # re-read when this many checks fail

_LIST_KEYS = {
    name for name, f in ExtendedBill.model_fields.items() if str(f.annotation).startswith("list")
}
_SCALAR_KEYS = set(ExtendedBill.model_fields) - _LIST_KEYS
# Long digit runs in free text could be account / reference numbers; never keep them.
_ID_PATTERN = re.compile(r"\d[\d\s\-]{9,}\d")


@dataclass
class Extraction:
    """Result of reading one bill."""

    extended: dict
    level1: dict
    checks: list[validate.Check]
    history: list[dict] = field(default_factory=list)
    attempts: int = 1

    @property
    def warnings(self) -> list[validate.Check]:
        return validate.failed(self.checks)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    text = str(value).strip()
    return text or None


def _scrub(text: str | None) -> str | None:
    return _ID_PATTERN.sub("[removed]", text) if text else text


def sanitize_extended(raw: Any) -> dict:
    """Coerce model output into the ExtendedBill shape.

    Unknown keys are dropped (so nothing unexpected such as identifiers leaks through),
    missing keys become null / [], numbers become strings so ``normalize`` handles
    everything uniformly.
    """
    if not isinstance(raw, dict):
        raise llm.LLMError("Model did not return a JSON object for the bill.")
    clean: dict[str, Any] = {}
    for key in _SCALAR_KEYS:
        clean[key] = _as_text(raw.get(key))
    for key in _LIST_KEYS:
        items = raw.get(key) or []
        rows = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            row = {k: _as_text(v) for k, v in item.items()}
            if "label" in row:
                row["label"] = _scrub(row["label"]) or ""
            rows.append(row)
        clean[key] = rows
    return {key: clean[key] for key in ExtendedBill.model_fields}


# The targeted re-read uses a little randomness so it can escape a repeated misreading.
REREAD_TEMPERATURE = 0.3


def _read(image: llm.types.Part, prompt: str, temperature: float = 0.0) -> dict:
    raw = llm.generate_json(
        prompt, images=[image], system=prompts.EXTRACTION_SYSTEM, schema=ExtendedBill,
        temperature=temperature,
    )
    return sanitize_extended(raw)


def _build(extended: dict, bill_id: str | None, attempts: int) -> Extraction:
    level1 = normalize.to_level1(extended, bill_id)
    return Extraction(
        extended=extended,
        level1=level1,
        checks=validate.run_checks(level1),
        history=normalize.normalize_history(extended),
        attempts=attempts,
    )


def from_extended(extended: dict, bill_id: str | None = None, attempts: int = 1) -> Extraction:
    """Rebuild an Extraction from a cached extended JSON (no model call)."""
    return _build(sanitize_extended(extended), bill_id, attempts)


def extract_bill(image: Path | bytes, bill_id: str | None = None, mime_type: str | None = None) -> Extraction:
    """Read one bill image. Raises ``llm.LLMError`` if the model fails."""
    part = llm.image_part(image, mime_type)
    hint = normalize.provider_from_bill_id(bill_id)

    first = _build(_read(part, prompts.extraction_prompt(hint)), bill_id, attempts=1)
    failures = first.warnings
    if len(failures) < REEXTRACT_THRESHOLD:
        return first

    log.info("%s: %d checks failed, re-reading the bill", bill_id or "bill", len(failures))
    try:
        retry_prompt = prompts.reextract_prompt(
            [f"{c.check}: {c.detail}" for c in failures], first.extended
        )
        second = _build(_read(part, retry_prompt, REREAD_TEMPERATURE), bill_id, attempts=2)
    except llm.LLMError as exc:
        log.warning("Re-extraction failed (%s); keeping the first reading", exc)
        return first

    # Keep whichever reading is more self-consistent; ties keep the first reading.
    best = second if len(second.warnings) < len(failures) else first
    best.attempts = 2
    return best
