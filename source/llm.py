"""Thin wrapper around the official ``google-genai`` SDK.

Responsibilities:
* one shared client per process,
* a process-wide rate limiter (free tier allows 15 requests/minute),
* exponential-backoff retries on 429 and 5xx errors,
* JSON-mode calls that accept bill images and an optional response schema.

Every LLM call in the project goes through :func:`generate_json`.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import random
import threading
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

import config

log = logging.getLogger(__name__)

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """Raised when the model cannot produce a usable response."""


class RateLimiter:
    """Enforce a minimum interval between consecutive calls (thread-safe)."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            delay = self._last_call + self._min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last_call = time.monotonic()


_rate_limiter = RateLimiter(config.MIN_SECONDS_BETWEEN_CALLS)
_client: genai.Client | None = None
_client_lock = threading.Lock()


def get_client() -> genai.Client:
    """Return the shared Gemini client, creating it on first use."""
    global _client
    config.check_provider()
    if not config.API_KEY:
        raise LLMError("API_KEY is not set. Copy .env.example to .env and add your Gemini key.")
    with _client_lock:
        if _client is None:
            _client = genai.Client(
                api_key=config.API_KEY,
                http_options=types.HttpOptions(timeout=config.REQUEST_TIMEOUT_SECONDS * 1000),
            )
    return _client


def image_part(image: Path | bytes, mime_type: str | None = None) -> types.Part:
    """Build an inline image part from a file path or raw bytes."""
    if isinstance(image, Path):
        mime_type = mime_type or mimetypes.guess_type(image.name)[0] or "image/png"
        data = image.read_bytes()
    else:
        data = image
        mime_type = mime_type or "image/png"
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "code", None)
    if isinstance(status, int):  # google.genai APIError carries the HTTP status as .code
        return status in _RETRYABLE_STATUS
    # Network-level hiccups (timeouts, dropped connections) are worth retrying too.
    return isinstance(exc, (TimeoutError, ConnectionError)) or "timeout" in type(exc).__name__.lower()


def _parse_json(text: str) -> Any:
    """Parse model output, tolerating stray markdown fences and reasoning blocks."""
    cleaned = text.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[1].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("\n") + 1:] if "\n" in cleaned else cleaned
    return json.loads(cleaned)


def _gemini_caller(
    prompt: str,
    images: list[types.Part] | None,
    system: str | None,
    schema: Any | None,
    temperature: float,
):
    """Return a zero-argument function that performs one Gemini request and returns its text."""
    contents: list[Any] = [*(images or []), prompt]
    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        system_instruction=system,
        temperature=temperature,
        # Bills are dense with small print; high resolution reads digits more reliably.
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH if images else None,
    )

    def call() -> str:
        response = get_client().models.generate_content(
            model=config.MODEL_NAME, contents=contents, config=gen_config
        )
        return response.text or ""

    return call


def generate_json(
    prompt: str,
    *,
    images: list[types.Part] | None = None,
    system: str | None = None,
    schema: Any | None = None,
    temperature: float = 0.0,
) -> Any:
    """Call the configured model (Gemini) in JSON mode and return the parsed object.

    Args:
        prompt: User prompt text (placed after any images).
        images: Image parts created with :func:`image_part`.
        system: Optional system instruction.
        schema: Optional response schema (Pydantic model or dict) for structured output.
        temperature: Sampling temperature; 0 keeps extraction deterministic.

    Raises:
        LLMError: if all retries fail or the response is not valid JSON.
    """
    config.check_provider()
    if not config.API_KEY:
        raise LLMError("API_KEY is not set. Copy .env.example to .env and add your API key.")

    call = _gemini_caller(prompt, images, system, schema, temperature)

    last_error: Exception | None = None
    for attempt in range(config.MAX_RETRIES + 1):
        _rate_limiter.wait()
        try:
            text = call()
            if not text.strip():
                raise LLMError("Model returned an empty response.")
            return _parse_json(text)
        except (json.JSONDecodeError, LLMError) as exc:
            # Malformed output: one more try usually fixes it, but do not loop forever.
            last_error = exc
            log.warning("Unusable model output (attempt %d): %s", attempt + 1, exc)
            if attempt >= 1:
                break
        except Exception as exc:  # noqa: BLE001 - SDK raises several error types
            last_error = exc
            if not _is_retryable(exc) or attempt == config.MAX_RETRIES:
                break
            delay = min(config.BACKOFF_BASE_SECONDS * 2**attempt, config.BACKOFF_MAX_SECONDS)
            delay += random.uniform(0, 1)
            log.warning("%s call failed (%s); retrying in %.1fs", config.MODEL_PROVIDER, exc, delay)
            time.sleep(delay)

    raise LLMError(f"{config.MODEL_PROVIDER} request failed: {last_error}") from last_error


def ping() -> str:
    """Make one tiny call to confirm the API key and model work."""
    result = generate_json('Reply with the JSON object {"status": "ok"}.')
    return str(result.get("status", result)) if isinstance(result, dict) else str(result)
