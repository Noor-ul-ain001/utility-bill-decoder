"""Central configuration: environment loading and project-wide constants.

All settings come from environment variables (optionally loaded from a ``.env``
file next to this module), so the same code runs from the CLI and the API.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SOURCE_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = SOURCE_DIR.parent

# Prefer source/.env, then fall back to a .env in the current working directory.
load_dotenv(SOURCE_DIR / ".env")
load_dotenv()

# --- Model configuration (only Google Gemini is allowed) ---------------------
MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "google").strip().lower()
MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite").strip()
API_KEY: str = os.getenv("API_KEY", "").strip()

# --- Rate limiting / retries (free tier: 15 requests per minute) -------------
MIN_SECONDS_BETWEEN_CALLS: float = float(os.getenv("MIN_SECONDS_BETWEEN_CALLS", "4.5"))
MAX_RETRIES: int = 4
BACKOFF_BASE_SECONDS: float = 5.0
BACKOFF_MAX_SECONDS: float = 60.0
REQUEST_TIMEOUT_SECONDS: int = 180
# Send the bill image along with Level 2 questions (more grounded answers, more input tokens).
ANSWER_WITH_IMAGE: bool = os.getenv("ANSWER_WITH_IMAGE", "true").strip().lower() not in {"0", "false", "no"}

# --- Data locations ----------------------------------------------------------
DEFAULT_TRAIN_BILLS: Path = PROJECT_ROOT / "train" / "bills"
DEFAULT_TEST_BILLS: Path = PROJECT_ROOT / "test" / "bills"
DEFAULT_TEST_CSV: Path = PROJECT_ROOT / "test" / "csv"
DEFAULT_OUTPUT: Path = PROJECT_ROOT / "output"
IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg")

# --- Domain constants (GUIDE sections 5.1 / 5.4) -----------------------------
PROVIDERS: tuple[str, ...] = ("KE", "LESCO", "IESCO")
CHARGE_TYPES: tuple[str, ...] = (
    "energy", "fixed", "fpa", "quarterly_adjustment",
    "surcharge", "meter_rent", "subsidy", "other",
)
TAX_TYPES: tuple[str, ...] = (
    "gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax",
)
FALLBACK_ANSWER: str = "The bill does not show enough information to answer this."


# Only Google Gemini is used (an allowed model under the competition rules).
SUPPORTED_PROVIDERS: tuple[str, ...] = ("google",)


def check_provider() -> None:
    """Fail fast if the configured provider is not supported."""
    if MODEL_PROVIDER not in SUPPORTED_PROVIDERS:
        raise RuntimeError(
            f"MODEL_PROVIDER={MODEL_PROVIDER!r} is not supported; use 'google' (Gemini)."
        )
