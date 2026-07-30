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
    movie_info = get_movie_info()
    aspect_ratio = get_aspect_ratio()
    span_note = f" (story time {segment.span})" if segment.span else ""

    char_tags_list = []
    for i, char in enumerate(characters):
        name_str = standardize_name(char)
        try:
            spec = get_character(char)
            voice_tag = f" <VOICE>{spec.voice}</VOICE>" if spec.voice else ""
        except ValueError:
            voice_tag = ""
        char_tags_list.append(f"{name_str} <IMAGE_REF_{i}>{voice_tag}")
    char_header_str = ", ".join(char_tags_list)

    tagged_logline = tag_character_mentions(logline, characters)
    tagged_setting = tag_character_mentions(setting, characters)
    tagged_segment_body = tag_character_mentions(segment.body, characters)

    prefix_declarations: list[str] = []
    if has_background_reference:
        bg_idx = len(characters)
        prefix_declarations.append(f"[# Background scene use references <IMAGE_REF_{bg_idx}>]")
    if has_continuity:
        cont_idx = len(characters) + (1 if has_background_reference else 0)
        prefix_declarations.append(f"[# Sources <FIRST_FRAME>IMAGE_REF_{cont_idx}]")

    prefix_block = "\n".join(prefix_declarations) + "\n\n" if prefix_declarations else ""

    setting_block = (
        f"=== SHARED SETTING & LIGHT (constant across the whole scene) ===\n{tagged_setting}\n\n"
        if tagged_setting
        else ""
    )

    cont_idx = len(characters) + (1 if has_background_reference else 0)
    bg_idx = len(characters)

    char_ref_range = f"<IMAGE_REF_0> through <IMAGE_REF_{len(characters)-1}>" if len(characters) > 1 else "<IMAGE_REF_0>"
    bg_ref_line = f"\n- Environment reference <IMAGE_REF_{bg_idx}> sets the background production set." if has_background_reference else ""

    opening_instruction = (
        ""
        if has_continuity
        else "Begin from starting pose/composition in script and end on a clean held final pose."
    )

    if has_background_reference:
        environment_instruction = (
            f"Background Set: Reference image <IMAGE_REF_{bg_idx}> is the exact set for this video (environment, set pieces, layout, lighting, depth layering)."
        )
    else:
        environment_instruction = ""

    opening_block = f"\n\n{opening_instruction}" if opening_instruction else ""
    env_block = f"\n\n{environment_instruction}" if environment_instruction else ""

    return f"""{prefix_block}In a single unbroken scene, in a single continuous shot with no scene cuts. Style: {movie_info.style_summary}

Scene: "{scene_name}" — {tagged_logline or 'see script below.'}

Characters appearing: {char_header_str}.
Match character designs EXACTLY to visual reference images ({char_ref_range}). Do NOT use character references as initial frames.{bg_ref_line}
{movie_info.camera_rules}{opening_block}{env_block}

Depth & Staging (mandatory): Characters stay on ground planes (feet on floor, never standing on furniture/props unless explicitly climbing). 
Midground set pieces MUST occlude characters passing behind them. Interacting characters share the same depth plane in 3/4 or profile view.

Single continuous camera shot (mandatory): One single continuous shot from a consistent camera perspective. 
STRICTLY NO sudden scene cuts, jump cuts, shot transitions, or camera angle changes. Camera moves smoothly in continuous motion.

Eyeline & camera rules (mandatory): Characters MUST look at each other or at scene objects as directed in script — NEVER look directly into camera lens. Maintain 3/4 or profile eyelines.

Dialogue & speaker mandates (mandatory):
- ONLY the character explicitly declared as speaker in a dialogue line moves their mouth and lips to speak.
- All non-speaking characters MUST keep their mouths firmly CLOSED, remaining silent while reacting with active body language.

Continuous character motion & physical locomotion (mandatory):
- Every character in frame MUST be actively alive with continuous secondary movement (rhythmic breathing, weight shifts, ear/whisker twitches). NO character may freeze or stand rigid.
- STRICTLY NO teleporting, sudden position pops, fading in/out of character locations, or creating duplicate/ghost character copies in frame.
- ALWAYS use proper, continuous physical locomotion and movement (stepping, walking, turning, pivoting, climbing) whenever a character or item changes location or facing orientation in the script.

{setting_block}=== SCENE SCRIPT{span_note} ===
{tagged_segment_body}"""


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

