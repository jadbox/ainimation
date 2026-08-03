"""Gemini API interactions for video generation."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import requests
from google import genai

from animator.config import POLL_INTERVAL_SECONDS, get_aspect_ratio

logger = logging.getLogger("animator.api")


def create_video_interaction(
    client: genai.Client,
    model: str,
    input_items: list[dict[str, Any]],
    duration: int,
) -> Any:
    """Request the video from Omni Flash, falling back to a minimal request.

    The full request asks for the reference_to_video task with an inline
    video response matching the configured ASPECT orientation; if the API
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
                "aspect_ratio": get_aspect_ratio(),
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
