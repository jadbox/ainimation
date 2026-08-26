"""OpenRouter video generation provider."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from animator.config import (
    DEFAULT_OPENROUTER_RESOLUTION,
    DEFAULT_OPENROUTER_VIDEO_MODEL,
    POLL_INTERVAL_SECONDS,
)
from animator.providers.base import ReferenceImage, VideoProvider, VideoRequest

logger = logging.getLogger("animator.providers.openrouter")

OPENROUTER_MODELS_SUPPORTING_LAST_FRAME: frozenset[str] = frozenset({
    "bytedance/seedance-2.0-mini",
    "bytedance/seedance-2.5",
    "black-forest-labs/flux-3-video",
    "minimax/hailuo-3",
    "kwaivgi/kling-v3.0-pro",
    "kwaivgi/kling-v3.0-std",
    "google/veo-3.1-fast",
    "google/veo-3.1-lite",
    "kwaivgi/kling-video-o1",
    "bytedance/seedance-2.0",
    "bytedance/seedance-2.0-fast",
    "alibaba/wan-2.7",
    "bytedance/seedance-1-5-pro",
    "google/veo-3.1",
})


class OpenRouterVideoProvider(VideoProvider):
    """Generate video via OpenRouter's asynchronous videos API.

    Uses ``POST /api/v1/videos`` to submit a job, polls the returned polling URL
    until completion, then downloads the finished MP4. Character and background
    references are sent as ``input_references``; a continuity frame is sent as a
    ``first_frame`` image for exact frame-0 continuity and a closing frame as a
    ``last_frame`` image for exact final-frame continuity. Alibaba Wan 3.0
    (``alibaba/wan-3.0``) is the default model at 480p.
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
            if self.model in OPENROUTER_MODELS_SUPPORTING_LAST_FRAME:
                frame_images.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": request.closing_frame.data_uri()},
                        "frame_type": "last_frame",
                    }
                )
            else:
                logger.info(
                    "Model %s does not support 'last_frame'; omitting closing frame reference.",
                    self.model,
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
        response = requests.get(content_url, headers=self._headers(), timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(
                f"Could not download generated video ({response.status_code})."
            )
        return response.content
