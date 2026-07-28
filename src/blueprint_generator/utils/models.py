"""Data models for blueprint generation attempts and subjects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Attempt:
    """Record of a single generation/review attempt."""

    number: int
    score: int | None
    accepted: bool
    learning: str
    feedback: str
    prompt_change: str
    prompt_used: str = ""


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
    review_instruction: str
