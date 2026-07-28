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


def to_jpeg(image_data: bytes) -> bytes:
    """Convert image bytes to high quality JPEG format resized to 1280x720 maximum."""
    with Image.open(io.BytesIO(image_data)) as image:
        converted = image.convert("RGB")
        converted.thumbnail((1280, 720), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        converted.save(buf, format="JPEG", quality=95, optimize=True)
        return buf.getvalue()


def save_jpeg(image_data: bytes, destination: Path) -> None:
    """Save JPEG image bytes to destination path."""
    destination.write_bytes(image_data)
