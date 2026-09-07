"""Data models for blueprint generation subjects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Subject:
    """One blueprint image to generate: a character sheet or a scene background plate."""

    label: str
    """Human-readable subject label for logs, e.g. ``scene 'X' background 'y'``."""

    display_name: str
    """Title used in iterations.md."""

    output_dir: Path
    style_slug: str
    initial_prompt: str

