"""Gemini API provider for video generation (backward-compatibility shim).

This module re-exports components from :mod:`animator.providers.gemini`.
New code should import directly from ``animator.providers`` or ``animator.providers.gemini``.
"""

from __future__ import annotations

from animator.providers.gemini import (
    GeminiVideoProvider,
    build_gemini_input_items,
    create_video_interaction,
    extract_video_bytes,
    wait_for_completion,
)

__all__ = [
    "GeminiVideoProvider",
    "build_gemini_input_items",
    "create_video_interaction",
    "extract_video_bytes",
    "wait_for_completion",
]
