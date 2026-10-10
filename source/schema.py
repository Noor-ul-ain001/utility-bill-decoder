"""Data models.

* ``ExtendedBill`` - what the model is asked to return. Values are the *printed
  text* (e.g. ``"54770CR"``, ``"21st Apr 2026"``); ``normalize.py`` converts them
  deterministically, so the LLM only reads and never does conversions.
* ``Level1`` - the exact GUIDE 5.1 output (18 keys, fixed order).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChargeType = Literal[
    "energy", "fixed", "fpa", "quarterly_adjustment", "surcharge", "meter_rent", "subsidy", "other"
]
TaxType = Literal["gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"]

# Exact key order required by GUIDE section 5.1.
LEVEL1_KEYS: tuple[str, ...] = (
    "provider", "tariff", "sanctioned_load_kw", "bill_month", "reading_date", "issue_date",
    "due_date", "previous_reading", "current_reading", "units_consumed", "charges",
    "total_charges", "taxes", "total_taxes", "current_bill", "arrears",
    "payable_within_due_date", "payable_after_due_date",
)


# --------------------------------------------------------------------------- #
# Extended extraction (model output)                                           #
# --------------------------------------------------------------------------- #
class PrintedLine(BaseModel):
    """One charge or tax line: printed label, classified type, printed amount text."""

    label: str = Field(description="Label text as printed (English part only).")
    type: str = Field(description="Classified type from the allowed list.")
    amount: str | None = Field(description="Amount exactly as printed, e.g. '1,054.00' or '38209CR'.")


class LabeledAmount(BaseModel):
    label: str
    amount: str | None


class PrintedPercent(BaseModel):
    label: str = Field(description="What the percentage refers to, e.g. 'energy charges' or 'taxes'.")
    percent: str | None


class TariffSlab(BaseModel):
    label: str
    units: str | None = None
    rate: str | None = None
    amount: str | None = None


class HistoryEntry(BaseModel):
    month: str = Field(description="Month as YYYY-MM.")
    units: str | None = None
    bill_amount: str | None = None
    payment: str | None = None


class ExtendedBill(BaseModel):
    """Everything read from one bill. Strings hold printed text; null when not printed."""

    provider: str | None
    tariff: str | None
    sanctioned_load_kw: str | None
    bill_month: str | None
    reading_date: str | None
    issue_date: str | None
    due_date: str | None
    previous_reading: str | None
    current_reading: str | None
    units_consumed: str | None
    charge_lines: list[PrintedLine]
    total_charges: str | None
    tax_lines: list[PrintedLine]
    total_taxes: str | None
    current_bill: str | None
    arrears: str | None
    payable_within_due_date: str | None
    payable_after_due_date: str | None
    late_payment_amounts: list[LabeledAmount] = Field(
        description="Every printed 'payable after due date' amount (all tiers)."
    )
    late_payment_surcharges: list[LabeledAmount] = Field(
        description="Printed late payment surcharge (LPS) amounts."
    )
    printed_percentages: list[PrintedPercent] = Field(
        description="Any printed percentage split, e.g. energy charges 83.39% / taxes 16.61%."
    )
    tariff_slabs: list[TariffSlab] = Field(description="Units/rate/amount rows if printed.")
    history: list[HistoryEntry] = Field(
        description="Consumption / billing history rows, including the current month if shown."
    )
    other_amounts: list[LabeledAmount] = Field(
        description="Other printed money lines not captured above (e.g. FPA notes, deferred amount, installments)."
    )
    fpa_note: str | None = Field(
        default=None,
        description="Printed note naming the month (and rate) of the fuel price adjustment, in English.",
    )
    net_metering_evidence: list[LabeledAmount] = Field(
        description="Printed signs of a net-metered (solar) connection, e.g. 'NET METERING CONNECTION', "
                    "'Net Metering Benefit', import/export meter rows; [] if none."
    )


# --------------------------------------------------------------------------- #
# Level 1 output                                                              #
# --------------------------------------------------------------------------- #
Number = int | float


class Charge(BaseModel):
    type: ChargeType
    amount: Number


class Tax(BaseModel):
    type: TaxType
    amount: Number


class Level1(BaseModel):
    provider: Literal["KE", "LESCO", "IESCO"] | None = None
    tariff: str | None = None
    sanctioned_load_kw: Number | None = None
    bill_month: str | None = None
    reading_date: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    previous_reading: Number | None = None
    current_reading: Number | None = None
    units_consumed: Number | None = None
    charges: list[Charge] = Field(default_factory=list)
    total_charges: Number | None = None
    taxes: list[Tax] = Field(default_factory=list)
    total_taxes: Number | None = None
    current_bill: Number | None = None
    arrears: Number | None = None
    payable_within_due_date: Number | None = None
    payable_after_due_date: Number | None = None

    def to_ordered_dict(self) -> dict:
        """Dump with every key present, in GUIDE 5.1 order."""
        data = self.model_dump()
        return {key: data[key] for key in LEVEL1_KEYS}


def empty_level1() -> dict:
    """All-null Level 1 object used when a bill fails completely."""
    return Level1().to_ordered_dict()
