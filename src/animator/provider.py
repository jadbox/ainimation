"""Provider abstraction for video generation backends (backward-compatibility shim).

This module re-exports components from the modular :mod:`animator.providers` package.
New code should import directly from ``animator.providers`` (or its submodules).
"""

from __future__ import annotations

from animator.providers import (
    GeminiVideoProvider,
    MiniMaxVideoProvider,
    OPENROUTER_MODELS_SUPPORTING_LAST_FRAME,
    OpenRouterVideoProvider,
    ReferenceImage,
    VideoProvider,
    VideoRequest,
    create_video_provider,
)

__all__ = [
    "GeminiVideoProvider",
    "MiniMaxVideoProvider",
    "OPENROUTER_MODELS_SUPPORTING_LAST_FRAME",
    "OpenRouterVideoProvider",
    "ReferenceImage",
    "VideoProvider",
    "VideoRequest",
    "create_video_provider",
]
