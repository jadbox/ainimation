"""Google Gemini Omni Flash video generation provider."""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any

import requests
from google import genai

from animator.config import (
    CLOSING_MESSAGE,
    CONTINUITY_MESSAGE,
    DEFAULT_VIDEO_MODEL,
    POLL_INTERVAL_SECONDS,
)
from animator.providers.base import ReferenceImage, VideoProvider, VideoRequest

logger = logging.getLogger("animator.providers.gemini")


def build_gemini_input_items(request: VideoRequest) -> list[dict[str, Any]]:
    """Encode a :class:`VideoRequest` into Gemini's input item dicts.

    Reference images are numbered ``<IMAGE_REF_N>`` in the same order the
    animator's prompt builder assigns them (characters, then background
    plate, then continuity frame, then closing frame) so that the alignment
    instructions prepended to the prompt reference the correct image.
    """
    items: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
    next_idx = 0
    for index, ref in enumerate(request.character_references):
        items.append(
            {
                "type": "text",
                "text": f"Character reference image <IMAGE_REF_{index}>: {ref.label}",
            }
        )
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(ref.data).decode("utf-8"),
                "mime_type": ref.mime_type,
            }
        )
        next_idx = index + 1
    if request.background_reference is not None:
        bg_idx = next_idx
        items.append(
            {
                "type": "text",
                "text": (
                    f"Environment reference image <IMAGE_REF_{bg_idx}>: production "
                    "background plate for this scene's set."
                ),
            }
        )
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(request.background_reference.data).decode("utf-8"),
                "mime_type": request.background_reference.mime_type,
            }
        )
        next_idx = bg_idx + 1
    if request.continuity_frame is not None:
        cont_idx = next_idx
        items.append(
            {
                "type": "text",
                "text": (
                    f"Mandatory opening frame <IMAGE_REF_{cont_idx}> "
                    f"(<FIRST_FRAME>): {CONTINUITY_MESSAGE}"
                ),
            }
        )
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(request.continuity_frame.data).decode("utf-8"),
                "mime_type": request.continuity_frame.mime_type,
            }
        )
        next_idx = cont_idx + 1
    if request.closing_frame is not None:
        close_idx = next_idx
        items.append(
            {
                "type": "text",
                "text": (
                    f"Mandatory closing frame <IMAGE_REF_{close_idx}> "
                    f"(<LAST_FRAME>): {CLOSING_MESSAGE}"
                ),
            }
        )
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(request.closing_frame.data).decode("utf-8"),
                "mime_type": request.closing_frame.mime_type,
            }
        )
    return items


class GeminiVideoProvider(VideoProvider):
    """Video generation via Google Gemini Omni Flash (``interactions`` API)."""

    name = "google"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or DEFAULT_VIDEO_MODEL
        key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if not key:
            raise RuntimeError(
                "Set GEMINI_API_KEY or GOOGLE_API_KEY before using the Gemini "
                "video provider."
            )
        self._client = genai.Client(api_key=key)

    def generate(self, request: VideoRequest, timeout: int) -> bytes:
        t0 = time.monotonic()
        input_items = build_gemini_input_items(request)
        interaction = create_video_interaction(
            self._client,
            self.model,
            input_items,
            request.duration,
            request.aspect_ratio,
        )
        interaction = wait_for_completion(self._client, interaction, timeout)
        video = extract_video_bytes(interaction)
        logger.info(
            "Google Gemini Omni Flash video generation completed in %.1fs.",
            time.monotonic() - t0,
        )
        return video


def create_video_interaction(
    client: genai.Client,
    model: str,
    input_items: list[dict[str, Any]],
    duration: int,
    aspect_ratio: str,
) -> Any:
    """Request the video from Omni Flash, falling back to a minimal request.

    The full request asks for the reference_to_video task with an inline
    video response matching the request's aspect ratio; if the API
    rejects those parameters, retry with just the model and input.
    """
    logger.info("Requesting video generation from model=%s ...", model)
    t0 = time.monotonic()
    try:
        interaction = client.interactions.create(
            model=model,
            input=input_items,
            response_modalities=["video"],
            generation_config={
                "video_config": {"task": "reference_to_video"},
                "temperature": 0.7,
            },
            response_format={
                "type": "video",
                "aspect_ratio": aspect_ratio,
                "delivery": "inline",
                "duration": f"{duration}s",
            },
        )
    except Exception as error:
        logger.warning(
            "Full video request was rejected (%s: %s). Retrying with the minimal "
            "model+input request.",
            type(error).__name__,
            error,
        )
        interaction = client.interactions.create(
            model=model,
            input=input_items,
            generation_config={"temperature": 0.7},
        )
    logger.info(
        "Video request accepted in %.1fs (interaction id: %s, status: %s)",
        time.monotonic() - t0,
        getattr(interaction, "id", None),
        getattr(interaction, "status", None),
    )
    return interaction


def wait_for_completion(client: genai.Client, interaction: Any, timeout: int) -> Any:
    """Poll the interaction until it completes, fails, or the timeout elapses."""
    terminal_ok = {"completed"}
    terminal_bad = {"failed", "cancelled", "incomplete", "budget_exceeded"}
    deadline = time.monotonic() + timeout
    while getattr(interaction, "status", None) not in terminal_ok | terminal_bad:
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Video generation did not finish within {timeout}s "
                f"(interaction id: {getattr(interaction, 'id', None)})."
            )
        logger.info(
            "Status: %s — polling again in %ds ...",
            getattr(interaction, "status", "unknown"),
            POLL_INTERVAL_SECONDS,
        )
        time.sleep(POLL_INTERVAL_SECONDS)
        interaction = client.interactions.get(interaction.id)
    status = getattr(interaction, "status", None)
    if status in terminal_bad:
        raise RuntimeError(f"Video generation ended with status {status!r}.")
    return interaction


def extract_video_bytes(interaction: Any) -> bytes:
    """Extract raw MP4 bytes from a completed interaction response."""
    video = getattr(interaction, "output_video", None)
    if video is None:
        raise RuntimeError("Gemini Omni Flash returned no output video.")
    data = getattr(video, "data", None)
    if data:
        return base64.b64decode(data)
    uri = getattr(video, "uri", None)
    if uri:
        logger.info("Downloading generated video from %s ...", uri)
        response = requests.get(uri, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(f"Could not download generated video ({response.status_code}).")
        return response.content
    raise RuntimeError("Gemini Omni Flash returned a video with neither data nor a URI.")
