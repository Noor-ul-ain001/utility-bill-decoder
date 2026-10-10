# ⚡ Utility Bill Decoder

**An AI assistant that reads Pakistani electricity bills (K-Electric, LESCO, IESCO), extracts every billing
detail as structured JSON, checks the numbers, and answers customer questions in plain English.**

Built for the **WTQ Build Track** challenge.

| | URL |
|---|---|
| 🌐 **Live app** | **https://utility-bill-decoder.vercel.app** |
| 🔌 **Live API** | **https://utility-bill-decoder-api.vercel.app** (health check: [`/api/health`](https://utility-bill-decoder-api.vercel.app/api/health)) |
| 📘 **Full technical docs** | [`source/README.md`](source/README.md) |

---

## The problem

Electricity bills in Pakistan mix tariff slabs, fuel price adjustments (FPA), quarterly adjustments, several
taxes, arrears and late-payment surcharges, and every provider prints them differently. Many bills are
photos: tilted, partly in Urdu, with grey boxes over personal details and even handwriting on top.
Utility Bill Decoder turns any of these into clean data and clear answers.

## What it does

### Level 1: extraction
Reads a bill image and returns one JSON object with the 18 fields of the challenge schema: provider, tariff,
sanctioned load, billing month, reading / issue / due dates, meter readings, units, every charge line, every
tax line, subtotals, current bill, arrears, and amounts payable before and after the due date.

### Level 2: questions
Answers questions such as *"Which month had the highest units?"*, *"How much more do I use in summer than
winter?"* or *"How much should I set aside each month?"*, with accurate numbers computed in code and estimates
clearly labelled.

### Outputs
`python main.py` fills the challenge templates and writes `output/level1.csv` (10 bills) and
`output/level2.csv` (120 answers).

## Features

### Web app ([live](https://utility-bill-decoder.vercel.app))

**Overview tab**
- **Upload a bill**: drag-and-drop, tap to browse, or the *Upload a bill* button; PNG/JPG with a preview.
- **Sample bills gallery**: one click decodes any of the 15 training/test bills.
- **Payable card**: amount due by the due date, the late-payment increase, check status, and a breakdown
  of how the payable amount is built (current bill + arrears + FPA billed separately).
- **Summary tiles**: units used, current bill, arrears and amount after the due date.
- **Where it goes**: donut chart of charges vs taxes around the current bill.
- **Readings**: previous/current reading, units, sanctioned load, reading, issue and due dates.
- **Usage insights**:
  - monthly units graph with the current month and a dashed average line;
  - this month vs the previous month (difference and %);
  - highest and lowest month;
  - average monthly units and how this bill compares.
- **Charges and Taxes & duties**: every printed line with its type, a share bar and the printed subtotal.
- **Consistency checks**: green/red results for readings vs units, line items vs subtotals,
  charges + taxes vs current bill, current bill + arrears (+ FPA) vs payable, and late vs on-time amounts.
- **Raw Level 1 JSON**: collapsible view and a *Copy JSON* button.
- **Full-size bill viewer**: click the bill image to zoom; Esc closes it.

**Ask tab**
- Free-text questions about the decoded bill, with a running Q&A history.
- One-click chips for the 12 official challenge questions (solar connection, highest month, fuel
  adjustment, late surcharges, year-on-year, average, summer vs winter, payment record, 3-month trend,
  next-month forecast, monthly budget, bill at last month's usage) plus a few extra ones.

**Batch run tab**
- Pick the *Test data* or *Training data* preset (or custom folders) and run the full pipeline.
- Live timer, per-bill results (provider, payable, checks passed, cached or freshly read).
- Download `level1.csv` and `level2.csv`.

**Everywhere**
- Live **agent status** pill: *Agent ready*, *Reading bill…*, *Answering…*, *Running batch…*, *Agent offline*.
- Loading skeletons, friendly error banners, disabled buttons while busy, pointer cursors on all clickable
  elements.
- Fully responsive, from wide desktops down to very narrow phones (about 210 px wide).

### Command line
```bash
cd source
python main.py --bills ../test/bills --csv ../test/csv --out ../output   # both CSVs
python main.py --bills ../train/bills --demo                             # print Level 1 JSON
python main.py ... --only KESC_0002 --no-cache --level 1                 # targeted re-runs
```
Shows per-bill progress, every validation warning, and a final summary. A failing bill never stops the run.

### REST API (FastAPI)
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | model name and whether an API key is configured (never the key) |
| POST | `/api/extract` | upload an image → Level 1 JSON, labelled lines, history, usage insights, checks |
| POST | `/api/extract-sample` | the same for a bundled sample bill |
| POST | `/api/ask` | answer one question about a decoded bill |
| GET | `/api/samples`, `/api/samples/{name}` | list or serve sample bill images |
| GET | `/api/datasets` | batch presets and whether their folders exist |
| POST | `/api/batch` | run the full pipeline on a folder and return per-bill results |
| GET | `/api/download/{level1\|level2}` | download the generated CSVs |

## How it works

```
bill image ──► Gemini (JSON mode + schema) ──► values exactly as printed ("54770CR", "21st Apr 2026")
                                                   │
                     normalize.py (code) ──────────┴──► Level 1 JSON ──► validate.py consistency checks
                                                                          │ 2+ checks fail?
                                          targeted re-read of the failed areas ◄┘ keep the better reading
Level 1 + history + line labels ──► calculator.py (all arithmetic) ──► stats ─┐
bill image + bill data + stats + questions ───────────────────────────────────┴─► Gemini ──► answers
```

Key design choices:
- **The model reads; code converts and calculates.** CR → negative, commas, dates, enums, averages,
  shares, trends and forecasts are deterministic Python, so numbers are never hallucinated.
- **Validation with targeted re-extraction.** Checks never change printed values. When two or more fail,
  the bill is re-read once with the failed checks listed, and the more consistent reading wins.
- **Rate-limit friendly.** One extraction call per bill and one call for all 12 questions. A shared limiter
  and exponential-backoff retries keep within the free tier.
- **Caching.** Extractions and answers are cached by image hash and model, so re-runs are instant.
- **Privacy.** Names, addresses, CNIC and account/reference/meter numbers are never extracted.

## Tech stack

| Layer | Technology |
|---|---|
| AI model | Google **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`) via the official `google-genai` SDK |
| Core pipeline + CLI | Python 3.11+, Pydantic |
| Backend | FastAPI (Vercel Python runtime in production, uvicorn locally) |
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS v4 (Vercel) |
| Tests | pytest (normalization, validation, calculator) |

## Run it locally

```bash
python -m venv .venv && .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r source/requirements.txt
copy source\.env.example source\.env                    # add your Gemini API key

cd source && uvicorn api:app --reload --port 8000       # backend  → http://localhost:8000
cd source/web && npm install && npm run dev             # frontend → http://localhost:5173
```

For local development the frontend uses `http://localhost:8000` (see `source/web/.env.example`). Production
builds use `source/web/.env.production`, which points to the deployed API.

## Repository layout

```
├── source/            Python pipeline, CLI, FastAPI app, React UI (web/), tests
├── output/            level1.csv and level2.csv generated for the 10 test bills
├── make_zip.py        builds and verifies the challenge submission ZIP
└── vercel.json        backend deployment config (frontend deploys from source/web)
```

## AI usage

| Category | Used |
|---|---|
| Models | Gemini `gemini-3.5-flash-lite` |
| APIs | Google Gemini API |
| Services | Vercel (hosting only) |
| Local OCR | none |
| AI coding tools | Claude Code (Claude) |
