"""Generate production-ready per-segment scene design files from story beats.

Expands an abridged story scene from ``movie.yml``'s ``story:`` section into a
full scene design document via an OpenRouter text model, then splits it into
self-contained per-segment prompt files (``out/scripts/<name>_part<N>.md``).
"""

from __future__ import annotations

from scriptgen.cli import main, run
from scriptgen.config import (
    DEFAULT_MODEL,
    DEFAULT_SCRIPTS_DIR,
    GEMINI_OPENROUTER_MODEL,
    MAX_RETRIES,
    MAX_SCRIPT_CHARS,
    SEGMENT_SPANS,
    resolve_openrouter_model,
)
from scriptgen.format import format_segment_base_prompt

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_SCRIPTS_DIR",
    "GEMINI_OPENROUTER_MODEL",
    "MAX_RETRIES",
    "MAX_SCRIPT_CHARS",
    "SEGMENT_SPANS",
    "format_segment_base_prompt",
    "main",
    "resolve_openrouter_model",
    "run",
]