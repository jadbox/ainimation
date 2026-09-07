"""Environment variables and model configuration constants for blueprint generation."""

from __future__ import annotations

import os

# Image model constants - Nano Banana 2 (Gemini 3.1 Flash Image Preview)
IMAGE_MODEL_NANO_BANANA_2 = "gemini-3.1-flash-image-preview"
DEFAULT_IMAGE_MODEL = IMAGE_MODEL_NANO_BANANA_2



def require_environment(name: str, alternate: str | None = None) -> str:
    """Ensure an environment variable is set."""
    value = os.environ.get(name) or (os.environ.get(alternate) if alternate else None)
    if not value:
        names = f"{name} or {alternate}" if alternate else name
        raise RuntimeError(f"Set {names} before running this command.")
    return value
