"""Consistency checks on a Level 1 object.

Checks only *report*; printed values are never changed here. A failing check is
either a misread (worth a targeted re-extraction) or a genuine quirk of the bill
(e.g. FPA billed outside the charges subtotal), so callers decide what to do.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

TOLERANCE = 1.0  # GUIDE scoring accepts numbers within +/-1


@dataclass(frozen=True)
class Check:
    check: str
    passed: bool
    detail: str

    def as_dict(self) -> dict:
        return asdict(self)


def _close(a: float, b: float, tol: float = TOLERANCE) -> bool:
    return abs(a - b) <= tol + 1e-9


def _fmt(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def run_checks(level1: dict) -> list[Check]:
    """Run every check whose inputs are present. Missing inputs mean the check is skipped."""
    checks: list[Check] = []
    prev, curr, units = level1.get("previous_reading"), level1.get("current_reading"), level1.get("units_consumed")
    charges, taxes = level1.get("charges") or [], level1.get("taxes") or []
    total_charges, total_taxes = level1.get("total_charges"), level1.get("total_taxes")
    current_bill, arrears = level1.get("current_bill"), level1.get("arrears")
    within, after = level1.get("payable_within_due_date"), level1.get("payable_after_due_date")

    if None not in (prev, curr, units):
        diff = curr - prev
        checks.append(Check(
            "Readings match units",
            _close(diff, units),
            f"current {_fmt(curr)} - previous {_fmt(prev)} = {_fmt(diff)}; units printed {_fmt(units)}",
        ))

    # LESCO / IESCO print "Total FPA" beside the charges block but outside the net-charges
    # subtotal and the current bill (Grand Total = Current Bill + FPA + arrears), so each
    # check also accepts the reading with FPA kept outside.
    fpa = sum(c["amount"] for c in charges if c["type"] == "fpa")

    if charges and total_charges is not None:
        total = sum(c["amount"] for c in charges)
        passed = _close(total, total_charges) or (fpa != 0 and _close(total - fpa, total_charges))
        note = f" ({_fmt(total - fpa)} without FPA)" if fpa else ""
        checks.append(Check(
            "Charge lines add up",
            passed,
            f"sum of {len(charges)} lines = {_fmt(total)}{note}; printed total {_fmt(total_charges)}",
        ))

    if taxes and total_taxes is not None:
        total = sum(t["amount"] for t in taxes)
        checks.append(Check(
            "Tax lines add up",
            _close(total, total_taxes),
            f"sum of {len(taxes)} lines = {_fmt(total)}; printed total {_fmt(total_taxes)}",
        ))

    charges_value = total_charges if total_charges is not None else (sum(c["amount"] for c in charges) if charges else None)
    taxes_value = total_taxes if total_taxes is not None else (sum(t["amount"] for t in taxes) if taxes else None)
    if None not in (charges_value, taxes_value, current_bill):
        total = charges_value + taxes_value
        checks.append(Check(
            "Charges + taxes = current bill",
            _close(total, current_bill),
            f"{_fmt(charges_value)} + {_fmt(taxes_value)} = {_fmt(total)}; current bill {_fmt(current_bill)}",
        ))

    if None not in (current_bill, within):
        expected = current_bill + (arrears or 0)
        passed = _close(round(expected), within) or (fpa != 0 and _close(round(expected + fpa), within))
        note = f" (+ FPA {_fmt(fpa)} = {_fmt(expected + fpa)})" if fpa else ""
        checks.append(Check(
            "Current bill + arrears = payable",
            passed,
            f"{_fmt(current_bill)} + arrears {_fmt(arrears or 0)} = {_fmt(expected)}{note}; payable {_fmt(within)}",
        ))

    if None not in (within, after):
        checks.append(Check(
            "Late amount >= on-time amount",
            after >= within - TOLERANCE,
            f"after due date {_fmt(after)}; within due date {_fmt(within)}",
        ))

    return checks


def failed(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.passed]
