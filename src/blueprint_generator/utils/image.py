"""Image extraction, generation, and processing utilities."""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger("blueprint_generator.image")


def extract_image(response: Any) -> bytes:
    """Extract raw image bytes from a Gemini API generation response."""
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and getattr(inline_data, "data", None):
                return inline_data.data
    raise RuntimeError("Gemini returned no inline image data.")


def generate_image(client: genai.Client, model: str, prompt: str) -> bytes:
    """Generate a 16:9 image using Gemini image generation model."""
    logger.info("Generating image with model=%s ...", model)
    logger.debug("Image generation prompt:\n%s", prompt[:500] + ("..." if len(prompt) > 500 else ""))
    t0 = time.monotonic()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio="16:9"),
        ),
    )
    data = extract_image(response)
    elapsed = time.monotonic() - t0
    logger.info("Image generated successfully in %.1fs (%d bytes raw)", elapsed, len(data))
    return data


TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
"""True 16:9 output dimensions for processed JPEGs."""


def crop_to_16_9(image: Image.Image) -> Image.Image:
    """Center-crop ``image`` to a true 16:9 aspect ratio.

    PIL's ``thumbnail`` preserves the source aspect ratio, so a model that
    returns a non-16:9 composition would otherwise slip through as e.g.
    1280x714, which breaks background/animation anchoring. Cropping to exactly
    16:9 keeps generated blueprints on-canon.
    """
    width, height = image.size
    target_ratio = TARGET_WIDTH / TARGET_HEIGHT
    source_ratio = width / height
    if abs(source_ratio - target_ratio) < 1e-6:
        return image
    if source_ratio > target_ratio:
        new_width = int(round(height * target_ratio))
        left = (width - new_width) // 2
        box = (left, 0, left + new_width, height)
    else:
        new_height = int(round(width / target_ratio))
        top = (height - new_height) // 2
        box = (0, top, width, top + new_height)
    return image.crop(box)


def to_jpeg(image_data: bytes) -> bytes:
    """Convert image bytes to a true 16:9 high quality JPEG resized to 1280x720."""
    with Image.open(io.BytesIO(image_data)) as image:
        converted = image.convert("RGB")
        converted = crop_to_16_9(converted)
        converted = converted.resize(
            (TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS
        )
        buf = io.BytesIO()
        converted.save(buf, format="JPEG", quality=95, optimize=True)
        return buf.getvalue()


def save_jpeg(image_data: bytes, destination: Path) -> None:
    """Save JPEG image bytes to destination path."""
    destination.write_bytes(image_data)
