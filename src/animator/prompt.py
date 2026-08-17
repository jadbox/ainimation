"""Prompt direction and input item construction for video generation.

Reference-image alignment instructions follow the MiniMax prompt-writing
guide's task formats, adapted to this pipeline's ``<IMAGE_REF_N>`` tags:

* **I2VA** (opening frame only, the normal chained case):
  ``For the target video, at 0.00 seconds into the target video,
  <IMAGE_REF_N> (from [Shot 1]) is fully referenced.``
* **FL2VA** (opening + closing frame, e.g. regenerating a middle part):
  ``How the reference pictures align with the target video — … aligns with
  the 0.00-second mark …; … aligns with the S.SS-second mark …``
* **L2VA** (closing frame only):
  ``How the reference pictures align with the target video — <IMAGE_REF_N>
  (from [Shot 1]) aligns with the S.SS-second mark of the target video.``

``S.SS`` is the clip duration with exactly two decimal places. The
instruction is the first line of the final prompt, followed by a blank line.
"""

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

PROTECTED_SPAN_RE = re.compile(r'("[^"]*"|<d>.*?</d>)', flags=re.DOTALL)


def tag_character_mentions(text: str, characters: list[str]) -> str:
    """Insert <IMAGE_REF_N> tags at every mention of a character name in non-quoted text.

    Character names are standardized to ALL CAPS with no punctuation marks.
    Spoken content — double-quoted lines and MiniMax ``<d>...</d>`` dialogue
    blocks — is protected so names inside spoken lines are never tagged.
    """
    if not text or not characters:
        return text

    # Split text into unprotected parts (even indices) and protected spans
    # (odd indices): quoted dialogue and <d> dialogue blocks.
    parts = PROTECTED_SPAN_RE.split(text)

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

        for i in range(len(parts)):
            if not (parts[i].startswith('"') or parts[i].startswith("<d>")):
                parts[i] = regex.sub(rf"\g<0> {tag}", parts[i])

    return "".join(parts)


def build_alignment_instructions(
    duration: int,
    cont_idx: int | None,
    close_idx: int | None,
    bg_idx: int | None,
) -> list[str]:
    """Return the MiniMax reference-picture alignment instruction lines."""
    duration_str = f"{float(duration):.2f}"
    lines: list[str] = []
    if cont_idx is not None and close_idx is not None:
        lines.append(
            "How the reference pictures align with the target video — "
            f"<IMAGE_REF_{cont_idx}> (from [Shot 1]) aligns with the "
            f"0.00-second mark of the target video; <IMAGE_REF_{close_idx}> "
            f"(from [Shot 1]) aligns with the {duration_str}-second mark of "
            "the target video."
        )
    elif cont_idx is not None:
        lines.append(
            "For the target video, at 0.00 seconds into the target video, "
            f"<IMAGE_REF_{cont_idx}> (from [Shot 1]) is fully referenced."
        )
    elif close_idx is not None:
        lines.append(
            "How the reference pictures align with the target video — "
            f"<IMAGE_REF_{close_idx}> (from [Shot 1]) aligns with the "
            f"{duration_str}-second mark of the target video."
        )
    if bg_idx is not None:
        lines.append(
            f"The environment set of this video matches background reference "
            f"<IMAGE_REF_{bg_idx}> exactly."
        )
    return lines


def add_reference_tags(
    base_prompt: str,
    characters: list[str],
    has_continuity: bool = False,
    has_background_reference: bool = False,
    has_closing_continuity: bool = False,
    duration: int = DEFAULT_DURATION_SECONDS,
) -> str:
    """Add reference image tags (<IMAGE_REF_N>, alignment instructions) to base_prompt."""
    next_idx = len(characters)
    bg_idx = next_idx if has_background_reference else None
    next_idx += 1 if has_background_reference else 0
    cont_idx = next_idx if has_continuity else None
    next_idx += 1 if has_continuity else 0
    close_idx = next_idx if has_closing_continuity else None

    instructions = build_alignment_instructions(duration, cont_idx, close_idx, bg_idx)
    if not has_continuity:
        if has_closing_continuity:
            instructions.append("Begin from starting pose/composition in script.")
        else:
            instructions.append(
                "Begin from starting pose/composition in script and end on a "
                "clean held final pose."
            )

    prefix_block = "\n".join(instructions) + "\n\n" if instructions else ""

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

    old_ref_stmt = (
        "Match designs EXACTLY to reference images; never use references as "
        "opening frames."
    )
    new_ref_stmt = (
        f"Match designs EXACTLY to reference images {ref_range_str}; never "
        "use references as opening frames."
    )
    if old_ref_stmt in text:
        text = text.replace(old_ref_stmt, new_ref_stmt, 1)

    # 3. Tag character name mentions across non-quoted narrative text
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
    """Build the textual direction prompt sent to the video provider."""
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
        duration=duration,
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
