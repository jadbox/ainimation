"""Prompt direction and input item construction for video generation."""

from __future__ import annotations

import re
from pathlib import Path

from animator.config import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_RESOLUTION,
)
from animator.models import SceneSegment
from animator.provider import ReferenceImage, VideoRequest
from movie_config import standardize_name


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
    has_closing_continuity: bool = False,
) -> str:
    """Add reference image tags (<IMAGE_REF_N>, opening instructions, prefixes) to base_prompt."""
    next_idx = len(characters)
    bg_idx = next_idx if has_background_reference else None
    next_idx += 1 if has_background_reference else 0
    cont_idx = next_idx if has_continuity else None
    next_idx += 1 if has_continuity else 0
    close_idx = next_idx if has_closing_continuity else None

    prefix_declarations: list[str] = []
    if has_background_reference and bg_idx is not None:
        prefix_declarations.append(f"[# Background scene use references <IMAGE_REF_{bg_idx}>]")
    if has_continuity and cont_idx is not None:
        prefix_declarations.append(f"[# Sources <FIRST_FRAME>IMAGE_REF_{cont_idx}]")
    if has_closing_continuity and close_idx is not None:
        prefix_declarations.append(f"[# Sources <LAST_FRAME>IMAGE_REF_{close_idx}]")

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
        if has_closing_continuity:
            instructions.append("Begin from starting pose/composition in script.")
        else:
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
    has_closing_continuity: bool = False,
    resolution: str = DEFAULT_RESOLUTION,
) -> str:
    """Build the textual direction prompt sent to Google Gemini Omni Flash."""
    from scriptgen.format import format_segment_base_prompt

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
        has_closing_continuity=has_closing_continuity,
    )


def build_video_request(
    direction: str,
    references: list[tuple[str, Path]],
    continuity_frame: Path | None = None,
    background_plate: Path | None = None,
    closing_frame: Path | None = None,
    duration: int = DEFAULT_DURATION_SECONDS,
    resolution: str = DEFAULT_RESOLUTION,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    temperature: float | None = None,
) -> VideoRequest:
    """Assemble a backend-agnostic :class:`VideoRequest` from the pipeline inputs.

    ``direction`` is the fully tagged prompt text; ``references`` are the
    character blueprint image paths; ``continuity_frame``, ``background_plate``
    and ``closing_frame`` are optional reference/opening/closing-frame image
    paths. Images are read and encoded up front so each :class:`VideoProvider`
    can serialise them for its own API.
    """
    character_references = tuple(
        ReferenceImage(
            label=standardize_name(name),
            data=image_path.read_bytes(),
            mime_type="image/jpeg",
        )
        for name, image_path in references
    )
    background_reference = (
        ReferenceImage(
            label="background",
            data=background_plate.read_bytes(),
            mime_type="image/jpeg",
        )
        if background_plate is not None
        else None
    )
    first_frame = (
        ReferenceImage(
            label="continuity",
            data=continuity_frame.read_bytes(),
            mime_type="image/jpeg",
        )
        if continuity_frame is not None
        else None
    )
    last_frame = (
        ReferenceImage(
            label="closing",
            data=closing_frame.read_bytes(),
            mime_type="image/jpeg",
        )
        if closing_frame is not None
        else None
    )
    return VideoRequest(
        prompt=direction,
        character_references=character_references,
        background_reference=background_reference,
        continuity_frame=first_frame,
        closing_frame=last_frame,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        temperature=temperature,
    )


