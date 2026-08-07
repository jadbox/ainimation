"""Provider abstraction for video generation backends.

The animator pipeline talks to a :class:`VideoProvider` instead of any single
vendor API. Concrete providers wrap different backends:

* :class:`~animator.api.GeminiVideoProvider` — Google Gemini Omni Flash (the
  original ``interactions``-based backend; selected as ``google``).
* :class:`OpenRouterVideoProvider` — OpenRouter's asynchronous ``/api/v1/videos``
  endpoint (e.g. ``minimax/hailuo-3``).
* :class:`MiniMaxVideoProvider` — the MiniMax API directly (``MiniMax-H3``).

A :class:`VideoRequest` normalises the pipeline's inputs (prompt text, character
and background reference images, optional continuity opening/closing frames,
duration, resolution and aspect ratio) into a backend-agnostic summary. Each
provider is responsible for encoding those inputs in whatever wire format its
API expects.
"""

from __future__ import annotations

import atexit
import base64
import logging
import os
import signal
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests

from animator.config import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_MINIMAX_RESOLUTION,
    DEFAULT_MINIMAX_VIDEO_MODEL,
    DEFAULT_OPENROUTER_RESOLUTION,
    DEFAULT_OPENROUTER_VIDEO_MODEL,
    DEFAULT_RESOLUTION,
    DEFAULT_VIDEO_PROVIDER,
    POLL_INTERVAL_SECONDS,
    VIDEO_PROVIDERS,
)

logger = logging.getLogger("animator.provider")


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


class OpenRouterVideoProvider(VideoProvider):
    """Generate video via OpenRouter's asynchronous videos API.

    Uses ``POST /api/v1/videos`` to submit a job, polls the returned polling URL
    until completion, then downloads the finished MP4. Character and background
    references are sent as ``input_references``; a continuity frame is sent as a
    ``first_frame`` image for exact frame-0 continuity and a closing frame as a
    ``last_frame`` image for exact final-frame continuity. MiniMax H3
    (``minimax/hailuo-3``) is the default model at 768p.
    """

    name = "openrouter"

    VIDEOS_URL = "https://openrouter.ai/api/v1/videos"
    TERMINAL_FAILED = {"failed", "cancelled", "expired"}

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        resolution: str = DEFAULT_OPENROUTER_RESOLUTION,
    ) -> None:
        self.model = model or DEFAULT_OPENROUTER_VIDEO_MODEL
        self.resolution = resolution
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Set OPENROUTER_API_KEY before using the OpenRouter video provider."
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, request: VideoRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": request.prompt,
            "duration": request.duration,
            "resolution": self.resolution,
            "aspect_ratio": request.aspect_ratio,
        }

        input_refs: list[dict[str, Any]] = []
        for ref in request.character_references:
            input_refs.append(
                {"type": "image_url", "image_url": {"url": ref.data_uri()}}
            )
        if request.background_reference is not None:
            input_refs.append(
                {
                    "type": "image_url",
                    "image_url": {"url": request.background_reference.data_uri()},
                }
            )
        if input_refs:
            payload["input_references"] = input_refs

        frame_images: list[dict[str, Any]] = []
        if request.continuity_frame is not None:
            frame_images.append(
                {
                    "type": "image_url",
                    "image_url": {"url": request.continuity_frame.data_uri()},
                    "frame_type": "first_frame",
                }
            )
        if request.closing_frame is not None:
            frame_images.append(
                {
                    "type": "image_url",
                    "image_url": {"url": request.closing_frame.data_uri()},
                    "frame_type": "last_frame",
                }
            )
        if frame_images:
            payload["frame_images"] = frame_images

        payload.update(request.extra)
        return payload

    def generate(self, request: VideoRequest, timeout: int) -> bytes:
        headers = self._headers()
        payload = self._build_payload(request)

        logger.info(
            "Submitting OpenRouter video request to model=%s (resolution=%s, "
            "duration=%ss, aspect=%s) ...",
            self.model,
            self.resolution,
            request.duration,
            request.aspect_ratio,
        )
        total_start = time.monotonic()
        t0 = time.monotonic()
        response = requests.post(
            self.VIDEOS_URL, headers=headers, json=payload, timeout=120
        )
        if response.status_code not in (200, 202):
            raise RuntimeError(
                f"OpenRouter video submission failed ({response.status_code}): "
                f"{response.text[:500]}"
            )
        job = response.json()
        job_id = job.get("id")
        polling_url = job.get("polling_url")
        logger.info(
            "Video job submitted in %.1fs (job id: %s, status: %s)",
            time.monotonic() - t0,
            job_id,
            job.get("status"),
        )
        if not polling_url:
            raise RuntimeError(
                f"OpenRouter returned a video job without a polling URL: {job}"
            )

        completed = self._poll(polling_url, headers, timeout)
        urls = completed.get("unsigned_urls") or []
        if not urls:
            raise RuntimeError("OpenRouter returned no downloadable video URLs.")
        content = self._download(urls[0], timeout)
        logger.info("Downloaded %d bytes of generated video.", len(content))
        logger.info(
            "OpenRouter video generation completed in %.1fs.",
            time.monotonic() - total_start,
        )
        return content

    def _poll(self, polling_url: str, headers: dict[str, str], timeout: int) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"OpenRouter video generation did not finish within {timeout}s "
                    f"({polling_url})."
                )
            response = requests.get(polling_url, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            logger.info("OpenRouter video status: %s", status)
            if status == "completed":
                return data
            if status in self.TERMINAL_FAILED:
                raise RuntimeError(
                    f"OpenRouter video generation ended with status {status!r}: "
                    f"{data.get('error', 'unknown error')}"
                )
            time.sleep(POLL_INTERVAL_SECONDS)

    def _download(self, content_url: str, timeout: int) -> bytes:
        response = requests.get(content_url, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(
                f"Could not download generated video ({response.status_code})."
            )
        return response.content


class MiniMaxVideoProvider(VideoProvider):
    """Generate video directly via the MiniMax API (MiniMax H3).

    Uses ``POST /v2/video_generation`` to submit an asynchronous task, polls
    ``GET /v2/query/video_generation/{task_id}`` until it succeeds, then
    downloads the finished MP4 from the returned ``content.url``.

    MiniMax distinguishes two mutually exclusive input modes:
    * **Reference mode** — character and background blueprints are sent as
      ``reference_image`` entries (used when no continuity frames exist).
    * **Frame mode** — a continuity frame is sent with ``role=first_frame``
      and/or a closing frame with ``role=last_frame`` so frame 0 (and/or the
      final frame) is the exact neighboring shot's frame. Because MiniMax
      forbids mixing ``reference_image`` with ``first_frame``/``last_frame``,
      the character references are omitted here — the locked frames already
      pin down the character designs and background.
    """

    name = "minimax"

    BASE_URL = "https://api.minimax.io"
    CREATE_URL = f"{BASE_URL}/v2/video_generation"
    QUERY_URL = f"{BASE_URL}/v2/query/video_generation"
    DELETE_URL = f"{BASE_URL}/v2/video_generation"
    TERMINAL_FAILED = {"failed", "cancelled"}

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        resolution: str = DEFAULT_MINIMAX_RESOLUTION,
    ) -> None:
        self.model = model or DEFAULT_MINIMAX_VIDEO_MODEL
        self.resolution = resolution
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Set MINIMAX_API_KEY before using the MiniMax video provider."
            )
        self._active_tasks: set[str] = set()
        self._shutdown_registered = False
        self._original_handlers: dict[int, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _register_shutdown_handlers(self) -> None:
        """Install one-time signal/atexit handlers that cancel queued jobs on exit."""
        if self._shutdown_registered:
            return
        self._shutdown_registered = True
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
            try:
                self._original_handlers[signum] = signal.getsignal(signum)
            except (ValueError, OSError):
                continue
            signal.signal(signum, self._handle_shutdown)
        atexit.register(self._cancel_active_tasks)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        logger.warning(
            "Received signal %s while MiniMax jobs may be in queue; cancelling "
            "in-flight task(s)...",
            signum,
        )
        self._cancel_active_tasks()
        original = self._original_handlers.get(signum, signal.SIG_DFL)
        signal.signal(signum, original)
        raise KeyboardInterrupt

    def cancel(self, task_id: str, reason: str = "program exited") -> None:
        """Cancel a queued MiniMax task (or delete its record if already finished).

        Hits ``DELETE /v2/video_generation/{task_id}``. MiniMax only cancels
        tasks whose status is ``queued``; jobs already running or finished are
        left alone. Errors are logged and swallowed so a best-effort cancel
        never masks the original failure.
        """
        url = f"{self.DELETE_URL}/{task_id}"
        try:
            response = requests.delete(url, headers=self._headers(), timeout=120)
        except requests.RequestException as error:
            logger.warning(
                "Failed to cancel MiniMax task %s (%s): %s", task_id, reason, error
            )
            return
        if response.status_code != 200:
            logger.warning(
                "MiniMax cancel request for task %s (%s) returned %s: %s",
                task_id,
                reason,
                response.status_code,
                response.text[:300],
            )
            return
        data = response.json()
        logger.info(
            "MiniMax task %s %s (%s)",
            task_id,
            data.get("action") or data.get("status") or "cancelled",
            reason,
        )

    def _cancel_active_tasks(self) -> None:
        """Cancel every MiniMax task currently tracked as active by this provider."""
        while self._active_tasks:
            task_id = self._active_tasks.pop()
            self.cancel(task_id, reason="program exit")

    def _build_payload(self, request: VideoRequest) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": request.prompt}
        ]

        if request.continuity_frame is not None or request.closing_frame is not None:
            if request.continuity_frame is not None:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": request.continuity_frame.data_uri()},
                        "role": "first_frame",
                    }
                )
            if request.closing_frame is not None:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": request.closing_frame.data_uri()},
                        "role": "last_frame",
                    }
                )
        else:
            for ref in request.character_references:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": ref.data_uri()},
                        "role": "reference_image",
                    }
                )
            if request.background_reference is not None:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": request.background_reference.data_uri()},
                        "role": "reference_image",
                    }
                )

        has_images = bool(
            request.continuity_frame is not None
            or request.closing_frame is not None
            or request.character_references
            or request.background_reference is not None
        )
        ratio = request.aspect_ratio
        if not has_images and (not ratio or ratio == "adaptive"):
            # MiniMax requires a concrete ratio (never 'adaptive') for
            # text-to-video, where no image input determines the framing.
            ratio = DEFAULT_ASPECT_RATIO

        payload: dict[str, Any] = {
            "model": self.model,
            "content": content,
            "duration": request.duration,
            "resolution": self.resolution,
            "ratio": ratio,
        }
        payload.update(request.extra)
        return payload

    def generate(self, request: VideoRequest, timeout: int) -> bytes:
        self._register_shutdown_handlers()
        headers = self._headers()
        payload = self._build_payload(request)

        modes: list[str] = []
        if request.continuity_frame is not None:
            modes.append("first-frame")
        if request.closing_frame is not None:
            modes.append("last-frame")
        in_mode = "+".join(modes) if modes else "reference"
        logger.info(
            "Submitting MiniMax video request (model=%s, mode=%s, resolution=%s, "
            "duration=%ss, ratio=%s) ...",
            self.model,
            in_mode,
            self.resolution,
            request.duration,
            request.aspect_ratio,
        )
        total_start = time.monotonic()
        t0 = time.monotonic()
        response = requests.post(
            self.CREATE_URL, headers=headers, json=payload, timeout=120
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"MiniMax video submission failed ({response.status_code}): "
                f"{response.text[:500]}"
            )
        data = response.json()
        task_id = data.get("task_id")
        logger.info(
            "MiniMax video task submitted in %.1fs (task id: %s)",
            time.monotonic() - t0,
            task_id,
        )
        if not task_id:
            raise RuntimeError(f"MiniMax returned a video task without a task id: {data}")

        self._active_tasks.add(task_id)
        try:
            content_url = self._poll(task_id, headers, timeout)
            if not content_url:
                raise RuntimeError("MiniMax returned no downloadable video URL.")
            content = self._download(content_url, timeout)
        finally:
            self._active_tasks.discard(task_id)
        logger.info("Downloaded %d bytes of generated video.", len(content))
        logger.info(
            "MiniMax video generation completed in %.1fs.",
            time.monotonic() - total_start,
        )
        return content

    def _poll(self, task_id: str, headers: dict[str, str], timeout: int) -> str:
        query_url = f"{self.QUERY_URL}/{task_id}"
        deadline = time.monotonic() + timeout
        first = True
        status_times: dict[str, float] = {"queued": 0.0, "running": 0.0}
        phase_start = time.monotonic()
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"MiniMax video generation did not finish within {timeout}s "
                    f"({query_url})."
                )
            if not first:
                time.sleep(POLL_INTERVAL_SECONDS)
            first = False
            response = requests.get(query_url, headers=headers, timeout=120)
            response.raise_for_status()
            task = response.json().get("task") or {}
            status = task.get("status")
            now = time.monotonic()
            logger.info(
                "MiniMax video status: %s (queued %.1fs, running %.1fs)",
                status,
                status_times["queued"],
                status_times["running"],
            )
            if status == "succeeded":
                return (task.get("content") or {}).get("url") or ""
            if status in self.TERMINAL_FAILED:
                raise RuntimeError(
                    f"MiniMax video generation ended with status {status!r}: "
                    f"{task.get('error', 'unknown error')}"
                )
            if status in status_times:
                status_times[status] += now - phase_start
            phase_start = now

    def _download(self, content_url: str, timeout: int) -> bytes:
        response = requests.get(content_url, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(
                f"Could not download generated video ({response.status_code})."
            )
        return response.content


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
        return OpenRouterVideoProvider(
            model=model,
            api_key=api_key,
            resolution=resolution or DEFAULT_OPENROUTER_RESOLUTION,
        )
    if name == "minimax":
        return MiniMaxVideoProvider(
            model=model,
            api_key=api_key,
            resolution=resolution or DEFAULT_MINIMAX_RESOLUTION,
        )
    if name in ("google", "gemini"):
        from animator.api import GeminiVideoProvider

        return GeminiVideoProvider(model=model, api_key=api_key)
    valid = ", ".join(VIDEO_PROVIDERS)
    raise ValueError(f"Unknown video provider {name!r}. Expected one of: {valid}.")
