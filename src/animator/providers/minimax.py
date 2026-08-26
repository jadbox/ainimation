"""MiniMax video generation provider."""

from __future__ import annotations

import atexit
import logging
import os
import signal
import time
from typing import Any

import requests

from animator.config import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_MINIMAX_RESOLUTION,
    DEFAULT_MINIMAX_VIDEO_MODEL,
    POLL_INTERVAL_SECONDS,
)
from animator.providers.base import ReferenceImage, VideoProvider, VideoRequest

logger = logging.getLogger("animator.providers.minimax")


class MiniMaxVideoProvider(VideoProvider):
    """Generate video directly via the MiniMax API (MiniMax H3).

    Uses ``POST /v2/video_generation`` to submit an asynchronous task, polls
    ``GET /v2/query/video_generation/{task_id}`` until it succeeds, then
    downloads the finished MP4 from the returned ``content.url``.

    Multimodal inputs are provided as content items:
    * Character and background blueprint references are sent with ``role=reference_image``.
    * Continuity frames are sent with ``role=first_frame`` (opening continuity)
      and/or ``role=last_frame`` (closing continuity).
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
        if request.continuity_frame is not None:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": request.continuity_frame.data_uri()},
                    "role": "reference_image",
                }
            )
        if request.closing_frame is not None:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": request.closing_frame.data_uri()},
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
        if request.character_references:
            modes.append("character-ref")
        if request.background_reference is not None:
            modes.append("bg-ref")
        if request.continuity_frame is not None:
            modes.append("continuity-ref")
        if request.closing_frame is not None:
            modes.append("closing-ref")
        in_mode = "+".join(modes) if modes else "text-only"
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
