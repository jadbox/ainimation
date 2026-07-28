"""Prompt direction and input item construction for video generation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from animator.config import CONTINUITY_MESSAGE, get_aspect_ratio
from animator.models import SceneSegment
from movie_config import get_movie_info


def build_direction(
    scene_name: str,
    logline: str,
    setting: str,
    segment: SceneSegment,
    characters: list[str],
    duration: int,
    has_continuity: bool = False,
    has_background_reference: bool = False,
) -> str:
    """Build the textual direction prompt sent to Google Gemini Omni Flash."""
    movie_info = get_movie_info()
    aspect_ratio = get_aspect_ratio()
    span_note = f" (story time {segment.span})" if segment.span else ""
    setting_block = (
        f"=== SHARED SETTING & LIGHT (constant across the whole scene) ===\n{setting}\n\n"
        if setting
        else ""
    )
    if has_continuity:
        opening_instruction = (
            "The final attached reference image is the mandatory opening frame "
            "of this video: reproduce it exactly as frame 0 — the characters AND "
            "the background scene alike (see the MANDATORY OPENING FRAME "
            "instruction below) — then end on a clean held final pose. The "
            "background must remain the exact same set, with the same props, "
            "layout, and lighting, throughout the clip."
        )
    else:
        opening_instruction = (
            "Begin from the exact starting pose/composition stated in the Shot "
            "Steps and end on a clean held final pose."
        )
    environment_instruction = (
        "The final attached reference image is this scene's production background "
        "plate: treat it as the exact set for this video — the same environment, "
        "set pieces, layout, lighting, and depth layering. Place the characters "
        "INTO this set on the ground planes stated in the script."
        if has_background_reference
        else ""
    )
    return f"""Animate one continuous {duration}-second, 720p, 24fps, {aspect_ratio} {movie_info.style_summary}

Scene: "{scene_name}" — {logline or 'see script below.'}

Characters appearing (reference images attached, in order): {", ".join(characters)}.
Match each character's design EXACTLY to its reference image — same fur colors,
garment, eyes, and proportions. {movie_info.camera_rules}
{opening_instruction}
{environment_instruction}
Depth ordering & staging (mandatory): every character stays on the exact ground plane
stated in the script — feet on the floor; a character NEVER stands on top of
furniture, props, or light-source pedestals (tables, desks, jars, lanterns)
unless the script explicitly calls for climbing. Midground set pieces sit
between the camera and the characters and must OCCLUDE the characters whenever
the blocking sends them behind those pieces; characters pass in front of or
behind set pieces exactly as directed, never through or on top of them. Interacting
characters stay on the same general depth plane so both characters are clearly
visible in 3/4 profile or profile angle facing each other.

Single continuous camera shot (mandatory): this entire video clip MUST be generated as one single continuous shot from a consistent camera perspective. STRICTLY NO sudden scene cuts, jump cuts, shot transitions, or camera angle changes during the video clip. The camera position moves smoothly in continuous motion within that single shot.

Eyeline & camera rules (mandatory): characters MUST look at each other or at
scene objects as directed in the script — NEVER look directly into the camera lens.
Maintain 3/4 profile or profile eyelines between interacting characters.

Continuous character motion (mandatory): every character in frame MUST be actively
alive with continuous secondary movement (rhythmic chest breathing, weight shifts,
shuffling papers/props, ear or whisker twitches). NO character may freeze, stand
rigid, or behave like a static robot.

{setting_block}=== SCENE SCRIPT{span_note} ===
{segment.body}"""


def build_input_items(
    direction: str,
    references: list[tuple[str, Path]],
    continuity_frame: Path | None = None,
    background_plate: Path | None = None,
) -> list[dict[str, Any]]:
    """Assemble text and encoded image payloads for Gemini video generation."""
    items: list[dict[str, Any]] = [{"type": "text", "text": direction}]
    for character_name, image_path in references:
        items.append({"type": "text", "text": f"Character reference image: {character_name}"})
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(image_path.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    if background_plate is not None:
        items.append(
            {
                "type": "text",
                "text": "Environment reference image: production background plate for this scene's set.",
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
        items.append({"type": "text", "text": CONTINUITY_MESSAGE})
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(continuity_frame.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    return items
