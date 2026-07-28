"""Environment variables and model configuration constants for blueprint generation."""

from __future__ import annotations

import os

# Review model constants
REVIEW_MODEL_GEMINI_FLASH_3_6 = "gemini-3.6-flash"
REVIEW_MODEL_KIMI_K3 = "moonshotai/kimi-k3"

# Static configuration variables
REVIEW_MODEL = REVIEW_MODEL_GEMINI_FLASH_3_6 # REVIEW_MODEL_KIMI_K3
MAX_ITERATIONS = 4

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_REVIEW_MODEL = REVIEW_MODEL


def require_environment(name: str, alternate: str | None = None) -> str:
    """Ensure an environment variable is set."""
    value = os.environ.get(name) or (os.environ.get(alternate) if alternate else None)
    if not value:
        names = f"{name} or {alternate}" if alternate else name
        raise RuntimeError(f"Set {names} before running this command.")
    return value
