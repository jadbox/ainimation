"""Configuration defaults and model resolution for :mod:`scriptgen`."""

from __future__ import annotations

# OpenRouter models are identified by a vendor/name slug (e.g. "google/gemini-3.8-flash").
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
# Shortcut: "--model gemini" maps to Google's flagship Gemini model on OpenRouter.
GEMINI_OPENROUTER_MODEL = "google/gemini-3.8-flash"
GEMINI_DIRECT_MODEL = "gemini-3.8-flash"
DEFAULT_MODEL = "google/gemini-3.8-flash"

# Reasoning effort passed to OpenRouter for reasoning-capable models (the
# default model).
REASONING_EFFORT = "high"

MAX_SCRIPT_CHARS = 1600
MAX_SCRIPT_PROMPT_CHARS = 800
MAX_RETRIES = 3

DEFAULT_PARTS = 3
MIN_PARTS = 1
MAX_PARTS = 10


def segment_span(index: int) -> str:
    """Return the 10-second story-time span for a zero-indexed scene part."""
    start = index * 10
    end = start + 10
    return f"{start // 60}:{start % 60:02d}-{end // 60}:{end % 60:02d}"


def resolve_openrouter_model(model: str) -> str:
    """Resolve the ``gemini`` shortcut to its OpenRouter model slug.

    Every OpenRouter model name is a ``vendor/name`` slug containing ``/``.
    Raises for anything that is neither a recognized shortcut nor a valid
    OpenRouter slug.
    """
    if model in ("gemini", "gemini-flash", "gemini-3.8", "gemini-3.8-flash"):
        return GEMINI_OPENROUTER_MODEL
    if model == "gemini-direct":
        return GEMINI_DIRECT_MODEL
    if "/" not in model:
        raise ValueError(
            f"Unknown model {model!r}. Pass an OpenRouter model slug like "
            f"{DEFAULT_MODEL!r} or the shortcut 'gemini' ({GEMINI_OPENROUTER_MODEL})."
        )
    return model
