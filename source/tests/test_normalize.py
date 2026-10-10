"""normalize.py: printed text -> typed Level 1 values (GUIDE 5.2-5.4)."""

import pytest

import normalize
from schema import LEVEL1_KEYS

from conftest import KESC_0008_LEVEL1


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("Rs. 19,964", 19964),          # GUIDE 5.2: strip currency and commas
        ("38209CR", -38209),            # GUIDE 5.2: CR -> negative
        ("54,770 Cr", -54770),
        ("-0.53", -0.53),
        ("2,860.62", 2860.62),
        ("1,054.00", 1054),             # whole numbers become int
        ("(120)", -120),                # accounting negative
        ("39411 / 2", 39411),           # trailing installment mark
        ("Rs.3,716", 3716),
        ("0", 0),
        (3.0, 3),
        (2860.62, 2860.62),
    ],
)
def test_parse_amount_values(printed, expected):
    result = normalize.parse_amount(printed)
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize("printed", [None, "", "-", "—", "N/A", "NOT TO BE PAID", "unreadable", "abc", True])
def test_parse_amount_returns_none_for_unavailable(printed):
    assert normalize.parse_amount(printed) is None


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("22nd Sep 2026", "2026-09-22"),   # GUIDE 5.2 example
        ("21st Apr 2026", "2026-04-21"),
        ("07-Apr-2026", "2026-04-07"),
        ("03-Apr-26", "2026-04-03"),
        ("17 JUL 26", "2026-07-17"),
        ("08 OCT 26", "2026-10-08"),
        ("2026-04-21", "2026-04-21"),
        ("21/04/2026", "2026-04-21"),      # day first, as printed in Pakistan
        ("Apr 21, 2026", "2026-04-21"),
    ],
)
def test_parse_date(printed, expected):
    assert normalize.parse_date(printed) == expected


@pytest.mark.parametrize("printed", [None, "", "31 Feb 2026", "not a date", "13/13/2026"])
def test_parse_date_invalid(printed):
    assert normalize.parse_date(printed) is None


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("MAR 2026", "2026-03"),          # GUIDE 5.2 example
        ("Apr-26", "2026-04"),
        ("JUL 2026", "2026-07"),
        ("SEP 26", "2026-09"),
        ("03/26", "2026-03"),
        ("Sep25", "2025-09"),
        ("2026-04", "2026-04"),
        ("21st Apr 2026", "2026-04"),
    ],
)
def test_parse_month(printed, expected):
    assert normalize.parse_month(printed) == expected


@pytest.mark.parametrize(
    ("value", "bill_id", "expected"),
    [
        ("KE", None, "KE"),
        ("K-Electric", None, "KE"),
        (None, "KESC_0002", "KE"),        # KESC file names -> KE
        ("Lahore Electric Supply Company", None, "LESCO"),
        ("iesco", None, "IESCO"),
        (None, "LESCO_0008", "LESCO"),
        ("unknown co", None, None),
    ],
)
def test_normalize_provider(value, bill_id, expected):
    assert normalize.normalize_provider(value, bill_id) == expected


def test_normalize_type_falls_back_to_other():
    assert normalize.normalize_type("Quarterly Adjustment", ("quarterly_adjustment", "other"), "other") == "quarterly_adjustment"
    assert normalize.normalize_type("mystery", ("energy", "other"), "other") == "other"


def test_lines_skip_blank_and_zero_and_keep_duplicates():
    lines = [
        {"label": "Variable 1", "type": "energy", "amount": "100"},
        {"label": "Variable 2", "type": "energy", "amount": "200"},   # duplicate type kept
        {"label": "Installment", "type": "other", "amount": "0"},     # zero skipped
        {"label": "Blank", "type": "other", "amount": None},          # blank skipped
        {"label": "Relief", "type": "subsidy", "amount": "3,332"},   # subsidy forced negative
    ]
    result = normalize.normalize_lines(lines, ("energy", "subsidy", "other"), "other")
    assert [(l["type"], l["amount"]) for l in result] == [("energy", 100), ("energy", 200), ("subsidy", -3332)]


def test_to_level1_reproduces_guide_worked_example(kesc_extended):
    level1 = normalize.to_level1(kesc_extended, "KESC_0008")
    assert level1 == KESC_0008_LEVEL1
    assert tuple(level1) == LEVEL1_KEYS  # exact key order of GUIDE 5.1


def test_to_level1_lesco_summary_layout(lesco_extended):
    level1 = normalize.to_level1(lesco_extended, "LESCO_0005")
    assert level1["provider"] == "LESCO"
    assert level1["bill_month"] == "2026-07"
    assert level1["units_consumed"] == 1037
    assert level1["charges"] == [{"type": "energy", "amount": 17367.77}]
    assert level1["taxes"] == []                 # combined tax only -> []
    assert level1["total_taxes"] == 3358.23      # ... and the amount goes to total_taxes
    assert level1["payable_within_due_date"] == -54770
    assert level1["payable_after_due_date"] is None


def test_payable_after_uses_highest_late_amount(kesc_extended):
    kesc_extended["payable_after_due_date"] = "3,574"  # model picked the lower tier
    assert normalize.payable_after(kesc_extended) == 3716


def test_to_level1_all_nulls_keeps_every_key():
    level1 = normalize.to_level1({}, None)
    assert tuple(level1) == LEVEL1_KEYS
    assert level1["charges"] == [] and level1["taxes"] == []
    assert all(level1[k] is None for k in LEVEL1_KEYS if k not in ("charges", "taxes"))


def test_normalize_history_sorts_and_dedupes():
    history = normalize.normalize_history({"history": [
        {"month": "Feb 26", "units": "88"},
        {"month": "2026-01", "units": "96"},
        {"month": "FEB 2026", "units": "90"},   # same month again: last one wins
        {"month": "garbage", "units": "1"},
    ]})
    assert [(h["month"], h["units"]) for h in history] == [("2026-01", 96), ("2026-02", 90)]
