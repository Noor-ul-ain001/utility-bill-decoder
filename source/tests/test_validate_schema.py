"""validate.py consistency checks and schema.py output shape."""

import copy

import validate
from schema import LEVEL1_KEYS, Level1, empty_level1

from conftest import KESC_0008_LEVEL1


def checks_by_name(level1):
    return {c.check: c for c in validate.run_checks(level1)}


def test_all_checks_pass_on_guide_example():
    checks = validate.run_checks(KESC_0008_LEVEL1)
    assert len(checks) == 6
    assert validate.failed(checks) == []


def test_reading_mismatch_is_reported():
    level1 = copy.deepcopy(KESC_0008_LEVEL1)
    level1["units_consumed"] = 200
    check = checks_by_name(level1)["Readings match units"]
    assert not check.passed
    assert "151" in check.detail and "200" in check.detail


def test_charge_sum_mismatch_is_reported():
    level1 = copy.deepcopy(KESC_0008_LEVEL1)
    level1["charges"] = level1["charges"][:-1]  # drop a line
    assert not checks_by_name(level1)["Charge lines add up"].passed


def test_tolerance_of_one_rupee():
    level1 = copy.deepcopy(KESC_0008_LEVEL1)
    level1["total_charges"] = 2861.5  # within +/-1 of 2860.62
    assert checks_by_name(level1)["Charge lines add up"].passed


def test_checks_never_modify_values():
    level1 = copy.deepcopy(KESC_0008_LEVEL1)
    level1["units_consumed"] = 999
    before = copy.deepcopy(level1)
    validate.run_checks(level1)
    assert level1 == before


def test_checks_skipped_when_inputs_missing():
    checks = validate.run_checks(empty_level1())
    assert checks == []


def test_combined_tax_bill_uses_totals():
    level1 = {**empty_level1(), "charges": [{"type": "energy", "amount": 100}], "total_charges": 100,
              "total_taxes": 20, "current_bill": 120}
    names = checks_by_name(level1)
    assert "Tax lines add up" not in names            # no tax lines to sum
    assert names["Charges + taxes = current bill"].passed


def test_check_serializes_for_api():
    check = validate.run_checks(KESC_0008_LEVEL1)[0]
    assert set(check.as_dict()) == {"check", "passed", "detail"}


def test_level1_has_exactly_the_18_guide_keys():
    assert len(LEVEL1_KEYS) == 18
    assert tuple(Level1().to_ordered_dict()) == LEVEL1_KEYS


def test_empty_level1_is_all_null():
    data = empty_level1()
    assert data["charges"] == [] and data["taxes"] == []
    assert data["provider"] is None and data["payable_after_due_date"] is None
