"""Animate scene scripts into 720p clips via a pluggable video provider."""

from __future__ import annotations

from animator.cli import main, run
from animator.models import SceneSegment

__all__ = ["SceneSegment", "main", "run"]
