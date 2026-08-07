"""Configuration defaults and model resolution for :mod:`scriptgen`."""

from __future__ import annotations

# OpenRouter models are identified by a vendor/name slug (e.g. "qwen/qwen3.8-max").
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
# Shortcut: "--model gemini" maps to Google's flagship Gemini model on OpenRouter.
GEMINI_OPENROUTER_MODEL = "google/gemini-3.6-flash"
DEFAULT_MODEL = "qwen/qwen3.8-max"

# Reasoning effort passed to OpenRouter for reasoning-capable models (the
# default model). Reduces excessive "thinking" time while keeping quality.
REASONING_EFFORT = "medium"

# A saved segment document (static template + generated segment body) must never
# exceed this many characters; otherwise generation retries with a reduction
# instruction. This keeps each prompt well under the video model input limits.
MAX_SCRIPT_CHARS = 6000
# The character limit the model is *told* to hit. Kept below MAX_SCRIPT_CHARS
# because LLMs tend to overshoot, so asking for 5000 reliably lands under the
# real 6000 budget.
MAX_SCRIPT_PROMPT_CHARS = MAX_SCRIPT_CHARS - 2000
MAX_RETRIES = 3

# Known 10-second segment time spans, indexed by part number.
SEGMENT_SPANS = {0: "0:00-0:10", 1: "0:10-0:20", 2: "0:20-0:30"}


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