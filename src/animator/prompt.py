"""Prompt direction and input item construction for video generation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from animator.config import CONTINUITY_MESSAGE
from animator.models import SceneSegment


def build_direction(
    scene_name: str,
    logline: str,
    setting: str,
    segment: SceneSegment,
    characters: list[str],
    duration: int,
    has_continuity: bool = False,
) -> str:
    """Build the textual direction prompt sent to Google Gemini Omni Flash."""
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
    return f"""Animate one continuous {duration}-second, 720p, 24fps, 16:9 hand-painted 2D cel
animation clip in the style of a 1982 Don Bluth feature (The Secret of NIMH):
hand-inked tapered lines, 2-tone cel shading, painterly gouache backgrounds,
warm amber key light against deep teal/indigo shadow, 360-degree rim lighting,
heavy vignette, soft-focus dark foreground occlusion on 20-30% of the frame
borders, film grain.

Scene: "{scene_name}" — {logline or 'see script below.'}

Characters appearing (reference images attached, in order): {", ".join(characters)}.
Match each character's design EXACTLY to its reference image — same fur colors,
garment, eyes, and proportions. Keep the camera at rodent eye-level
(2-12 inches high) around a single dominant practical light source.
{opening_instruction}

{setting_block}=== SCENE SCRIPT{span_note} ===
{segment.body}"""


def build_input_items(
    direction: str,
    references: list[tuple[str, Path]],
    continuity_frame: Path | None = None,
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
