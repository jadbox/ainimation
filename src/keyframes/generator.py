"""Keyframe image generation via Gemini API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from animator.models import SceneSegment
from blueprint_generator.utils.image import (
    generate_image,
    normalize_aspect_ratio,
    save_jpeg,
    to_jpeg,
)
from keyframes.prompt import build_keyframe_prompt
from movie_config import get_movie_info

logger = logging.getLogger("keyframes")


def generate_keyframe(
    client: genai.Client,
    model: str,
    scene_name: str,
    segment: SceneSegment,
    keyframe_type: str,
    characters: list[str],
    character_refs: list[tuple[str, Path]],
    background_plate: Path | None,
    ref_prev: Path | None,
    ref_after: Path | None,
    output_path: Path,
    prompt_file_path: Path,
) -> Path:
    """Assemble multimodal contents, prompt Gemini, and save the keyframe proposal."""
    movie_info = get_movie_info()
    aspect_ratio = normalize_aspect_ratio(movie_info.orientation)

    logger.info(
        "--- Generating %s keyframe proposal for %s part %d (aspect_ratio=%s) ---",
        keyframe_type.upper(),
        scene_name,
        segment.index,
        aspect_ratio,
    )

    prompt_text = build_keyframe_prompt(
        scene_name=scene_name,
        segment=segment,
        keyframe_type=keyframe_type,
        characters=characters,
        has_background=background_plate is not None,
        has_ref_prev=ref_prev is not None,
        has_ref_after=ref_after is not None,
    )

    prompt_file_path.write_text(prompt_text, encoding="utf-8")
    logger.info("Saved keyframe prompt (%d chars) to: %s", len(prompt_text), prompt_file_path)

    # Build Gemini multimodal contents list
    contents: list[Any] = []
    for i, (name, img_path) in enumerate(character_refs):
        contents.append(
            f"[Character Reference <IMAGE_REF_{i}>: {name} — Match character design, anatomy, and wardrobe exactly]"
        )
        contents.append(types.Part.from_bytes(data=img_path.read_bytes(), mime_type="image/jpeg"))

    if background_plate is not None:
        contents.append(
            "[Scene Background Plate Reference <IMAGE_REF_BG> — Match background environment, architecture, props, and lighting exactly]"
        )
        contents.append(
            types.Part.from_bytes(data=background_plate.read_bytes(), mime_type="image/jpeg")
        )

    if ref_prev is not None:
        contents.append(
            f"[Previous Reference Frame <IMAGE_REF_PREV>: {ref_prev.name} — Authoritative background and character continuity reference; match background environment and character designs exactly]"
        )
        contents.append(types.Part.from_bytes(data=ref_prev.read_bytes(), mime_type="image/jpeg"))

    if ref_after is not None:
        contents.append(
            f"[After / Next Reference Frame <IMAGE_REF_AFTER>: {ref_after.name} — Authoritative background and character continuity reference; match background environment and character designs exactly]"
        )
        contents.append(types.Part.from_bytes(data=ref_after.read_bytes(), mime_type="image/jpeg"))

    contents.append(prompt_text)

    raw_image_bytes = generate_image(client, model, contents, aspect_ratio=aspect_ratio)
    jpeg_bytes = to_jpeg(raw_image_bytes, aspect_ratio=aspect_ratio)
    save_jpeg(jpeg_bytes, output_path)

    file_uri = output_path.resolve().as_uri()
    print(f"\nWrote keyframe proposal: {output_path}")
    print(f"Review proposal image: {file_uri}")
    print(f"Prompt saved to: {prompt_file_path}\n")
    return output_path
