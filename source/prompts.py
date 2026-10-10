"""Prompt text for extraction (Level 1) and question answering (Level 2).

Kept separate from the code so the rules from the GUIDE are easy to review in one place.
"""

from __future__ import annotations

import json

# --------------------------------------------------------------------------- #
# Level 1 extraction                                                           #
# --------------------------------------------------------------------------- #
EXTRACTION_SYSTEM = """You read Pakistani electricity bills (K-Electric, LESCO, IESCO) from images and \
transcribe billing values into JSON. You are a careful transcriber, not a calculator."""

# Worked example from GUIDE section 5.5-5.7 (training bill KESC_0008), in the extended format.
KESC_0008_EXAMPLE = {
    "provider": "KE",
    "tariff": "A1-R",
    "sanctioned_load_kw": "3",
    "bill_month": "Apr-26",
    "reading_date": "03-Apr-26",
    "issue_date": "07-Apr-2026",
    "due_date": "21st Apr 2026",
    "previous_reading": "8819",
    "current_reading": "8970",
    "units_consumed": "151",
    "charge_lines": [
        {"label": "Fixed Charges", "type": "fixed", "amount": "900.00"},
        {"label": "Variable Upto 100 Units (Protected)", "type": "energy", "amount": "1,054.00"},
        {"label": "Variable Upto 200 Units (Protected)", "type": "energy", "amount": "663.51"},
        {"label": "Uniform Quarterly Adjustment", "type": "quarterly_adjustment", "amount": "52.91"},
        {"label": "FCA :Feb-26", "type": "fpa", "amount": "125.27"},
        {"label": "Additional Surcharge (PHL)", "type": "surcharge", "amount": "64.93"},
    ],
    "total_charges": "2,860.62",
    "tax_lines": [
        {"label": "Electricity Duty", "type": "electricity_duty", "amount": "29.41"},
        {"label": "Sales Tax u/s 3(1)*", "type": "gst", "amount": "520.21"},
        {"label": "MUCT (KMC)", "type": "municipal_tax", "amount": "20.00"},
    ],
    "total_taxes": "569.62",
    "current_bill": "3,430.24",
    "arrears": "-0.53",
    "payable_within_due_date": "3,430",
    "payable_after_due_date": "3,716",
    "late_payment_amounts": [
        {"label": "Amount Payable from 22-Apr - 24-Apr with 5% LPS", "amount": "3,574"},
        {"label": "Amount Payable after 24-Apr-26 with 10% LPS", "amount": "3,716"},
    ],
    "late_payment_surcharges": [
        {"label": "Late Payment Surcharge (5%)", "amount": "143.03"},
        {"label": "Late Payment Surcharge (10%)", "amount": "286.06"},
    ],
    "printed_percentages": [
        {"label": "energy charges", "percent": "83.39"},
        {"label": "taxes and duties", "percent": "16.61"},
    ],
    "tariff_slabs": [
        {"label": "Fixed Charges", "units": "3.00", "rate": "300.0000", "amount": "900.00"},
        {"label": "Variable Upto 100 Units (Protected)", "units": "100.00", "rate": "10.5400", "amount": "1,054.00"},
        {"label": "Variable Upto 200 Units (Protected)", "units": "51.00", "rate": "13.0100", "amount": "663.51"},
    ],
    "history": [
        {"month": "2025-04", "units": "141"}, {"month": "2025-05", "units": "138"},
        {"month": "2025-06", "units": "197"}, {"month": "2025-07", "units": "239"},
        {"month": "2025-08", "units": "203"}, {"month": "2025-09", "units": "176"},
        {"month": "2025-10", "units": "173"}, {"month": "2025-11", "units": "187"},
        {"month": "2025-12", "units": "124"},
        {"month": "2026-01", "units": "96", "bill_amount": "2,780.55", "payment": "2780.00"},
        {"month": "2026-02", "units": "88", "bill_amount": "2,782.51", "payment": "2783.00"},
        {"month": "2026-03", "units": "115", "bill_amount": "2,577.31", "payment": "2577.00"},
        {"month": "2026-04", "units": "151"},
    ],
    "other_amounts": [
        {"label": "Opening Balance", "amount": "2,576.47"},
        {"label": "Payments/Adjustment", "amount": "-2,577.00"},
    ],
    "net_metering_evidence": [],
    "fpa_note": "FCA :Feb-26",
}

EXTRACTION_PROMPT = """Read the electricity bill image and return ONE JSON object with the keys shown \
in the example at the end. Transcribe; never calculate.

GENERAL RULES
1. Copy every value AS PRINTED, as a string (keep commas, decimals, "CR" and minus signs exactly as \
they appear; code will convert them). Do not recalculate, round, correct or fill gaps.
2. Use null when a value is not printed, is blank, is covered by a grey box, or is unreadable. Never guess. \
Use [] for an empty list.
3. NEVER output personal identifiers: no names, addresses, CNIC, account / reference / consumer / \
contract / invoice / meter numbers. They are not part of the schema.
4. Bills may be tilted, photographed at an angle, or partly in Urdu. Read the English labels and the digits; \
Urdu text is only a translation of the English labels.
5. Read PRINTED values only. Ignore handwriting, pen marks, circled numbers, stamps and notes written on \
the paper, even when they sit on top of a printed field; if handwriting makes a printed value unreadable, use null.

FIELDS
- provider: "KE" (K-Electric), "LESCO" or "IESCO". The file name hint is {provider_hint}.
- tariff: tariff code exactly as printed (e.g. "A1-R", "A-1a(01)", "A-1b(03)T").
- sanctioned_load_kw: the "Sanc Load" / "S.Load" / "San Load" value (kW).
- bill_month: as printed (e.g. "Apr-26", "JUL 2026"). reading_date, issue_date, due_date: as printed. \
The due date is the last date to pay WITHOUT late surcharge.
- previous_reading, current_reading, units_consumed: the printed meter readings and the units billed \
this month. If several meter rows exist, use the main energy row; units_consumed is the billed units as printed.
- charge_lines: ONE entry per printed line in the electricity-charges section, in printed order. \
Skip lines that are blank or printed as 0. Keep separate entries when the same type appears twice \
(e.g. two "Variable Upto ... Units" lines are two energy entries). Never put subtotal lines here, and never unit counts such as "UNITS CONSUMED".
- tax_lines: ONE entry per printed line in the taxes / duties / government-charges section. Classify a \
line by the SECTION it is printed in, not by its name. If the bill prints only one combined tax amount \
(e.g. a single "Taxes" line in a summary block), return tax_lines [] and put that amount in total_taxes.
- total_charges: the printed charges subtotal (null if no subtotal is printed). \
total_taxes: the printed tax subtotal (null if none).
- current_bill: this month's bill amount as printed. arrears: previous dues / arrears carried forward, \
keeping the printed sign; null if blank.
- payable_within_due_date: amount payable by the due date. payable_after_due_date: the amount payable \
after the due date; if several late amounts are printed, put the HIGHEST here and list all of them in \
late_payment_amounts.
- Credits: amounts such as "38209CR" stay as printed with CR (they become negative). Subsidy / relief \
lines are deductions.

CHARGE TYPES (charge_lines.type)
energy = cost of units (Variable Upto ... Units, Cost of Electricity, Energy Charges, Total Electricity Charges \
when it is the only energy line); fixed = fixed charges; fpa = fuel price / fuel charges adjustment (FPA, FCA, \
Total FPA); quarterly_adjustment = QTA, Uniform Quarterly Adjustment; surcharge = surcharges such as \
Additional Surcharge (PHL), F.C Surcharge; meter_rent = meter or service rent; subsidy = government subsidy \
or relief; other = anything else.

TAX TYPES (tax_lines.type)
gst = sales tax / GST (including GST on FPA); electricity_duty = electricity duty (ED); income_tax = income \
tax; municipal_tax = municipal / local charges under taxes, e.g. MUCT (KMC); other_tax = extra tax, further \
tax, TV fee, any other tax line.

LAYOUT NOTES
- K-Electric: the "Bill Calculation" table lists charge lines above the "Electricity Charges" subtotal and \
tax lines between it and the "Taxes and Duties" subtotal. "Electricity Charges for current month" is the \
current bill. "Previous Dues" is the arrears. Late amounts appear as "Amount Payable ... with 5% / 10% LPS".
- LESCO / IESCO: the "BILL CHARGES BREAKDOWN" block is a summary laid out in TWO column pairs: the left pair is Total Electricity Charges, Subsidies, Net Electricity Charges, Taxes, Current Bill, Grand Total; the right pair is Arrears, Installment, Adjustments, W.E Credit, Lock Open Credit, Total FPA. Each amount sits on the SAME horizontal row as its label (Urdu text between them is only a translation); read row by row and never shift a value to the next label. Cross-check: Net Electricity Charges + Taxes is about Current Bill, and Grand Total equals PAYABLE WITHIN DUE DATE. The "L.P SURCHARGE" amounts next to the due date are \
late-payment surcharges (put them in late_payment_surcharges), never charge lines. An amount followed by marks such as "/ 2" is still that amount (e.g. Arrears "39411 / 2" means 39411). Lines such as "Total Electricity Charges" \
(energy), "Subsidies" (subsidy) and "Total FPA" (fpa) are charge lines; "Net Electricity Charges" is the \
charges subtotal (total_charges: the money amount printed on the Net Electricity Charges row, after the \
percentage, never a meter reading); "Taxes" is a combined tax amount (tax_lines [], total_taxes set); \
"Current Bill" is current_bill; "Arrears" is arrears. Zero lines (Installment, Adjustments, W.E Credit...) \
are skipped. The "PAYABLE AFTER DUE DATE" box can show more than one amount; take the highest. Text such \
as "NOT TO BE PAID" is not an amount (use null).

EXTRA FIELDS (used for answering questions later; same transcription rules)
- late_payment_amounts / late_payment_surcharges: every printed tier with its label.
- printed_percentages: any printed percentage split (e.g. energy 83.39 % / taxes 16.61 %, or \
"Net Electricity Charges 84.76 %").
- tariff_slabs: units / rate / amount rows if a rate table is printed, else [].
- history: every month in the usage / billing history (bar chart or table), INCLUDING the current month if \
it is shown. month must be "YYYY-MM": infer the year from the printed year labels and month order. \
units, bill_amount and payment as printed (null when not shown for that month). Merge the usage chart and \
the billing/payment table into one row per month. LESCO / IESCO "BILL HISTORY" tables are split into TWO \
side-by-side halves (e.g. Jul-Dec on the left, Jan-Jun on the right): read BOTH halves, usually 12 months. \
Keep minus signs on units (net-metering bills can show exported units as negative). The FIRST history row \
is sometimes printed squeezed into or overlapping the column-header line (e.g. "AUG 25 721 80594 80594" \
printed over "MONTH STATUS UNITS BILL PAYMENT"); include that month too.
- other_amounts: other printed money lines not captured above (opening balance, payments, deferred amount, \
installments, FPA notes from the message box).
- fpa_note: the printed note that says WHICH month the fuel price adjustment is for, translated to English, \
e.g. "FPA for Jun-26: 412 units @ 0.7503 = Rs 371" (often an Urdu sentence in a yellow box) or \
"FPA FEB-26 @ 1.4235", or the month inside a KE label such as "FCA :Feb-26". null if no month is printed.
- net_metering_evidence: every printed sign of a net-metered (solar) connection, with its value if any: \
"NET METERING CONNECTION", "Net Metering Benefit", "Customer Type NM", import / export meter rows, exported \
units, a tariff code ending in "T" next to such text. [] for a standard connection.

WORKED EXAMPLE (training bill KESC_0008; the image you receive is a different bill):
{example}

Return only the JSON object for the bill in the image."""

REEXTRACT_PROMPT = """Your previous reading of this bill failed these consistency checks:
{failures}

Previous reading (JSON):
{previous}

Look at the image again, focusing on the areas involved in the failed checks (meter readings, each \
charge and tax line and their subtotals, current bill, arrears, payable amounts). Correct any digit, sign, \
decimal point or missed/duplicated line you misread. A check may also fail because the bill itself is \
like that (for example FPA billed outside the subtotal); in that case keep the printed values. Never invent \
or calculate values to make a check pass.

Return the complete corrected JSON object with the same keys and the same transcription rules."""


def extraction_prompt(provider_hint: str | None) -> str:
    return EXTRACTION_PROMPT.format(
        provider_hint=provider_hint or "unknown",
        example=json.dumps(KESC_0008_EXAMPLE, ensure_ascii=False),
    )


def reextract_prompt(failures: list[str], previous: dict) -> str:
    return REEXTRACT_PROMPT.format(
        failures="\n".join(f"- {f}" for f in failures),
        previous=json.dumps(previous, ensure_ascii=False),
    )


# --------------------------------------------------------------------------- #
# Level 2 answers                                                              #
# --------------------------------------------------------------------------- #
ANSWER_SYSTEM = """You explain Pakistani electricity bills to customers in plain, friendly English. \
You ground every statement in the bill data you are given."""

ANSWER_RULES = """ANSWER RULES
1. Write in English only, even though parts of the bill are in Urdu.
2. Use ONLY the bill data below (and the bill image to double-check). Do not use outside tariff, rate or \
policy information.
3. Never do your own arithmetic. Every average, difference, count, percentage, share, per-unit cost and \
estimate must come from COMPUTED_STATS. Quote those numbers (rounded sensibly, e.g. 2 decimals for PKR, \
1 decimal for percentages).
4. Label estimates clearly as estimates and say in one short clause how they were calculated.
5. If a question can reasonably mean more than one thing (e.g. whether the current month counts as part of \
"history", or "bill" meaning current bill vs payable amount), state the interpretation you used or answer both.
6. If the bill does not show something needed, say so plainly (e.g. "The bill does not show ...") instead \
of guessing.
7. Never mention names, addresses, CNIC, account, reference, consumer or meter numbers.
8. Write for a customer: never mention JSON, field names, "null", COMPUTED_STATS or how the data was \
provided. When a value is missing, say "the bill does not show ...". When counting months, name them.
9. Use the most specific printed detail: for late payment list EVERY printed tier with its date and amount \
(surcharge and total payable); for fuel adjustment give the amount AND the month from the FPA note / label.
10. Be concise and specific: 1-3 sentences, PKR amounts written like "PKR 3,430.24", months like \
"July 2025". Mention the relevant printed line items when they help.

STYLE EXAMPLES (training bill KESC_0008):
Q: How much of my bill is taxes?
A: Taxes and duties total PKR 569.62 out of your current bill of PKR 3,430.24, or about 16.6%. The bill \
shows a split of 83.39% energy charges and 16.61% taxes. The tax lines are sales tax (PKR 520.21), \
electricity duty (PKR 29.41), and MUCT (KMC) (PKR 20.00).
Q: How many months in my history went above 200 units?
A: Two of the 12 previous months exceeded 200 units: July 2025 (239) and August 2025 (203). The current \
month used 151 units, so the count is two whether or not the current month is included."""

BATCH_ANSWER_PROMPT = """{rules}

BILL_DATA (values read from the bill; amounts in PKR, credits negative):
{bill}

COMPUTED_STATS (calculated in code from BILL_DATA; use these numbers):
{stats}

QUESTIONS:
{questions}

Return a JSON object mapping each question id to its answer string, e.g. {{"Q1": "...", "Q2": "..."}}. \
Answer every question id listed; never leave an answer empty."""

SINGLE_ANSWER_PROMPT = """{rules}

BILL_DATA (values read from the bill; amounts in PKR, credits negative):
{bill}

COMPUTED_STATS (calculated in code from BILL_DATA; use these numbers):
{stats}

QUESTION: {question}

Return a JSON object {{"answer": "..."}}."""
