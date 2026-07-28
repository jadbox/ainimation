"""Character and scene-background blueprint generation pipeline."""

from __future__ import annotations


def slug(name: str) -> str:
    """Return a filesystem-safe lowercase slug for a character or scene name."""
    return name.lower().replace(" ", "-").replace(".", "").replace("'", "")
