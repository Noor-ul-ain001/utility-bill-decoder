# Utility Bill Decoder

Reads Pakistani electricity bills (K-Electric, LESCO, IESCO) from images and produces:

- **Level 1** – one JSON object per bill (GUIDE section 5.1) → `output/level1.csv`
- **Level 2** – plain-English answers to the 12 questions per bill → `output/level2.csv`

A Python CLI does the scored work. A FastAPI backend and a React UI reuse the same modules for the demo.

## Runtime

- **Python 3.11+** (developed and tested on Python 3.14)
- **Node.js 22+** (only for the optional web UI; tested on Node 24)

## Setup

```bash
# from the project root (the folder that contains source/, test/, train/)
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r source/requirements.txt

cp source/.env.example source/.env     # then put your Gemini API key in source/.env
```

`.env` variables (all read by `config.py`):

| Variable | Value |
|---|---|
| `MODEL_PROVIDER` | `google` |
| `MODEL_NAME` | `gemini-3.5-flash-lite` |
| `API_KEY` | your Google AI Studio key |
| `MIN_SECONDS_BETWEEN_CALLS` | optional, default `4.5` (free tier: 15 requests/min) |
| `ANSWER_WITH_IMAGE` | optional, default `true`: also send the bill image with Level 2 questions |

## Run

**CLI (generates both CSVs):**

```bash
cd source && python main.py --bills ../test/bills --csv ../test/csv --out ../output
```

Options:

| Flag | Meaning |
|---|---|
| `--only KESC_0002` | process only this bill (repeatable or comma-separated); other rows keep earlier results |
| `--no-cache` | ignore `output/cache/` and call the model again |
| `--level 1\|2\|all` | which CSV(s) to write (default `all`) |
| `--demo` | print Level 1 JSON and checks for every image in `--bills`, no CSV needed |

```bash
cd source && python main.py --bills ../train/bills --demo     # try it on the training bills
```

The CLI prints per-bill progress, every validation warning and a final summary (bills OK, warnings, failures).
A bill that fails never stops the run: it gets an all-null Level 1 JSON and fallback answers, and the error is logged.

**Backend:**

```bash
cd source && uvicorn api:app --reload --port 8000
```

**Frontend:**

```bash
cd source/web && npm install && npm run dev        # http://localhost:5173
```

The UI reads `VITE_API_URL` (see `web/.env.example`, default `http://localhost:8000`).

The UI has three views:

- **Overview** - upload a bill or pick a sample. It shows the payable amount, a charges vs taxes split,
  readings, usage insights (monthly units graph, this month vs last month, highest and lowest month,
  average monthly units), every charge and tax line, the consistency checks and the raw Level 1 JSON.
- **Ask** - free-form questions with suggestion chips; each answer uses the same calculator as Level 2.
- **Batch run** - runs the CLI pipeline on the *Test data* (`test/`) or *Training data* (`train/`) preset,
  lists every bill and offers both CSVs for download. `train/csv/` holds templates with the GUIDE sample
  questions, so the batch can be tried before the test data is released.

The layout is responsive from wide desktops down to very narrow phones (about 210 px).

## Architecture

```
source/
├── main.py         CLI entry point (argparse) → pipeline.run_batch
├── pipeline.py     orchestration shared by CLI and API; on-disk cache; never crashes on one bill
├── extractor.py    image → extended JSON (model) → Level 1 (code); targeted re-extraction
├── prompts.py      extraction / re-extraction / answer prompts (GUIDE rules + KESC_0008 example)
├── llm.py          google-genai client, shared rate limiter, retries with exponential backoff, JSON mode
├── schema.py       Pydantic models: ExtendedBill (model output) and Level1 (exact 18-key output)
├── normalize.py    printed text → typed values: "Rs. 19,964"→19964, "38209CR"→-38209, dates, enums
├── validate.py     consistency checks (readings, subtotals, bill = charges + taxes, payable)
├── calculator.py   all Level 2 arithmetic: shares, history stats, thresholds, comparisons, estimates
├── answerer.py     Level 2: 12 questions in one call per bill; single-question mode for the UI
├── csv_io.py       reads templates, writes CSVs with the csv module (UTF-8, QUOTE_MINIMAL)
├── config.py       environment loading and constants
├── api.py          FastAPI app (thin layer over pipeline.py): health, samples, datasets, extract, ask, batch, download
└── web/            React + Vite + TypeScript + Tailwind demo UI
```

Flow for one bill:

```
image ──► Gemini (JSON mode + response schema) ──► ExtendedBill (printed strings)
                                                     │
                                normalize.py (code) ─┴─► Level 1 JSON ──► validate.py
                                                                            │ 2+ checks fail?
                                     re-read once, listing the failed checks ◄┘ keep the better reading
Level 1 + history + line labels ──► calculator.py ──► stats ─┐
bill image + bill data + stats + 12 questions ───────────────┴─► Gemini ──► {Q1..Q12: answer}
```

## Design choices

- **The model reads; code converts and calculates.** The extraction schema asks for values *as printed*
  (`"54770CR"`, `"21st Apr 2026"`). `normalize.py` converts them deterministically, so sign, comma and date
  rules are applied the same way every time. Every Level 2 number (tax share, averages, months above N units,
  month-over-month change, cost per unit, late penalty, estimates) is computed in `calculator.py`, and the
  model is told to quote those numbers rather than do arithmetic. Numbers in the questions (for example
  "above 300 units") automatically become extra thresholds.
- **Validation with targeted re-extraction.** `validate.py` checks readings against units, line items against
  subtotals, charges + taxes against the current bill, and current bill + arrears against the payable amount.
  Checks only report and never change printed values. If two or more fail, the bill is re-read once with the
  failed checks listed, and the reading that passes more checks is kept.
- **Extended extraction.** Besides the Level 1 fields, the model returns history (units, bill, payment per
  month), labelled charge and tax lines, printed percentage splits, late-payment tiers and tariff slabs. These
  are used only for Level 2 answers and the UI.
- **Rate-limit friendly.** One extraction call per bill (two only when validation fails) and one call for all
  12 questions per bill. A shared limiter keeps calls at least 4.5 s apart, and 429/5xx errors are retried
  with exponential backoff (up to 4 retries).
- **Caching.** Extractions are cached in `output/cache/{bill_id}.json`, keyed by image SHA-256 and model, and
  answers by question set. Re-runs skip finished bills; `--no-cache` forces fresh calls.
- **Privacy.** Personal identifiers are not in the schema, unknown keys are dropped, and long digit runs in
  labels are removed.
- **Never an empty cell.** A missing answer triggers one retry for that bill, then the fallback
  "The bill does not show enough information to answer this."

## AI usage

| Category | Used |
|---|---|
| Models | Gemini `gemini-3.5-flash-lite` (via `MODEL_NAME`) |
| APIs | Google Gemini API (official `google-genai` Python SDK) |
| Services | none |
| Local OCR | none |
| AI coding tools | Claude Code (Claude) |

The model is used for the two tasks that need it: reading the bill images and writing plain-English answers.
Parsing, validation, arithmetic, CSV handling and caching are ordinary Python code.
