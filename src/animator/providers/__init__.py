"""Provider abstraction for video generation backends.

The animator pipeline talks to a :class:`VideoProvider` instead of any single
vendor API. Concrete providers wrap different backends:

* :class:`~animator.providers.gemini.GeminiVideoProvider` — Google Gemini Omni Flash (the
  original ``interactions``-based backend; selected as ``google``).
* :class:`~animator.providers.openrouter.OpenRouterVideoProvider` — OpenRouter's asynchronous
  ``/api/v1/videos`` endpoint (e.g. ``alibaba/wan-3.0``).
* :class:`~animator.providers.minimax.MiniMaxVideoProvider` — the MiniMax API directly (``MiniMax-H3``).

A :class:`VideoRequest` normalises the pipeline's inputs (prompt text, character
and background reference images, optional continuity opening/closing frames,
duration, resolution and aspect ratio) into a backend-agnostic summary. Each
provider is responsible for encoding those inputs in whatever wire format its
API expects.
"""

from __future__ import annotations

from animator.providers.base import ReferenceImage, VideoProvider, VideoRequest
from animator.providers.factory import create_video_provider
from animator.providers.gemini import GeminiVideoProvider
from animator.providers.minimax import MiniMaxVideoProvider
from animator.providers.openrouter import (
    OPENROUTER_MODELS_SUPPORTING_LAST_FRAME,
    OpenRouterVideoProvider,
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
