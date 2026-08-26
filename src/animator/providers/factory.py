"""Factory function to instantiate video generation providers."""

from __future__ import annotations

from animator.config import (
    DEFAULT_MINIMAX_RESOLUTION,
    DEFAULT_OPENROUTER_RESOLUTION,
    DEFAULT_VIDEO_PROVIDER,
    VIDEO_PROVIDERS,
)
from animator.providers.base import VideoProvider


def create_video_provider(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    resolution: str | None = None,
) -> VideoProvider:
    """Instantiate a video provider by name.

    ``provider`` is one of :data:`VIDEO_PROVIDERS` (default: the MiniMax
    backend, MiniMax H3 at 768P). ``model`` and ``api_key`` are optional
    and fall back to each provider's configured defaults.
    """
    name = (provider or DEFAULT_VIDEO_PROVIDER).lower()
    if name == "openrouter":
        from animator.providers.openrouter import OpenRouterVideoProvider

        return OpenRouterVideoProvider(
            model=model,
            api_key=api_key,
            resolution=resolution or DEFAULT_OPENROUTER_RESOLUTION,
        )
    if name == "minimax":
        from animator.providers.minimax import MiniMaxVideoProvider

        return MiniMaxVideoProvider(
            model=model,
            api_key=api_key,
            resolution=resolution or DEFAULT_MINIMAX_RESOLUTION,
        )
    if name in ("google", "gemini"):
        from animator.providers.gemini import GeminiVideoProvider

        return GeminiVideoProvider(model=model, api_key=api_key)
    valid = ", ".join(VIDEO_PROVIDERS)
    raise ValueError(f"Unknown video provider {name!r}. Expected one of: {valid}.")
