"""Fal.ai video generation provider supporting MiniMax H3 Max models."""

from __future__ import annotations

import atexit
import logging
import os
import re
import signal
import time
from typing import Any

import fal_client
import requests

from animator.config import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_FAL_RESOLUTION,
    DEFAULT_FAL_VIDEO_MODEL,
    POLL_INTERVAL_SECONDS,
)
from animator.providers.base import ReferenceImage, VideoProvider, VideoRequest

logger = logging.getLogger("animator.providers.fal")

REFERENCE_TAG = re.compile(r"<IMAGE_REF_(\d+)>")
ALIGNMENT_LINE = re.compile(
    r"^(?:How the reference pictures align with the target video|For the target video, at|The environment set of this video matches background reference).*$",
    re.MULTILINE,
)
REFERENCE_STATEMENT_LINE = re.compile(
    r"^Match designs EXACTLY to reference images.*$",
    re.MULTILINE,
)


def prepare_reference_prompt(prompt: str) -> str:
    """Convert pipeline <IMAGE_REF_N> tags to Fal's 'Image N+1' labels."""
    return REFERENCE_TAG.sub(lambda m: f"Image {int(m[1]) + 1}", prompt)


def prepare_image_to_video_prompt(prompt: str) -> str:
    """Strip character/background reference tags and alignment statements for image-to-video."""
    text = ALIGNMENT_LINE.sub("", prompt)
    text = REFERENCE_STATEMENT_LINE.sub("", text)
    text = re.sub(r"\s*<IMAGE_REF_\d+>", "", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _normalize_resolution(resolution: str, is_image_to_video: bool = False) -> str:
    res = resolution.upper().strip()
    if res in ("480P", "480"):
        return "480P"
    if res in ("720P", "720", "768P", "768"):
        return "768P"
    if not is_image_to_video and res in ("1080P", "1080", "2K"):
        return res if res == "2K" else "1080P"
    return "480P" if is_image_to_video else "768P"


def _normalize_duration(duration: int, is_image_to_video: bool = False) -> int:
    max_dur = 10 if is_image_to_video else 15
    return max(5, min(int(duration), max_dur))


class FalVideoProvider(VideoProvider):
    """Generate video via Fal.ai API.

    Supports minimax/h3-max/reference-to-video (ordered reference images)
    and minimax/h3-max/image-to-video (start and/or end frame continuity).
    """

    name = "fal"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        resolution: str = DEFAULT_FAL_RESOLUTION,
    ) -> None:
        raw_model = (model or DEFAULT_FAL_VIDEO_MODEL).strip()
        self.model = raw_model.split(":", 1)[1] if raw_model.startswith("fal:") else raw_model
        self.api_key = api_key or os.environ.get("FAL_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError(
                "Set FAL_KEY in the environment before using the Fal video provider."
            )
        self.resolution = resolution
        self._client = fal_client.SyncClient(key=self.api_key)
        self._active_handles: set[Any] = set()
        self._shutdown_registered = False
        self._original_handlers: dict[int, Any] = {}

    @property
    def is_image_to_video(self) -> bool:
        return "image-to-video" in self.model

    def _register_shutdown_handlers(self) -> None:
        """Install signal/atexit handlers that cancel queued Fal jobs on exit."""
        if self._shutdown_registered:
            return
        self._shutdown_registered = True
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
            try:
                self._original_handlers[signum] = signal.getsignal(signum)
            except (ValueError, OSError):
                continue
            signal.signal(signum, self._handle_shutdown)
        atexit.register(self._cancel_active_handles)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        logger.warning(
            "Received signal %s while Fal video generation in progress; cancelling...",
            signum,
        )
        self._cancel_active_handles()
        original = self._original_handlers.get(signum, signal.SIG_DFL)
        signal.signal(signum, original)

    def _cancel_active_handles(self) -> None:
        for handle in list(self._active_handles):
            try:
                handle.cancel()
                logger.info("Cancelled Fal task %s", getattr(handle, "request_id", handle))
            except Exception as exc:
                logger.debug("Failed to cancel Fal task: %s", exc)
        self._active_handles.clear()

    def _upload_image(self, ref: ReferenceImage) -> str:
        """Upload image bytes directly to Fal storage."""
        return self._client.upload(ref.data, content_type=ref.mime_type)

    def _build_payload(self, request: VideoRequest) -> dict[str, Any]:
        """Construct the endpoint-specific request payload."""
        if self.is_image_to_video:
            # Image-to-video: ignore all character/bg references, only use optional start and end frames
            prompt = prepare_image_to_video_prompt(request.prompt)
            payload: dict[str, Any] = {
                "prompt": prompt,
                "duration": _normalize_duration(request.duration, is_image_to_video=True),
                "resolution": _normalize_resolution(
                    request.resolution or self.resolution, is_image_to_video=True
                ),
                "prompt_expansion_mode": "balanced",
            }
            if request.continuity_frame:
                logger.info("Uploading start frame for Fal image-to-video...")
                payload["image_url"] = self._upload_image(request.continuity_frame)
            if request.closing_frame:
                logger.info("Uploading end frame for Fal image-to-video...")
                payload["end_image_url"] = self._upload_image(request.closing_frame)
        else:
            # Reference-to-video: upload all references in canonical order
            prompt = prepare_reference_prompt(request.prompt)
            payload = {
                "prompt": prompt,
                "duration": _normalize_duration(request.duration, is_image_to_video=False),
                "resolution": _normalize_resolution(
                    request.resolution or self.resolution, is_image_to_video=False
                ),
                "aspect_ratio": request.aspect_ratio or DEFAULT_ASPECT_RATIO,
                "prompt_expansion_mode": "balanced",
            }
            all_refs: list[ReferenceImage] = []
            all_refs.extend(request.character_references)
            if request.background_reference:
                all_refs.append(request.background_reference)
            if request.continuity_frame:
                all_refs.append(request.continuity_frame)
            if request.closing_frame:
                all_refs.append(request.closing_frame)

            if all_refs:
                logger.info("Uploading %d reference image(s) to Fal...", len(all_refs))
                payload["reference_image_urls"] = [
                    self._upload_image(ref) for ref in all_refs
                ]

        payload.update(request.extra)
        return payload

    def generate(self, request: VideoRequest, timeout: int) -> bytes:
        """Submit job to Fal, poll until completion, and download generated video bytes."""
        self._register_shutdown_handlers()
        payload = self._build_payload(request)

        logger.info(
            "Submitting Fal video request to model=%s (resolution=%s, duration=%ss)...",
            self.model,
            payload.get("resolution"),
            payload.get("duration"),
        )
        total_start = time.monotonic()
        handle = self._client.submit(self.model, arguments=payload)
        self._active_handles.add(handle)
        logger.info("Fal job submitted (request id: %s)", handle.request_id)

        try:
            deadline = time.monotonic() + timeout
            previous_status = None
            while True:
                status = handle.status(with_logs=True)
                summary = type(status).__name__
                if isinstance(status, fal_client.Queued) and hasattr(status, "position"):
                    summary += f" (position {status.position})"
                if summary != previous_status:
                    logger.info("Fal job %s status: %s", handle.request_id, summary)
                    previous_status = summary

                if isinstance(status, fal_client.Completed):
                    break

                if time.monotonic() > deadline:
                    handle.cancel()
                    raise TimeoutError(
                        f"Fal video generation did not finish within {timeout}s "
                        f"(request_id: {handle.request_id})."
                    )
                time.sleep(POLL_INTERVAL_SECONDS)

            try:
                result = handle.get()
            except fal_client.FalClientError as exc:
                raise RuntimeError(f"Fal video generation failed: {exc}") from exc
        finally:
            self._active_handles.discard(handle)

        video_info = result.get("video") if isinstance(result, dict) else None
        video_url = (
            video_info.get("url")
            if isinstance(video_info, dict)
            else result.get("video_url") if isinstance(result, dict) else None
        )
        if not video_url:
            raise RuntimeError(f"Fal returned no video URL in result: {result}")

        content = self._download(video_url, timeout=120)
        logger.info(
            "Fal video generation completed in %.1fs (%d bytes).",
            time.monotonic() - total_start,
            len(content),
        )
        return content

    def _download(self, video_url: str, timeout: int) -> bytes:
        logger.info("Downloading generated video from %s...", video_url)
        resp = requests.get(video_url, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Could not download generated video from Fal ({resp.status_code}): {resp.text[:300]}"
            )
        return resp.content
