"""Generator and provider abstraction for video generation backends.

Re-exports provider implementations and factory functions.
"""

from __future__ import annotations

from animator.provider import *  # noqa: F401, F403
from animator.providers import (
    FalVideoProvider,
    GeminiVideoProvider,
    MiniMaxVideoProvider,
    OpenRouterVideoProvider,
    ReferenceImage,
    VideoProvider,
    VideoRequest,
    create_video_provider,
)

__all__ = [
    "FalVideoProvider",
    "GeminiVideoProvider",
    "MiniMaxVideoProvider",
    "OpenRouterVideoProvider",
    "ReferenceImage",
    "VideoProvider",
    "VideoRequest",
    "create_video_provider",
]
