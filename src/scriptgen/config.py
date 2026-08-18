"""Configuration defaults and model resolution for :mod:`scriptgen`."""

from __future__ import annotations

# OpenRouter models are identified by a vendor/name slug (e.g. "google/gemini-3.7-flash").
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
# Shortcut: "--model gemini" maps to Google's flagship Gemini model on OpenRouter.
GEMINI_OPENROUTER_MODEL = "google/gemini-3.7-flash"
DEFAULT_MODEL = "google/gemini-3.7-flash"

# Reasoning effort passed to OpenRouter for reasoning-capable models (the
# default model).
REASONING_EFFORT = "high"

# Budget model (measured in characters):
# MiniMax H3 prompt guidelines (base-en.txt & ref-en.txt) require lean, dense prompts.
# Total prompt sent to the video generator (static header + segment body + animator reference tags)
# must remain strictly under 1,700 characters.
#   1,700  absolute maximum total prompt for the video generator
#    -350  safety margin reserved for animator reference tags (<IMAGE_REF_N> & alignment header)
#  ------
#   1,350  hard cap for each saved part file — anything over is rejected
MAX_SCRIPT_CHARS = 1350
# Target segment-body budget (~600-650 chars) so that
# header (~300-350 chars) + body easily fits within MAX_SCRIPT_CHARS (1,350 chars).
MAX_SCRIPT_PROMPT_CHARS = 650
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
    if model == "gemini":
        return GEMINI_OPENROUTER_MODEL
    if "/" not in model:
        raise ValueError(
            f"Unknown model {model!r}. Pass an OpenRouter model slug like "
            f"{DEFAULT_MODEL!r} or the shortcut 'gemini' ({GEMINI_OPENROUTER_MODEL})."
        )
    return model
