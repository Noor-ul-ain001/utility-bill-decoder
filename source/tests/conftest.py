"""Shared fixtures. Every test runs offline: the LLM is replaced by a scripted fake."""

from __future__ import annotations

import copy
import csv
import re
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))

import config  # noqa: E402
import llm  # noqa: E402
import prompts  # noqa: E402

# The GUIDE section 5.7 answer for training bill KESC_0008.
KESC_0008_LEVEL1 = {
    "provider": "KE", "tariff": "A1-R", "sanctioned_load_kw": 3, "bill_month": "2026-04",
    "reading_date": "2026-04-03", "issue_date": "2026-04-07", "due_date": "2026-04-21",
    "previous_reading": 8819, "current_reading": 8970, "units_consumed": 151,
    "charges": [
        {"type": "fixed", "amount": 900}, {"type": "energy", "amount": 1054},
        {"type": "energy", "amount": 663.51}, {"type": "quarterly_adjustment", "amount": 52.91},
        {"type": "fpa", "amount": 125.27}, {"type": "surcharge", "amount": 64.93},
    ],
    "total_charges": 2860.62,
    "taxes": [
        {"type": "electricity_duty", "amount": 29.41}, {"type": "gst", "amount": 520.21},
        {"type": "municipal_tax", "amount": 20},
    ],
    "total_taxes": 569.62, "current_bill": 3430.24, "arrears": -0.53,
    "payable_within_due_date": 3430, "payable_after_due_date": 3716,
}

# A LESCO-style summary bill (combined taxes, CR credit, "NOT TO BE PAID").
LESCO_EXTENDED = {
    "provider": "LESCO", "tariff": "A-1b(03)T", "sanctioned_load_kw": "10", "bill_month": "JUL 2026",
    "reading_date": "17 JUL 26", "issue_date": "20 JUL 26", "due_date": "30 JUL 26",
    "previous_reading": "21822", "current_reading": "22859", "units_consumed": "1,037",
    "charge_lines": [
        {"label": "Total Electricity Charges", "type": "energy", "amount": "17,367.77"},
        {"label": "Subsidies", "type": "subsidy", "amount": None},
    ],
    "total_charges": "17,367.77", "tax_lines": [], "total_taxes": "3,358.23",
    "current_bill": "20726", "arrears": "-75496", "payable_within_due_date": "54770CR",
    "payable_after_due_date": "NOT TO BE PAID",
    "late_payment_amounts": [], "late_payment_surcharges": [], "printed_percentages": [],
    "tariff_slabs": [], "history": [{"month": "2025-07", "units": "781"}], "other_amounts": [],
}


@pytest.fixture
def kesc_extended() -> dict:
    return copy.deepcopy(prompts.KESC_0008_EXAMPLE)


@pytest.fixture
def lesco_extended() -> dict:
    return copy.deepcopy(LESCO_EXTENDED)


class FakeLLM:
    """Scripted stand-in for ``llm.generate_json``.

    * extraction prompts return ``extraction`` (or the next item of ``extraction_queue``),
    * batch-answer prompts return an answer for every question id in the prompt,
    * single-question prompts return ``{"answer": ...}``.
    Set ``fail = True`` to raise ``LLMError`` for every call.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.extraction: dict = copy.deepcopy(prompts.KESC_0008_EXAMPLE)
        self.extraction_queue: list[dict] = []
        self.answer_overrides: dict[str, str] = {}
        self.fail = False

    def __call__(self, prompt, *, images=None, system=None, schema=None, temperature=0.0):
        self.calls.append({"prompt": prompt, "images": images or [], "schema": schema})
        if self.fail:
            raise llm.LLMError("model unavailable (fake)")
        if "Return a JSON object mapping each question id" in prompt:
            ids = re.findall(r"^(Q\d+):", prompt.split("QUESTIONS:")[1], flags=re.MULTILINE)
            return {qid: self.answer_overrides.get(qid, f"Answer to {qid}.") for qid in ids}
        if "QUESTION:" in prompt:
            return {"answer": "Taxes are PKR 569.62, about 16.6% of the bill."}
        if self.extraction_queue:
            return self.extraction_queue.pop(0)
        return copy.deepcopy(self.extraction)

    @property
    def extraction_calls(self) -> int:
        return sum(1 for c in self.calls if c["schema"] is not None)


@pytest.fixture
def fake_llm(monkeypatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(llm, "generate_json", fake)
    monkeypatch.setattr(config, "API_KEY", "test-key")
    return fake


FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def write_templates(csv_dir: Path, bill_ids: list[str], questions: list[tuple[str, str]]) -> None:
    csv_dir.mkdir(parents=True, exist_ok=True)
    with (csv_dir / "level1.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bill_id", "json"])
        for b in bill_ids:
            w.writerow([b, ""])
    with (csv_dir / "level2.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bill_id", "question_id", "question", "answer"])
        for b in bill_ids:
            for qid, q in questions:
                w.writerow([b, qid, q, ""])


QUESTIONS = [
    ("Q1", "How much of my bill is taxes?"),
    ("Q2", "How many months in my history went above 200 units?"),
]


@pytest.fixture
def workspace(tmp_path) -> dict:
    """A project-like folder: bills/, csv/ templates and an output/ folder."""
    bills = tmp_path / "test" / "bills"
    bills.mkdir(parents=True)
    (bills / "KESC_0008.png").write_bytes(FAKE_PNG)
    (bills / "LESCO_0005.jpg").write_bytes(FAKE_PNG + b"lesco")
    csv_dir = tmp_path / "test" / "csv"
    write_templates(csv_dir, ["KESC_0008", "LESCO_0005"], QUESTIONS)
    return {"root": tmp_path, "bills": bills, "csv": csv_dir, "out": tmp_path / "output"}
