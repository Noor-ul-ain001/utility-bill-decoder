# Utility Bill Decoder

AI assistant that reads Pakistani electricity bills (K-Electric, LESCO, IESCO), extracts every billing
field as JSON and answers customer questions in plain English. Built for the WTQ Build Track.

- `source/`: Python pipeline + CLI, FastAPI backend and React UI. **Full documentation: [source/README.md](source/README.md)**
- `output/`: generated `level1.csv` (extraction) and `level2.csv` (answers) for the test bills
- `make_zip.py`: builds and verifies the submission ZIP

Model: Google Gemini (`gemini-3.5-flash-lite`) via the official `google-genai` SDK.
