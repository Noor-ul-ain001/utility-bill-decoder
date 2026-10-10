"""Level 2: plain-English answers grounded in one bill.

Batch mode answers all questions for a bill in ONE model call (rate-limit friendly);
single mode answers one question for the UI. Both send the same context: the bill
data, the precomputed statistics and the bill image.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import calculator
import config
import llm
import normalize
import prompts

log = logging.getLogger(__name__)


@dataclass
class BillContext:
    """Everything the answer model sees about one bill."""

    bill_data: dict
    level1: dict
    history: list[dict]
    charge_lines: list[dict]
    tax_lines: list[dict]
    printed_percentages: list[dict]
    late_surcharges: list[dict]
    net_metering_evidence: list[dict]
    fpa_note: str | None
    image: Path | bytes | None = None
    mime_type: str | None = None

    def stats(self, questions: list[str]) -> dict:
        return calculator.compute_stats(
            self.level1, self.history, self.charge_lines, self.tax_lines,
            self.printed_percentages, self.late_surcharges, questions, self.net_metering_evidence,
            self.fpa_note,
        )


def build_context(level1: dict, extended: dict, history: list[dict],
                  image: Path | bytes | None = None, mime_type: str | None = None) -> BillContext:
    """Assemble the answer context from a finished extraction."""
    charge_lines = normalize.normalize_lines(extended.get("charge_lines"), config.CHARGE_TYPES, "other")
    tax_lines = normalize.normalize_lines(extended.get("tax_lines"), config.TAX_TYPES, "other_tax")
    percentages = [
        {"label": p.get("label"), "percent": normalize.parse_percent(p.get("percent"))}
        for p in extended.get("printed_percentages") or []
        if normalize.parse_percent(p.get("percent")) is not None
    ]

    def amounts(key: str) -> list[dict]:
        return [
            {"label": item.get("label"), "amount": normalize.parse_amount(item.get("amount"))}
            for item in extended.get(key) or []
            if normalize.parse_amount(item.get("amount")) is not None
        ]

    late_surcharges = amounts("late_payment_surcharges")
    # Labelled lines and history are already in the computed stats, so they are not repeated here.
    bill_data = {
        "level1": level1,
        "late_payment_amounts": amounts("late_payment_amounts"),
        "late_payment_surcharges": late_surcharges,
        "printed_percentages": percentages,
        "tariff_slabs": extended.get("tariff_slabs") or [],
        "other_printed_amounts": amounts("other_amounts"),
    }
    evidence = [{"label": e.get("label"), "value": e.get("amount")} for e in extended.get("net_metering_evidence") or []]
    return BillContext(bill_data, level1, history, charge_lines, tax_lines, percentages,
                       late_surcharges, evidence, extended.get("fpa_note"), image, mime_type)


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _images(ctx: BillContext) -> list:
    """The bill image lets the model double-check context; it can be disabled to save tokens."""
    if ctx.image is None or not config.ANSWER_WITH_IMAGE:
        return []
    return [llm.image_part(ctx.image, ctx.mime_type)]


def _clean(answer: object) -> str:
    return " ".join(str(answer).split()) if answer is not None else ""


def answer_batch(ctx: BillContext, questions: list[tuple[str, str]]) -> dict[str, str]:
    """Answer all ``(question_id, question)`` pairs for one bill.

    One call for every question; if any answer is missing or empty, the bill is
    retried once for the missing ones. Never returns an empty answer.
    """
    answers: dict[str, str] = {}
    pending = list(questions)
    stats = _dump(ctx.stats([q for _, q in questions]))

    for attempt in range(2):
        if not pending:
            break
        prompt = prompts.BATCH_ANSWER_PROMPT.format(
            rules=prompts.ANSWER_RULES,
            bill=_dump(ctx.bill_data),
            stats=stats,
            questions="\n".join(f"{qid}: {text}" for qid, text in pending),
        )
        try:
            result = llm.generate_json(prompt, images=_images(ctx), system=prompts.ANSWER_SYSTEM, temperature=0.2)
        except llm.LLMError as exc:
            log.warning("Answer call failed (attempt %d): %s", attempt + 1, exc)
            continue
        if isinstance(result, dict):
            for qid, _ in pending:
                text = _clean(result.get(qid))
                if text:
                    answers[qid] = text
        pending = [(qid, q) for qid, q in pending if qid not in answers]

    for qid, _ in pending:
        log.warning("No answer for %s; using fallback text", qid)
        answers[qid] = config.FALLBACK_ANSWER
    return answers


def answer_single(ctx: BillContext, question: str) -> str:
    """Answer one free-form question (used by the UI). Raises ``llm.LLMError`` on failure."""
    prompt = prompts.SINGLE_ANSWER_PROMPT.format(
        rules=prompts.ANSWER_RULES,
        bill=_dump(ctx.bill_data),
        stats=_dump(ctx.stats([question])),
        question=question,
    )
    result = llm.generate_json(prompt, images=_images(ctx), system=prompts.ANSWER_SYSTEM, temperature=0.2)
    text = _clean(result.get("answer") if isinstance(result, dict) else result)
    return text or config.FALLBACK_ANSWER
