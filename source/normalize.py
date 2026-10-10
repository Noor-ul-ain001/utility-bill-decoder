"""Deterministic conversion of printed text into Level 1 values (GUIDE 5.2-5.4).

The model returns what is printed; this module turns it into typed values:
* amounts: strip "Rs."/commas, ``CR`` suffix -> negative, whole numbers -> int,
* dates: many printed formats -> ``YYYY-MM-DD`` / ``YYYY-MM``,
* enums: provider and charge/tax types restricted to the allowed values.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import config
from schema import LEVEL1_KEYS, Level1

Number = int | float

_MONTHS = {
    m: i
    for i, names in enumerate(
        [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
         ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
         ("oct", "october"), ("nov", "november"), ("dec", "december")],
        start=1,
    )
    for m in names
}
_NULL_WORDS = {"", "-", "--", "—", "n/a", "na", "nil", "null", "none", "not to be paid", "unreadable"}


# --------------------------------------------------------------------------- #
# Numbers                                                                      #
# --------------------------------------------------------------------------- #
def clean_number(value: Number) -> Number:
    """Return an int for whole numbers, otherwise a float rounded to 2 decimals."""
    as_float = round(float(value), 2)
    return int(as_float) if as_float.is_integer() else as_float


def parse_amount(value: Any) -> Number | None:
    """Parse a printed amount. ``"Rs. 19,964"`` -> 19964, ``"38209CR"`` -> -38209.

    Returns None for blanks, dashes, words such as "NOT TO BE PAID", or anything unparseable.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return clean_number(value)
    text = str(value).strip().lower()
    if text in _NULL_WORDS:
        return None

    negative = False
    if re.search(r"\bcr\b|cr$|\(cr\)", text):  # credit marker, e.g. "54770CR" or "54,770 Cr"
        negative = True
        text = re.sub(r"\(?cr\)?", "", text)
    if text.startswith("(") and text.endswith(")"):  # accounting negative "(123)"
        negative = True
        text = text[1:-1]

    text = re.sub(r"\s*/\s*\d+$", "", text)  # trailing installment marks, e.g. "39411 / 2"
    text = re.sub(r"(rs\.?|pkr|kwh|kw|units?)", "", text)
    text = text.replace(",", "").replace(" ", "")
    match = re.fullmatch(r"([+-]?)(\d+(?:\.\d+)?|\.\d+)-?", text)
    if not match:
        return None
    number = float(match.group(2))
    if match.group(1) == "-" or text.endswith("-"):  # some bills print trailing minus
        negative = not negative if number else negative
    return clean_number(-number if negative else number)


# --------------------------------------------------------------------------- #
# Dates                                                                        #
# --------------------------------------------------------------------------- #
def _year(text: str) -> int | None:
    year = int(text)
    if year < 100:
        year += 2000
    return year if 1990 <= year <= 2100 else None


def _month(text: str) -> int | None:
    text = text.lower().strip(".")
    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 12 else None
    return _MONTHS.get(text) or _MONTHS.get(text[:3])


def _safe_date(y: int | None, m: int | None, d: int) -> str | None:
    if y is None or m is None:
        return None
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(value: Any) -> str | None:
    """Parse a printed date into ``YYYY-MM-DD``.

    Handles ``2026-04-21``, ``21st Apr 2026``, ``07-Apr-2026``, ``03-Apr-26``, ``17 JUL 26``,
    ``21/04/2026`` (day first, as printed in Pakistan) and ``Apr 21, 2026``.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NULL_WORDS:
        return None
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)

    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text):
        return _safe_date(_year(m[1]), _month(m[2]), int(m[3]))
    if m := re.fullmatch(r"(\d{1,2})[\s\-/.,]+([A-Za-z]{3,9})\.?[\s\-/.,]+(\d{2,4})", text):
        return _safe_date(_year(m[3]), _month(m[2]), int(m[1]))
    if m := re.fullmatch(r"([A-Za-z]{3,9})\.?[\s\-/.]+(\d{1,2}),?[\s\-/.]+(\d{2,4})", text):
        return _safe_date(_year(m[3]), _month(m[1]), int(m[2]))
    if m := re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", text):
        return _safe_date(_year(m[3]), _month(m[2]), int(m[1]))
    return None


def parse_month(value: Any) -> str | None:
    """Parse a billing month into ``YYYY-MM``: ``Apr-26``, ``JUL 2026``, ``SEP 26``, ``03/26``, ``Sep25``."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NULL_WORDS:
        return None
    if full := parse_date(text):
        return full[:7]

    patterns = (
        (r"(\d{4})[-/.](\d{1,2})", 1, 2),               # 2026-04
        (r"([A-Za-z]{3,9})\.?[\s\-/.,']*(\d{2,4})", 2, 1),  # Apr-26, JUL 2026, Sep25
        (r"(\d{1,2})[-/.](\d{2,4})", 2, 1),             # 03/26
        (r"(\d{2,4})[\s\-/.]+([A-Za-z]{3,9})", 1, 2),   # 26 Apr
    )
    for pattern, y_idx, m_idx in patterns:
        if m := re.fullmatch(pattern, text):
            year, month = _year(m[y_idx]), _month(m[m_idx])
            if year and month:
                return f"{year:04d}-{month:02d}"
    return None


# --------------------------------------------------------------------------- #
# Enums                                                                        #
# --------------------------------------------------------------------------- #
_PROVIDER_ALIASES = {
    "KE": "KE", "KESC": "KE", "K-ELECTRIC": "KE", "KELECTRIC": "KE", "K ELECTRIC": "KE",
    "LESCO": "LESCO", "LAHORE ELECTRIC SUPPLY COMPANY": "LESCO",
    "IESCO": "IESCO", "ISLAMABAD ELECTRIC SUPPLY COMPANY": "IESCO",
}


def provider_from_bill_id(bill_id: str | None) -> str | None:
    """``KESC_0008`` -> ``KE``; file names are a reliable provider hint."""
    if not bill_id:
        return None
    return _PROVIDER_ALIASES.get(bill_id.split("_")[0].upper())


def normalize_provider(value: Any, bill_id: str | None = None) -> str | None:
    if value:
        key = str(value).strip().upper()
        if key in _PROVIDER_ALIASES:
            return _PROVIDER_ALIASES[key]
        for alias, provider in _PROVIDER_ALIASES.items():
            if alias in key:
                return provider
    return provider_from_bill_id(bill_id)


def normalize_type(value: Any, allowed: tuple[str, ...], fallback: str) -> str:
    text = re.sub(r"[\s\-]+", "_", str(value or "").strip().lower())
    return text if text in allowed else fallback


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return None if text.lower() in _NULL_WORDS else text


# --------------------------------------------------------------------------- #
# Extended JSON -> Level 1                                                     #
# --------------------------------------------------------------------------- #
# Rows such as "UNITS CONSUMED 89" sit inside some charge tables but are unit counts, not money.
_NON_MONEY_LABEL = re.compile(r"^\s*(units?(\s+consumed)?|mdi|multiplying factor|mf)\s*$", re.IGNORECASE)


def normalize_lines(lines: list[dict] | None, allowed: tuple[str, ...], fallback: str) -> list[dict]:
    """Typed lines with label kept; skips blank, zero and non-money lines (GUIDE 5.3)."""
    result: list[dict] = []
    for line in lines or []:
        if _NON_MONEY_LABEL.match(str(line.get("label") or "")):
            continue
        amount = parse_amount(line.get("amount"))
        if amount is None or amount == 0:
            continue
        line_type = normalize_type(line.get("type"), allowed, fallback)
        if line_type == "subsidy" and amount > 0:  # GUIDE 5.2: subsidies are deductions
            amount = -amount
        result.append({"label": _clean_text(line.get("label")) or "", "type": line_type, "amount": amount})
    return result


def payable_after(extended: dict) -> Number | None:
    """Highest printed after-due-date amount (GUIDE 5.3)."""
    candidates = [parse_amount(extended.get("payable_after_due_date"))]
    candidates += [parse_amount(item.get("amount")) for item in extended.get("late_payment_amounts") or []]
    values = [v for v in candidates if v is not None]
    return max(values) if values else None


def to_level1(extended: dict, bill_id: str | None = None) -> dict:
    """Convert the extended extraction into the exact Level 1 object (18 keys, GUIDE order)."""
    charges = normalize_lines(extended.get("charge_lines"), config.CHARGE_TYPES, "other")
    taxes = normalize_lines(extended.get("tax_lines"), config.TAX_TYPES, "other_tax")

    level1 = Level1(
        provider=normalize_provider(extended.get("provider"), bill_id),
        tariff=_clean_text(extended.get("tariff")),
        sanctioned_load_kw=parse_amount(extended.get("sanctioned_load_kw")),
        bill_month=parse_month(extended.get("bill_month")),
        reading_date=parse_date(extended.get("reading_date")),
        issue_date=parse_date(extended.get("issue_date")),
        due_date=parse_date(extended.get("due_date")),
        previous_reading=parse_amount(extended.get("previous_reading")),
        current_reading=parse_amount(extended.get("current_reading")),
        units_consumed=parse_amount(extended.get("units_consumed")),
        charges=[{"type": c["type"], "amount": c["amount"]} for c in charges],
        total_charges=parse_amount(extended.get("total_charges")),
        taxes=[{"type": t["type"], "amount": t["amount"]} for t in taxes],
        total_taxes=parse_amount(extended.get("total_taxes")),
        current_bill=parse_amount(extended.get("current_bill")),
        arrears=parse_amount(extended.get("arrears")),
        payable_within_due_date=parse_amount(extended.get("payable_within_due_date")),
        payable_after_due_date=payable_after(extended),
    )
    data = level1.to_ordered_dict()
    assert tuple(data) == LEVEL1_KEYS
    return data


def normalize_history(extended: dict) -> list[dict]:
    """History rows as ``{month: YYYY-MM, units, bill_amount, payment}``, sorted, de-duplicated."""
    rows: dict[str, dict] = {}
    for item in extended.get("history") or []:
        month = parse_month(item.get("month"))
        if not month:
            continue
        rows[month] = {
            "month": month,
            "units": parse_amount(item.get("units")),
            "bill_amount": parse_amount(item.get("bill_amount")),
            "payment": parse_amount(item.get("payment")),
        }
    return [rows[m] for m in sorted(rows)]


def parse_percent(value: Any) -> Number | None:
    if value is None:
        return None
    return parse_amount(str(value).replace("%", ""))
