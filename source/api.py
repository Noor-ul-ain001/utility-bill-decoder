"""FastAPI backend for the demo UI. A thin layer over pipeline.py: no extraction or
answering logic lives here.

Run:  uvicorn api:app --reload --port 8000   (from the source/ folder)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import answerer
import calculator
import config
import extractor
import llm
import normalize
import pipeline

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SAMPLE_DIRS: dict[str, Path] = {"train": config.DEFAULT_TRAIN_BILLS, "test": config.DEFAULT_TEST_BILLS}
CACHE_DIR = config.DEFAULT_OUTPUT / "cache"
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

app = FastAPI(title="Utility Bill Decoder API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# In-memory bill store (keyed by image SHA-256) so questions never re-extract   #
# --------------------------------------------------------------------------- #
@dataclass
class StoredBill:
    extraction: extractor.Extraction
    image: bytes
    mime_type: str

    def context(self) -> answerer.BillContext:
        e = self.extraction
        return answerer.build_context(e.level1, e.extended, e.history, self.image, self.mime_type)


_bills: dict[str, StoredBill] = {}
_bills_lock = threading.Lock()
_batch_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Request / response models                                                   #
# --------------------------------------------------------------------------- #
class AskRequest(BaseModel):
    bill_key: str = Field(min_length=8)
    question: str = Field(min_length=2, max_length=500)


class SampleRequest(BaseModel):
    name: str


class BatchRequest(BaseModel):
    bills_dir: str = "test/bills"
    csv_dir: str = "test/csv"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _extract_response(bill_key: str, extraction: extractor.Extraction) -> dict:
    ext = extraction.extended
    return {
        "bill_key": bill_key,
        "level1": extraction.level1,
        "validation": [c.as_dict() for c in extraction.checks],
        "charge_lines": normalize.normalize_lines(ext.get("charge_lines"), config.CHARGE_TYPES, "other"),
        "tax_lines": normalize.normalize_lines(ext.get("tax_lines"), config.TAX_TYPES, "other_tax"),
        "history": extraction.history,
        "usage": calculator.usage_insights(extraction.history, extraction.level1),
    }


def _extract(data: bytes, mime_type: str, bill_id: str | None) -> dict:
    """Extract (or reuse) a bill and remember it for follow-up questions."""
    key = pipeline.sha256(data)
    with _bills_lock:
        stored = _bills.get(key)
    if stored is None:
        # Reuse the CLI cache for known bills (verified by image hash), else the uploads cache.
        cache_file = CACHE_DIR / "uploads" / f"{key[:24]}.json"
        candidates = ([CACHE_DIR / f"{bill_id}.json"] if bill_id else []) + [cache_file]
        extraction = next(
            (e for c in candidates if (e := pipeline.load_cached_extraction(c, key, bill_id or ""))), None
        )
        if extraction is None:
            try:
                extraction = extractor.extract_bill(data, bill_id, mime_type)
            except llm.LLMError as exc:
                raise HTTPException(502, f"The model could not read this bill: {exc}") from exc
            pipeline.save_extraction(cache_file, key, extraction)
        stored = StoredBill(extraction, data, mime_type)
        with _bills_lock:
            _bills[key] = stored
    return _extract_response(key, stored.extraction)


def _list_samples() -> list[dict]:
    samples = []
    for dataset, folder in SAMPLE_DIRS.items():
        for path in pipeline.list_bill_images(folder):
            samples.append({"name": path.name, "dataset": dataset, "path": path})
    return samples


def _sample_path(name: str) -> Path:
    for sample in _list_samples():
        if sample["name"] == name:
            return sample["path"]
    raise HTTPException(404, f"Sample bill not found: {name}")


def _project_dir(value: str, label: str) -> Path:
    """Resolve a user-supplied folder relative to the project root, refusing paths outside it."""
    path = (config.PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(config.PROJECT_ROOT):
        raise HTTPException(400, f"{label} must be inside the project folder.")
    if not path.is_dir():
        raise HTTPException(
            400,
            f"{label} not found: {value}. Test data goes in test/bills and test/csv; "
            "use the Training preset (train/bills, train/csv) to try the batch run before then.",
        )
    return path


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    return {"model": config.MODEL_NAME, "provider": config.MODEL_PROVIDER, "api_key_set": bool(config.API_KEY)}


@app.post("/api/extract")
def extract(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    mime_type = file.content_type if file.content_type in _MIME.values() else _MIME.get(suffix)
    if mime_type is None:
        raise HTTPException(400, "Please upload a PNG or JPG image of the bill.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "The image is larger than 15 MB.")
    return _extract(data, mime_type, Path(file.filename or "").stem or None)


@app.post("/api/extract-sample")
def extract_sample(body: SampleRequest) -> dict:
    path = _sample_path(body.name)
    return _extract(path.read_bytes(), _MIME.get(path.suffix.lower(), "image/png"), path.stem)


@app.post("/api/ask")
def ask(body: AskRequest) -> dict:
    with _bills_lock:
        stored = _bills.get(body.bill_key)
    if stored is None:
        raise HTTPException(400, "Unknown bill. Please decode the bill again.")
    try:
        return {"answer": answerer.answer_single(stored.context(), body.question.strip())}
    except llm.LLMError as exc:
        raise HTTPException(502, f"The model could not answer right now: {exc}") from exc


@app.get("/api/samples")
def samples() -> list[dict]:
    return [
        {"name": s["name"], "dataset": s["dataset"], "url": f"/api/samples/{s['name']}"}
        for s in _list_samples()
    ]


@app.get("/api/samples/{name}")
def sample_image(name: str) -> FileResponse:
    path = _sample_path(name)
    return FileResponse(path, media_type=_MIME.get(path.suffix.lower()))


@app.get("/api/datasets")
def datasets() -> list[dict]:
    """Batch presets and whether their folders exist, so the UI can guide the user."""
    presets = []
    for name in ("test", "train"):
        bills, csvs = config.PROJECT_ROOT / name / "bills", config.PROJECT_ROOT / name / "csv"
        presets.append({
            "name": name,
            "bills_dir": f"{name}/bills",
            "csv_dir": f"{name}/csv",
            "bill_count": len(pipeline.list_bill_images(bills)),
            "available": bills.is_dir() and (csvs / "level1.csv").is_file(),
        })
    return presets


@app.post("/api/batch")
def batch(body: BatchRequest) -> dict:
    bills_dir = _project_dir(body.bills_dir, "Bills folder")
    csv_dir = _project_dir(body.csv_dir, "CSV folder")
    if not _batch_lock.acquire(blocking=False):
        raise HTTPException(409, "A batch run is already in progress.")
    try:
        summary = pipeline.run_batch(bills_dir, csv_dir, config.DEFAULT_OUTPUT, progress=log.info)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        _batch_lock.release()
    return summary.as_dict()


@app.get("/api/download/{level}")
def download(level: Literal["level1", "level2"]) -> FileResponse:
    path = config.DEFAULT_OUTPUT / f"{level}.csv"
    if not path.is_file():
        raise HTTPException(404, f"{level}.csv has not been generated yet. Run a batch first.")
    return FileResponse(path, media_type="text/csv", filename=f"{level}.csv")
