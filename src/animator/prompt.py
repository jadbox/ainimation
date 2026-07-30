"""Prompt direction and input item construction for video generation."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from animator.config import CONTINUITY_MESSAGE, DEFAULT_RESOLUTION, get_aspect_ratio
from animator.models import SceneSegment
from movie_config import get_character, get_movie_info, standardize_name


def tag_character_mentions(text: str, characters: list[str]) -> str:
    """Insert <IMAGE_REF_N> tags at every mention of a character name in non-quoted text.

    Character names are standardized to ALL CAPS with no punctuation marks.
    """
    if not text or not characters:
        return text

    # Split text into non-quoted parts (even indices) and quoted dialogue parts (odd indices)
    parts = re.split(r'("[^"]*")', text)

    for index, char_name in enumerate(characters):
        clean_name = standardize_name(char_name)
        if not clean_name:
            continue
        tag = f"<IMAGE_REF_{index}>"
        words = clean_name.split()
        word_pattern = r"\s+".join(rf"{re.escape(w)}\.?" for w in words)
        pattern = rf"\b{word_pattern}\b"
        # Negative lookahead ensures we don't re-tag if <IMAGE_REF_...> is already present
        regex = re.compile(rf"{pattern}(?!\s*<IMAGE_REF_\d+>)", re.IGNORECASE)

        # Only tag non-quoted narrative and direction text, leaving spoken dialogue inside quotes untouched
        for i in range(len(parts)):
            if not parts[i].startswith('"'):
                parts[i] = regex.sub(rf"\g<0> {tag}", parts[i])

    return "".join(parts)


def add_reference_tags(
    base_prompt: str,
    characters: list[str],
    has_continuity: bool = False,
    has_background_reference: bool = False,
) -> str:
    """Add reference image tags (<IMAGE_REF_N>, opening instructions, prefixes) to base_prompt."""
    bg_idx = len(characters) if has_background_reference else None
    cont_idx = (
        len(characters) + (1 if has_background_reference else 0)
        if has_continuity
        else None
    )

    prefix_declarations: list[str] = []
    if has_background_reference and bg_idx is not None:
        prefix_declarations.append(f"[# Background scene use references <IMAGE_REF_{bg_idx}>]")
    if has_continuity and cont_idx is not None:
        prefix_declarations.append(f"[# Sources <FIRST_FRAME>IMAGE_REF_{cont_idx}]")

    prefix_block = "\n".join(prefix_declarations) + "\n\n" if prefix_declarations else ""

    text = base_prompt

    # 1. Tag character header line
    for i, char in enumerate(characters):
        clean_name = standardize_name(char)
        if not clean_name:
            continue
        tag = f"<IMAGE_REF_{i}>"
        pattern = rf"\b{re.escape(clean_name)}\b(?!\s*<IMAGE_REF_\d+>)"
        text = re.sub(pattern, f"{clean_name} {tag}", text, count=1, flags=re.IGNORECASE)

    # 2. Update reference image statement line
    if len(characters) > 1:
        ref_range_str = f"(<IMAGE_REF_0> through <IMAGE_REF_{len(characters) - 1}>)"
    elif len(characters) == 1:
        ref_range_str = "(<IMAGE_REF_0>)"
    else:
        ref_range_str = ""

    bg_ref_line = (
        f"\n- Environment reference <IMAGE_REF_{bg_idx}> sets the background production set."
        if has_background_reference and bg_idx is not None
        else ""
    )

    old_ref_stmt = "Match character designs EXACTLY to visual reference images. Do NOT use character references as initial frames."
    new_ref_stmt = f"Match character designs EXACTLY to visual reference images {ref_range_str}. Do NOT use character references as initial frames.{bg_ref_line}"
    if old_ref_stmt in text:
        text = text.replace(old_ref_stmt, new_ref_stmt, 1)

    # 3. Add opening / background instructions
    instructions: list[str] = []
    if not has_continuity:
        instructions.append("Begin from starting pose/composition in script and end on a clean held final pose.")
    if has_background_reference and bg_idx is not None:
        instructions.append(
            f"Background Set: Reference image <IMAGE_REF_{bg_idx}> is the exact set for this video (environment, set pieces, layout, lighting, depth layering)."
        )

    if instructions:
        inst_block = "\n\n".join(instructions)
        if "Depth & Staging (mandatory):" in text:
            text = text.replace("Depth & Staging (mandatory):", f"{inst_block}\n\nDepth & Staging (mandatory):", 1)
        else:
            text = text + "\n\n" + inst_block

    # 4. Tag character name mentions across non-quoted narrative text
    text = tag_character_mentions(text, characters)

    return prefix_block + text


def build_direction(
    scene_name: str,
    logline: str,
    setting: str,
    segment: SceneSegment,
    characters: list[str],
    duration: int,
    has_continuity: bool = False,
    has_background_reference: bool = False,
    resolution: str = DEFAULT_RESOLUTION,
) -> str:
    """Build the textual direction prompt sent to Google Gemini Omni Flash."""
    from scene_script import format_segment_base_prompt

    base_prompt = format_segment_base_prompt(
        scene_name=scene_name,
        logline=logline,
        setting=setting,
        characters=characters,
        span=segment.span,
        segment_body=segment.body,
    )
    return add_reference_tags(
        base_prompt=base_prompt,
        characters=characters,
        has_continuity=has_continuity,
        has_background_reference=has_background_reference,
    )


def build_input_items(
    direction: str,
    references: list[tuple[str, Path]],
    continuity_frame: Path | None = None,
    background_plate: Path | None = None,
) -> list[dict[str, Any]]:
    """Assemble text and encoded image payloads for Gemini video generation."""
    items: list[dict[str, Any]] = [{"type": "text", "text": direction}]
    for i, (character_name, image_path) in enumerate(references):
        items.append({"type": "text", "text": f"Character reference image <IMAGE_REF_{i}>: {standardize_name(character_name)}"})
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(image_path.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    if background_plate is not None:
        bg_idx = len(references)
        items.append(
            {
                "type": "text",
                "text": f"Environment reference image <IMAGE_REF_{bg_idx}>: production background plate for this scene's set.",
            }
        )
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(background_plate.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    if continuity_frame is not None:
        items.append({"type": "text", "text": f"Mandatory opening frame <FIRST_FRAME>: {CONTINUITY_MESSAGE}"})
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(continuity_frame.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    return items


