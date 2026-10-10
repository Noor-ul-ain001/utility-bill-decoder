"""Deterministic statistics for Level 2 answers and the UI's usage insights.

The LLM never does arithmetic: every share, average, difference, count and
estimate it quotes comes from here. Helpers are deliberately general because the
exact test questions are only known at run time; numbers mentioned in the
questions (e.g. "above 300 units") become extra thresholds automatically.
"""

from __future__ import annotations

import re
from datetime import date
from statistics import mean
from typing import Any

Number = int | float
DEFAULT_THRESHOLDS = (100, 200, 300)
_MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"]


def r2(value: float | None) -> float | None:
    """Round to 2 decimals (None-safe), dropping a trailing .0 for whole numbers."""
    if value is None:
        return None
    rounded = round(float(value), 2)
    return int(rounded) if rounded.is_integer() else rounded


def pct(part: float | None, whole: float | None) -> float | None:
    if part is None or not whole:
        return None
    return r2(part / whole * 100)


def month_label(month: str | None) -> str | None:
    """'2025-07' -> 'July 2025'."""
    if not month or len(month) < 7:
        return month
    try:
        return f"{_MONTH_NAMES[int(month[5:7]) - 1]} {month[:4]}"
    except (ValueError, IndexError):
        return month


def _shift_month(month: str, delta: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    index = y * 12 + (m - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


# --------------------------------------------------------------------------- #
# History                                                                      #
# --------------------------------------------------------------------------- #
def split_history(history: list[dict], level1: dict) -> tuple[list[dict], dict | None]:
    """Return (previous months, current month entry).

    The current month is the history row matching ``bill_month``; if the history
    has no such row but units_consumed is known, a synthetic current entry is used.
    """
    bill_month = level1.get("bill_month")
    rows = [h for h in history if h.get("units") is not None]
    previous = [h for h in rows if h["month"] != bill_month and (not bill_month or h["month"] < bill_month)]
    current = next((h for h in rows if h["month"] == bill_month), None)
    if current is None and level1.get("units_consumed") is not None and bill_month:
        current = {"month": bill_month, "units": level1["units_consumed"], "bill_amount": level1.get("current_bill"),
                   "payment": None}
    return previous, current


def _summary(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    units = [h["units"] for h in rows]
    highest = max(rows, key=lambda h: h["units"])
    lowest = min(rows, key=lambda h: h["units"])
    return {
        "months_count": len(rows),
        "first_month": month_label(rows[0]["month"]),
        "last_month": month_label(rows[-1]["month"]),
        "average_units": r2(mean(units)),
        "total_units": r2(sum(units)),
        "highest": {"month": month_label(highest["month"]), "units": highest["units"]},
        "lowest": {"month": month_label(lowest["month"]), "units": lowest["units"]},
    }


def _months_where(rows: list[dict], predicate) -> dict:
    hits = [h for h in rows if predicate(h["units"])]
    return {"count": len(hits), "months": [f"{month_label(h['month'])} ({h['units']})" for h in hits]}


def threshold_counts(previous: list[dict], current: dict | None, thresholds: list[Number]) -> dict:
    """For each threshold: previous months above / below it, plus counts that include the current month."""
    result = {}
    for t in thresholds:
        above = _months_where(previous, lambda u, t=t: u > t)
        below = _months_where(previous, lambda u, t=t: u < t)
        current_above = (current["units"] > t) if current else None
        current_below = (current["units"] < t) if current else None
        result[str(t)] = {
            "previous_months_above": above,
            "previous_months_below": below,
            "current_month_above": current_above,
            "count_above_including_current_month": above["count"] + (1 if current_above else 0),
            "count_below_including_current_month": below["count"] + (1 if current_below else 0),
        }
    return result


def _change(new: float | None, old: float | None) -> dict | None:
    if new is None or old is None:
        return None
    return {"from": old, "to": new, "difference": r2(new - old), "percent_change": pct(new - old, abs(old)) if old else None}


def usage_insights(history: list[dict], level1: dict) -> dict:
    """Compact usage summary for the UI: graph points, current vs previous, extremes, average."""
    previous, current = split_history(history, level1)
    points = previous + ([current] if current else [])
    prev_month = previous[-1] if previous else None
    summary_prev = _summary(previous)
    return {
        "points": [{"month": h["month"], "units": h["units"], "is_current": h is current} for h in points],
        "current": {"month": current["month"], "units": current["units"]} if current else None,
        "previous": {"month": prev_month["month"], "units": prev_month["units"]} if prev_month else None,
        "change_vs_previous": _change(current["units"], prev_month["units"]) if current and prev_month else None,
        "average_units": summary_prev["average_units"] if summary_prev else None,
        "average_months": summary_prev["months_count"] if summary_prev else 0,
        "highest": _extreme(points, max),
        "lowest": _extreme(points, min),
        "change_vs_average": _change(current["units"], summary_prev["average_units"]) if current and summary_prev else None,
    }


def _extreme(rows: list[dict], fn) -> dict | None:
    if not rows:
        return None
    row = fn(rows, key=lambda h: h["units"])
    return {"month": row["month"], "units": row["units"]}


# --------------------------------------------------------------------------- #
# Full statistics for Level 2                                                  #
# --------------------------------------------------------------------------- #
def numbers_in_questions(questions: list[str]) -> list[Number]:
    """Numbers that look like unit thresholds ('above 300 units', 'more than 150')."""
    found: set[Number] = set()
    for q in questions:
        # Only numbers in a units context: "200 units", "above 300", "more than 150 kWh" (not "last 12 months").
        pattern = r"(?:(?:above|over|below|under|exceed(?:ed|s)?|more than|less than|than)\s+(\d+(?:\.\d+)?))|(\d+(?:\.\d+)?)\s*(?:units?|kwh)"
        for groups in re.findall(pattern, q, flags=re.IGNORECASE):
            match = groups[0] or groups[1]
            value = float(match)
            if 1 <= value <= 5000 and not (1990 <= value <= 2100):  # skip years
                found.add(int(value) if value.is_integer() else value)
    return sorted(found)


def _line_breakdown(lines: list[dict], subtotal: float | None, current_bill: float | None) -> list[dict]:
    base = subtotal if subtotal else sum(l["amount"] for l in lines) or None
    return [
        {
            "label": l.get("label") or l["type"],
            "type": l["type"],
            "amount": l["amount"],
            "percent_of_section_total": pct(l["amount"], base),
            "percent_of_current_bill": pct(l["amount"], current_bill),
        }
        for l in lines
    ]


def _by_type(lines: list[dict]) -> dict:
    totals: dict[str, float] = {}
    for line in lines:
        totals[line["type"]] = totals.get(line["type"], 0) + line["amount"]
    return {k: r2(v) for k, v in totals.items()}


def _days_between(a: str | None, b: str | None) -> int | None:
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days if a and b else None
    except ValueError:
        return None


def compute_stats(
    level1: dict,
    history: list[dict],
    charge_lines: list[dict],
    tax_lines: list[dict],
    printed_percentages: list[dict] | None = None,
    late_surcharges: list[dict] | None = None,
    questions: list[str] | None = None,
    net_metering_evidence: list[dict] | None = None,
    fpa_note: str | None = None,
) -> dict[str, Any]:
    """Every number the answer model may need, each clearly named."""
    units = level1.get("units_consumed")
    current_bill = level1.get("current_bill")
    total_charges = level1.get("total_charges")
    total_taxes = level1.get("total_taxes")
    within = level1.get("payable_within_due_date")
    after = level1.get("payable_after_due_date")

    charges_value = total_charges if total_charges is not None else (sum(c["amount"] for c in charge_lines) if charge_lines else None)
    taxes_value = total_taxes if total_taxes is not None else (sum(t["amount"] for t in tax_lines) if tax_lines else None)
    charges_by_type = _by_type(charge_lines)
    energy = charges_by_type.get("energy")

    previous, current = split_history(history, level1)
    with_current = previous + ([current] if current else [])
    thresholds = sorted(set(DEFAULT_THRESHOLDS) | set(numbers_in_questions(questions or [])))

    stats: dict[str, Any] = {
        "bill_amounts": {
            "current_bill": current_bill,
            "total_charges": charges_value,
            "total_taxes": taxes_value,
            "arrears": level1.get("arrears"),
            "payable_within_due_date": within,
            "payable_after_due_date": after,
            "units_consumed": units,
        },
        "shares": {
            "taxes_percent_of_current_bill": pct(taxes_value, current_bill),
            "charges_percent_of_current_bill": pct(charges_value, current_bill),
            "taxes_percent_of_charges_plus_taxes": pct(taxes_value, (charges_value or 0) + (taxes_value or 0)),
            "taxes_percent_of_charges": pct(taxes_value, charges_value),
            "printed_percentage_split": printed_percentages or [],
        },
        "charge_lines": _line_breakdown(charge_lines, charges_value, current_bill),
        "charges_by_type": charges_by_type,
        "tax_lines": _line_breakdown(tax_lines, taxes_value, current_bill),
        "taxes_by_type": _by_type(tax_lines),
        "per_unit": {
            "effective_cost_per_unit_current_bill": r2(current_bill / units) if current_bill is not None and units else None,
            "energy_charges_per_unit": r2(energy / units) if energy is not None and units else None,
            "charges_per_unit_before_tax": r2(charges_value / units) if charges_value is not None and units else None,
            "taxes_per_unit": r2(taxes_value / units) if taxes_value is not None and units else None,
        },
        "late_payment": {
            "penalty_if_paid_after_due_date": r2(after - within) if None not in (after, within) else None,
            "penalty_percent_of_payable": pct(after - within, within) if None not in (after, within) else None,
            "printed_surcharges": late_surcharges or [],
        },
        "readings": {
            "current_minus_previous_reading": r2(level1["current_reading"] - level1["previous_reading"])
            if None not in (level1.get("current_reading"), level1.get("previous_reading")) else None,
            "printed_units_consumed": units,
        },
        "dates": {
            "days_from_issue_to_due_date": _days_between(level1.get("issue_date"), level1.get("due_date")),
            "days_from_reading_to_due_date": _days_between(level1.get("reading_date"), level1.get("due_date")),
        },
        "history": {
            "note": "previous_months excludes the current bill month; including_current adds it.",
            "current_month": {"month": month_label(current["month"]), "units": current["units"]} if current else None,
            "previous_months": [{"month": month_label(h["month"]), "units": h["units"],
                                 "bill_amount": h.get("bill_amount"), "payment": h.get("payment")} for h in previous],
            "previous_months_summary": _summary(previous),
            "including_current_summary": _summary(with_current),
            "thresholds": threshold_counts(previous, current, thresholds),
        },
    }

    # Month-over-month and same month last year.
    comparisons: dict[str, Any] = {}
    if current:
        last = next((h for h in previous if h["month"] == _shift_month(current["month"], -1)), None)
        year_ago = next((h for h in previous if h["month"] == _shift_month(current["month"], -12)), None)
        summary = stats["history"]["previous_months_summary"]
        comparisons["vs_previous_month_units"] = _change(current["units"], last["units"]) if last else None
        comparisons["previous_month"] = month_label(last["month"]) if last else None
        comparisons["vs_same_month_last_year_units"] = _change(current["units"], year_ago["units"]) if year_ago else None
        comparisons["same_month_last_year"] = month_label(year_ago["month"]) if year_ago else None
        comparisons["vs_previous_months_average_units"] = _change(current["units"], summary["average_units"]) if summary else None
        if last and last.get("bill_amount") is not None and current_bill is not None:
            comparisons["vs_previous_month_bill_amount"] = _change(current_bill, last["bill_amount"])
    stats["comparisons"] = comparisons

    bills = [h for h in previous if h.get("bill_amount") is not None]
    payments = [h for h in previous if h.get("payment") is not None]
    stats["billing_history"] = {
        "months_with_bill_amount": len(bills),
        "average_bill_amount": r2(mean(h["bill_amount"] for h in bills)) if bills else None,
        "highest_bill": {"month": month_label(max(bills, key=lambda h: h["bill_amount"])["month"]),
                         "amount": max(h["bill_amount"] for h in bills)} if bills else None,
        "total_paid": r2(sum(h["payment"] for h in payments)) if payments else None,
        "months_paid_less_than_billed": [month_label(h["month"]) for h in previous
                                         if None not in (h.get("payment"), h.get("bill_amount"))
                                         and h["payment"] < h["bill_amount"] - 1],
    }

    stats["estimates"] = _estimates(stats, units, current_bill)
    stats["last_12_months"] = last_12_months(previous, current)
    stats["seasonal"] = seasonal_comparison(previous, current)
    stats["recent_trend"] = recent_trend(previous, current)
    stats["forecast_next_month"] = forecast_next_month(previous, current)
    stats["payments"] = payment_record(previous)
    stats["monthly_set_aside"] = monthly_set_aside(previous, current, stats["per_unit"]["effective_cost_per_unit_current_bill"])
    stats["bill_at_last_month_units"] = bill_at_last_month_units(previous, current, stats["per_unit"]["effective_cost_per_unit_current_bill"])
    stats["fuel_adjustment"] = fuel_adjustment(charge_lines, fpa_note)
    stats["net_metering"] = net_metering(net_metering_evidence or [], with_current)
    return stats


# --------------------------------------------------------------------------- #
# Helpers for common customer questions                                        #
# --------------------------------------------------------------------------- #
def _window(previous: list[dict], current: dict | None, size: int = 12) -> list[dict]:
    """Rows within the latest ``size`` CALENDAR months (current month included when known).

    Calendar-based, so a history with gaps never stretches back further than ``size`` months.
    """
    rows = previous + ([current] if current else [])
    if not rows:
        return []
    start = _shift_month(rows[-1]["month"], -(size - 1))
    return [h for h in rows if h["month"] >= start]


def _labelled(rows: list[dict]) -> list[str]:
    return [f"{month_label(h['month'])} ({h['units']})" for h in rows]


def last_12_months(previous: list[dict], current: dict | None) -> dict:
    """Highest / lowest month in the latest 12 months, with and without the current month."""
    window = _window(previous, current)
    prev12 = previous[-12:]
    return {
        "months_including_current": _labelled(window),
        "including_current_summary": _summary(window),
        "previous_12_months_summary": _summary(prev12),
    }


def seasonal_comparison(previous: list[dict], current: dict | None) -> dict | None:
    """Summer (Jun-Aug) vs winter (Dec-Feb) units over the latest 12 months shown."""
    window = _window(previous, current)
    summer = [h for h in window if h["month"][5:7] in {"06", "07", "08"}]
    winter = [h for h in window if h["month"][5:7] in {"12", "01", "02"}]
    if not summer or not winter:
        return {"available": False, "summer_months": _labelled(summer), "winter_months": _labelled(winter)}
    s_total, w_total = sum(h["units"] for h in summer), sum(h["units"] for h in winter)
    s_avg, w_avg = s_total / len(summer), w_total / len(winter)
    return {
        "available": True,
        "summer_months": _labelled(summer), "winter_months": _labelled(winter),
        "summer_total": r2(s_total), "winter_total": r2(w_total),
        "summer_average": r2(s_avg), "winter_average": r2(w_avg),
        "difference_total": r2(s_total - w_total),
        "difference_average_per_month": r2(s_avg - w_avg),
        "complete_seasons": len(summer) == 3 and len(winter) == 3,
    }


def recent_trend(previous: list[dict], current: dict | None) -> dict | None:
    """Direction over the latest 3 months (current included), month by month."""
    last3 = _window(previous, current, 3)
    if len(last3) < 2:
        return None
    missing = 3 - len(last3)
    steps = [_change(b["units"], a["units"]) for a, b in zip(last3, last3[1:])]
    diffs = [s["difference"] for s in steps]
    if all(d > 0 for d in diffs):
        direction = "up every month"
    elif all(d < 0 for d in diffs):
        direction = "down every month"
    else:
        direction = "mixed"
    return {
        "months": _labelled(last3),
        "month_to_month_changes": steps,
        "overall_change": _change(last3[-1]["units"], last3[0]["units"]),
        "direction": direction,
        "months_missing_from_history": missing,
    }


def forecast_next_month(previous: list[dict], current: dict | None) -> dict | None:
    """Labelled estimates for next month's units from the 12-month history."""
    window = _window(previous, current)
    if not window:
        return None
    latest = window[-1]["month"]
    next_month = _shift_month(latest, 1)
    year_ago = next((h for h in previous + ([current] if current else []) if h["month"] == _shift_month(next_month, -12)), None)
    result: dict[str, Any] = {
        "next_month": month_label(next_month),
        "estimate_12_month_average": {"value": r2(mean(h["units"] for h in window)),
                                      "method": f"average of the {len(window)} latest months"},
        "estimate_same_month_last_year": {"value": year_ago["units"], "method": f"units in {month_label(year_ago['month'])}"}
        if year_ago else None,
    }
    if len(window) >= 3:  # least-squares line through the months, extended one step
        n = len(window)
        xs, ys = range(n), [h["units"] for h in window]
        x_mean, y_mean = (n - 1) / 2, mean(ys)
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sum((x - x_mean) ** 2 for x in xs)
        result["estimate_linear_trend"] = {"value": r2(max(y_mean + slope * (n - x_mean), 0)),
                                           "method": f"straight-line trend over {n} months ({r2(slope)} units/month)"}
    result["note"] = "Seasonality matters; the same-month-last-year figure is usually the most realistic."
    return result


def payment_record(previous: list[dict]) -> dict:
    """Whether each previous bill shown was paid (only months with printed payment columns count)."""
    with_bill = [h for h in previous if h.get("bill_amount") is not None]
    unpaid = [h for h in with_bill if not h.get("payment")]
    short = [h for h in with_bill if h.get("payment") and h["payment"] < h["bill_amount"] - 1]
    return {
        "months_with_bill_shown": len(with_bill),
        "months_with_payment_shown": sum(1 for h in with_bill if h.get("payment")),
        "months_without_payment": [month_label(h["month"]) for h in unpaid],
        "months_paid_less_than_billed": [f"{month_label(h['month'])} (billed {h['bill_amount']}, paid {h['payment']})" for h in short],
        "total_billed": r2(sum(h["bill_amount"] for h in with_bill)) if with_bill else None,
        "total_paid": r2(sum(h["payment"] or 0 for h in with_bill)) if with_bill else None,
    }


def monthly_set_aside(previous: list[dict], current: dict | None, per_unit: float | None) -> dict | None:
    """Even monthly budget: average printed bill over the latest 12 months (or units x cost as a fallback)."""
    window = _window(previous, current)
    bills = [h for h in window if h.get("bill_amount") is not None]
    if bills:
        total = sum(h["bill_amount"] for h in bills)
        return {"value": r2(total / len(bills)), "total_over_period": r2(total), "months_used": len(bills),
                "method": f"average of {len(bills)} printed monthly bill amounts"}
    if per_unit and window:
        avg_units = mean(h["units"] for h in window)
        return {"value": r2(avg_units * per_unit), "months_used": len(window),
                "method": f"estimate: average {r2(avg_units)} units x PKR {per_unit} per unit (no bill amounts printed)"}
    return None


def bill_at_last_month_units(previous: list[dict], current: dict | None, per_unit: float | None) -> dict | None:
    """Rough bill if next month uses as many units as last month (the month before this bill)."""
    if not previous:
        return None
    # "Last month" is the calendar month before this bill; fall back to the latest month shown.
    wanted = _shift_month(current["month"], -1) if current else None
    last = next((h for h in previous if h["month"] == wanted), previous[-1])
    result: dict[str, Any] = {"last_month": month_label(last["month"]), "last_month_units": last["units"],
                              "last_month_printed_bill": last.get("bill_amount")}
    if per_unit:
        result["estimate"] = {"value": r2(last["units"] * per_unit),
                              "method": f"{last['units']} units x PKR {per_unit} per unit (this bill's effective rate)"}
    return result


def fuel_adjustment(charge_lines: list[dict], note: str | None = None) -> dict:
    """FPA / FCA lines as printed, plus the printed note naming the month they relate to."""
    lines = [l for l in charge_lines if l["type"] == "fpa"]
    return {"lines": [{"label": l.get("label"), "amount": l["amount"]} for l in lines],
            "total": r2(sum(l["amount"] for l in lines)) if lines else None,
            "printed_note_with_month": note}


def net_metering(evidence: list[dict], months: list[dict]) -> dict:
    """Signals for 'is this a net-metered (solar) connection?'."""
    negative = [h for h in months if h["units"] < 0]
    return {
        "printed_evidence": evidence,
        "negative_unit_months": _labelled(negative),
        "likely_net_metered": bool(evidence) or bool(negative),
    }


def _estimates(stats: dict, units: Number | None, current_bill: Number | None) -> dict:
    """Simple, clearly-labelled estimates using only numbers printed on this bill."""
    per_unit = stats["per_unit"]["effective_cost_per_unit_current_bill"]
    summary = stats["history"]["previous_months_summary"]
    estimates: dict[str, Any] = {
        "method_note": "Estimates scale this bill's effective cost per unit (current bill / units). "
                       "Real bills use slab rates, so treat them as rough.",
    }
    if per_unit and summary:
        avg = summary["average_units"]
        estimates["bill_at_average_usage"] = {
            "value": r2(avg * per_unit),
            "method": f"average {avg} units x PKR {per_unit} per unit",
        }
        estimates["annual_cost_at_average_usage"] = {
            "value": r2(avg * per_unit * 12),
            "method": f"average {avg} units x PKR {per_unit} x 12 months",
        }
    if per_unit and units:
        for cut in (10, 20):
            saved_units = units * cut / 100
            estimates[f"saving_if_usage_cut_{cut}_percent"] = {
                "value": r2(saved_units * per_unit),
                "method": f"{cut}% of {units} units = {r2(saved_units)} units x PKR {per_unit}",
            }
        for extra in (50, 100):
            estimates[f"bill_if_{extra}_more_units"] = {
                "value": r2((units + extra) * per_unit),
                "method": f"({units} + {extra}) units x PKR {per_unit}",
            }
    return estimates
