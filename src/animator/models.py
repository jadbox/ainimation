"""Data models for animator segments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSegment:
    """One 10-second segment of a scene script."""

    index: int
    span: str
    """The time span written in the header, e.g. ``0:10-0:20`` (may be empty)."""
    body: str
