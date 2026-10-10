"""calculator.py: every Level 2 number is computed in code (GUIDE 6.1 'get the numbers right')."""

import pytest

import calculator
import normalize

from conftest import KESC_0008_LEVEL1


@pytest.fixture
def kesc(kesc_extended):
    history = normalize.normalize_history(kesc_extended)
    charges = normalize.normalize_lines(kesc_extended["charge_lines"], ("fixed", "energy", "fpa", "surcharge", "quarterly_adjustment"), "other")
    taxes = normalize.normalize_lines(kesc_extended["tax_lines"], ("gst", "electricity_duty", "municipal_tax"), "other_tax")
    return KESC_0008_LEVEL1, history, charges, taxes


def test_split_history_separates_current_month(kesc):
    level1, history, _, _ = kesc
    previous, current = calculator.split_history(history, level1)
    assert len(previous) == 12
    assert current == {"month": "2026-04", "units": 151, "bill_amount": None, "payment": None}


def test_split_history_synthesizes_current_month_when_missing(kesc):
    level1, history, _, _ = kesc
    previous, current = calculator.split_history(history[:-1], level1)
    assert len(previous) == 12
    assert current["units"] == 151 and current["month"] == "2026-04"


def test_guide_sample_months_above_200(kesc):
    """GUIDE 6.2: two of the 12 previous months exceeded 200 units (July 2025, August 2025)."""
    level1, history, charges, taxes = kesc
    stats = calculator.compute_stats(level1, history, charges, taxes, questions=["above 200 units?"])
    t200 = stats["history"]["thresholds"]["200"]
    assert t200["previous_months_above"] == {"count": 2, "months": ["July 2025 (239)", "August 2025 (203)"]}
    assert t200["count_above_including_current_month"] == 2
    assert t200["current_month_above"] is False


def test_guide_sample_tax_share(kesc):
    """GUIDE 6.2: taxes PKR 569.62 of PKR 3,430.24 is about 16.6%."""
    level1, history, charges, taxes = kesc
    stats = calculator.compute_stats(level1, history, charges, taxes)
    assert stats["shares"]["taxes_percent_of_current_bill"] == pytest.approx(16.61, abs=0.01)
    assert stats["bill_amounts"]["total_taxes"] == 569.62


def test_history_summary(kesc):
    level1, history, charges, taxes = kesc
    summary = calculator.compute_stats(level1, history, charges, taxes)["history"]["previous_months_summary"]
    assert summary["months_count"] == 12
    assert summary["average_units"] == pytest.approx(156.42, abs=0.01)
    assert summary["highest"] == {"month": "July 2025", "units": 239}
    assert summary["lowest"] == {"month": "February 2026", "units": 88}


def test_comparisons(kesc):
    level1, history, charges, taxes = kesc
    comp = calculator.compute_stats(level1, history, charges, taxes)["comparisons"]
    assert comp["vs_previous_month_units"]["difference"] == 36          # 151 - 115
    assert comp["vs_previous_month_units"]["percent_change"] == pytest.approx(31.3, abs=0.01)
    assert comp["same_month_last_year"] == "April 2025"
    assert comp["vs_same_month_last_year_units"]["difference"] == 10    # 151 - 141


def test_per_unit_and_late_penalty(kesc):
    level1, history, charges, taxes = kesc
    stats = calculator.compute_stats(level1, history, charges, taxes)
    assert stats["per_unit"]["effective_cost_per_unit_current_bill"] == pytest.approx(22.72, abs=0.01)
    assert stats["late_payment"]["penalty_if_paid_after_due_date"] == 286    # 3716 - 3430
    assert stats["readings"]["current_minus_previous_reading"] == 151


def test_estimates_are_labelled_with_method(kesc):
    level1, history, charges, taxes = kesc
    estimates = calculator.compute_stats(level1, history, charges, taxes)["estimates"]
    assert "method_note" in estimates
    est = estimates["bill_at_average_usage"]
    assert est["value"] > 0 and "average" in est["method"]


def test_numbers_in_questions_become_thresholds():
    assert calculator.numbers_in_questions(["above 300 units in 2025?", "more than 150"]) == [150, 300]


def test_stats_survive_missing_data():
    stats = calculator.compute_stats({k: None for k in KESC_0008_LEVEL1} | {"charges": [], "taxes": []}, [], [], [])
    assert stats["per_unit"]["effective_cost_per_unit_current_bill"] is None
    assert stats["history"]["previous_months_summary"] is None
    assert stats["comparisons"] == {}


def test_usage_insights_for_ui(kesc):
    level1, history, _, _ = kesc
    usage = calculator.usage_insights(history, level1)
    assert len(usage["points"]) == 13
    assert usage["points"][-1]["is_current"] is True
    assert usage["previous"] == {"month": "2026-03", "units": 115}
    assert usage["change_vs_previous"]["difference"] == 36
    assert usage["highest"] == {"month": "2025-07", "units": 239}
    assert usage["lowest"] == {"month": "2026-02", "units": 88}
    assert usage["average_units"] == pytest.approx(156.42, abs=0.01)
    assert usage["average_months"] == 12


def test_usage_insights_without_history():
    usage = calculator.usage_insights([], {"bill_month": None, "units_consumed": None})
    assert usage["points"] == [] and usage["highest"] is None and usage["average_units"] is None
