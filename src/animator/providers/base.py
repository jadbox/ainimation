"""Unified base interface and data models for video generation providers."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from animator.config import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_RESOLUTION,
)


@dataclass(frozen=True)
class ReferenceImage:
    """An encoded reference image sent along with a video prompt."""

    label: str
    """Human-readable description of what this image depicts."""

    data: bytes
    """Raw image bytes (e.g. JPEG)."""

    mime_type: str = "image/jpeg"

    def data_uri(self) -> str:
        """Return the image as a base64 data URI for REST-style image_url inputs."""
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime_type};base64,{encoded}"


@dataclass(frozen=True)
class VideoRequest:
    """Backend-agnostic description of a single video generation request."""

    prompt: str
    """The direction/prompt text sent to the model."""

    character_references: tuple[ReferenceImage, ...] = ()
    """Character blueprint reference images (style guidance)."""

    background_reference: ReferenceImage | None = None
    """Optional production background plate for the scene set."""

    continuity_frame: ReferenceImage | None = None
    """Optional mandatory opening frame (last frame of the previous segment)."""

    closing_frame: ReferenceImage | None = None
    """Optional mandatory closing frame (first frame of the next segment)."""

    duration: int = DEFAULT_DURATION_SECONDS
    """Requested clip length in seconds."""

    resolution: str = DEFAULT_RESOLUTION
    """Requested output resolution (e.g. '720p', '768p')."""

    aspect_ratio: str = DEFAULT_ASPECT_RATIO
    """Requested output aspect ratio (e.g. '16:9')."""

    temperature: float | None = None
    """Sampling temperature, where the backend supports it."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Backend-specific passthrough options."""


class VideoProvider(ABC):
    """Common interface every video backend provider implements."""

    name: str

    @abstractmethod
    def generate(self, request: VideoRequest, timeout: int) -> bytes:
        """Submit the request, wait for completion, and return the video bytes.

        Raises ``RuntimeError`` on failure or timeout.
        """
