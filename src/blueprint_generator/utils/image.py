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


def normalize_aspect_ratio(orientation: str | None) -> str:
    """Normalize orientation/aspect ratio string to Gemini supported aspect ratios."""
    if not orientation:
        return "16:9"
    norm = orientation.lower().strip()
    if norm == "landscape":
        return "16:9"
    if norm == "portrait":
        return "9:16"
    return norm


def aspect_ratio_to_dimensions(aspect_ratio: str) -> tuple[int, int]:
    """Return (width, height) pixel dimensions for a given aspect ratio string."""
    norm = normalize_aspect_ratio(aspect_ratio)
    if norm == "16:9":
        return (1280, 720)
    if norm == "9:16":
        return (720, 1280)
    if norm == "1:1":
        return (1024, 1024)
    if norm == "4:3":
        return (960, 720)
    if norm == "3:4":
        return (720, 960)

    try:
        w_str, h_str = norm.split(":")
        w, h = float(w_str), float(h_str)
        if w >= h:
            return (int(round(720 * (w / h))), 720)
        else:
            return (720, int(round(720 * (h / w))))
    except Exception:
        return (1280, 720)


def generate_image(
    client: genai.Client,
    model: str,
    prompt: str | list[Any],
    aspect_ratio: str = "16:9",
) -> bytes:
    """Generate an image using Gemini image generation model with specified aspect ratio."""
    norm_ratio = normalize_aspect_ratio(aspect_ratio)
    logger.info("Generating image with model=%s (aspect_ratio=%s) ...", model, norm_ratio)
    if isinstance(prompt, str):
        logger.debug("Image generation prompt:\n%s", prompt[:500] + ("..." if len(prompt) > 500 else ""))
    else:
        logger.debug("Image generation prompt with %d content items", len(prompt))
    t0 = time.monotonic()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio=norm_ratio),
        ),
    )
    data = extract_image(response)
    elapsed = time.monotonic() - t0
    logger.info("Image generated successfully in %.1fs (%d bytes raw)", elapsed, len(data))
    return data


TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
"""Default 16:9 output dimensions for processed JPEGs."""


def crop_to_aspect_ratio(image: Image.Image, aspect_ratio: str = "16:9") -> Image.Image:
    """Center-crop ``image`` to match the target aspect ratio."""
    target_width, target_height = aspect_ratio_to_dimensions(aspect_ratio)
    target_ratio = target_width / target_height
    width, height = image.size
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


def crop_to_16_9(image: Image.Image) -> Image.Image:
    """Center-crop ``image`` to a true 16:9 aspect ratio."""
    return crop_to_aspect_ratio(image, "16:9")


def to_jpeg(image_data: bytes, aspect_ratio: str = "16:9") -> bytes:
    """Convert image bytes to a high quality JPEG resized to the target aspect ratio."""
    target_width, target_height = aspect_ratio_to_dimensions(aspect_ratio)
    with Image.open(io.BytesIO(image_data)) as image:
        converted = image.convert("RGB")
        converted = crop_to_aspect_ratio(converted, aspect_ratio)
        converted = converted.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )
        buf = io.BytesIO()
        converted.save(buf, format="JPEG", quality=95, optimize=True)
        return buf.getvalue()


def save_jpeg(image_data: bytes, destination: Path) -> None:
    """Save JPEG image bytes to destination path."""
    destination.write_bytes(image_data)
