"""Prompt construction for keyframe image generation."""

from __future__ import annotations

from animator.models import SceneSegment
from blueprint_generator.utils.image import (
    aspect_ratio_to_dimensions,
    normalize_aspect_ratio,
)
from blueprint_generator.utils.prompts import render_style_checklist
from movie_config import get_character, get_movie_info, standardize_name


def build_keyframe_prompt(
    scene_name: str,
    segment: SceneSegment,
    keyframe_type: str,
    characters: list[str],
    has_background: bool = False,
    has_ref_prev: bool = False,
    has_ref_after: bool = False,
) -> str:
    """Build the textual direction prompt for keyframe image generation."""
    movie_info = get_movie_info()
    aspect_ratio = normalize_aspect_ratio(movie_info.orientation)
    width, height = aspect_ratio_to_dimensions(aspect_ratio)

    # Style checklist
    checklist = render_style_checklist(movie_info)
    checklist_block = (
        f"\nFilm Style Checklist (Mandatory Do's and Don'ts):\n{checklist}\n"
        if checklist
        else ""
    )

    # Character roster details
    char_specs: list[str] = []
    for i, char in enumerate(characters):
        clean_name = standardize_name(char)
        try:
            spec = get_character(char)
            desc = f"{clean_name} (<IMAGE_REF_{i}>): a {spec.species} — {spec.identity}. Appearance: {spec.appearance}."
            if spec.avoid:
                desc += f" Avoid: {spec.avoid}."
        except ValueError:
            desc = f"{clean_name} (<IMAGE_REF_{i}>)"
        char_specs.append(desc)
    characters_block = "\n".join(f"- {item}" for item in char_specs) if char_specs else "None."

    # Target keyframe objective instructions
    if keyframe_type == "start":
        target_instruction = (
            "KEYFRAME TARGET: START FRAME (Time 0:00 / Opening Beat of this segment)\n"
            "Depict the exact opening moment, initial character positions, starting poses, "
            "and initial lighting/composition at the very beginning (0:00) of this scene part."
        )
    else:
        target_instruction = (
            "KEYFRAME TARGET: END FRAME (Closing Beat / Final Held Pose of this segment)\n"
            "Depict the culmination of the action, final character emotional poses, "
            "held expressions, and closing composition at the very end of this scene part."
        )

    # Reference alignment instructions
    ref_instructions: list[str] = []
    if characters:
        ref_indices = ", ".join(f"<IMAGE_REF_{i}>" for i in range(len(characters)))
        ref_instructions.append(
            f"1. Character Reference Model Sheets ({ref_indices}): Match character designs, proportions, "
            "fur/feather/skin texturing, anatomy, colors, and garments EXACTLY to their respective reference model sheets."
        )
    if has_background:
        ref_instructions.append(
            f"{len(ref_instructions)+1}. Background Plate Reference (<IMAGE_REF_BG>): Ensure the background environment, "
            "set architecture, props, furniture, wall/floor textures, spatial layout, depth planes, and lighting atmosphere "
            "MATCH the background reference plate (<IMAGE_REF_BG>) exactly. Do NOT invent a different room layout, alter architecture, or replace props."
        )
    if has_ref_prev and has_ref_after:
        ref_instructions.append(
            f"{len(ref_instructions)+1}. Chronological Bridge Context: This keyframe sits chronologically "
            "BETWEEN the Previous Reference Frame (<IMAGE_REF_PREV>) and the Next Reference Frame (<IMAGE_REF_AFTER>). "
            "Both reference frames define the exact same scene environment. The background environment (room layout, "
            "architecture, furniture, props, wall/window elements, and lighting scheme) MUST match both reference frames "
            "identically across the scene. Character designs and outfits must match identically, while reconciling character "
            "positions, poses, expressions, and camera staging as a coherent, harmonious midway state bridging the two moments."
        )
        ref_instructions.append(
            f"{len(ref_instructions)+1}. Previous Reference Frame (<IMAGE_REF_PREV>): Maintain strict visual and environmental "
            "continuity with this earlier frame (room set, furniture, props, materials, palette, lighting, and character appearance)."
        )
        ref_instructions.append(
            f"{len(ref_instructions)+1}. After / Next Reference Frame (<IMAGE_REF_AFTER>): Maintain strict visual and environmental "
            "continuity leading into this subsequent frame (room set, furniture, props, materials, palette, lighting, and character appearance)."
        )
    elif has_ref_prev:
        ref_instructions.append(
            f"{len(ref_instructions)+1}. Previous Reference Frame (<IMAGE_REF_PREV>): This reference frame establishes the "
            "authoritative scene environment, set layout, and character appearance for the preceding moment in this scene. "
            "The background environment (room layout, architecture, furniture, props, wall/window elements, textures, palette, "
            "and lighting) in your generated keyframe MUST MATCH the background shown in <IMAGE_REF_PREV> exactly. "
            "Ensure character designs and outfits match identically, maintaining seamless continuity with <IMAGE_REF_PREV>."
        )
    elif has_ref_after:
        ref_instructions.append(
            f"{len(ref_instructions)+1}. After / Next Reference Frame (<IMAGE_REF_AFTER>): This reference frame establishes the "
            "authoritative scene environment, set layout, and character appearance for the subsequent moment in this scene. "
            "The background environment (room layout, architecture, furniture, props, wall/window elements, textures, palette, "
            "and lighting) in your generated keyframe MUST MATCH the background shown in <IMAGE_REF_AFTER> exactly. "
            "Ensure character designs and outfits match identically, with their poses and camera staging leading naturally into <IMAGE_REF_AFTER>."
        )

    alignment_block = "\n".join(ref_instructions) if ref_instructions else "No external image references."

    return f"""Create a single, highly polished, true {aspect_ratio} hand-painted 2D animation production keyframe illustration in {movie_info.style}.

{target_instruction}

Scene: "{scene_name}"
Camera Rules: {movie_info.camera_rules}

Hard Direction Rules:
{chr(10).join(f"- {rule}" for rule in movie_info.hard_direction_rules)}
{checklist_block}
Characters in Scene:
{characters_block}

Reference Image Alignment & Continuity Instructions:
{alignment_block}

Scene Script & Setting:
{segment.body}

MANDATES:
- Output ONE clean, cohesive {aspect_ratio} production keyframe image for cel animation ({width}x{height}).
- Hand-painted 2D cel animation look with rich cel shading, gouache backgrounds, and rim lighting.
- Characters interact within the scene and NEVER look into the camera lens.
- STRICT BACKGROUND MATCHING: Ensure the background environment, set architecture, furniture, props, textures, and lighting strictly match the reference frames and background plates. Do NOT alter the room layout, change props, or invent a new background.
- STRICT CHARACTER MATCHING: Ensure all characters strictly match their reference model sheets and continuity reference frames in appearance, anatomy, facial features, proportions, colors, and garments.
- STRICTLY NO text, dialogue subtitles, sound effect labels, watermarks, UI overlays, storyboard borders, split screens, turnaround lineup layouts, or collage elements."""
