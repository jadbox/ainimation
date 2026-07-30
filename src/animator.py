#!/usr/bin/env python3
"""Animate a scene script into 720p clips with Gemini Omni Flash.

Reads the scene segment prompt files at ``out/scripts/<scene>_part<N>.md``
(produced by ``src/scene_script.py``), collects the final character blueprint
images for the characters appearing in the scene, and sends the prompt plus
reference images to Google Gemini Omni Flash.

Each segment prompt file is mostly complete and self-contained; ``animator`` adds
the necessary image reference tags (<IMAGE_REF_N>), opening/continuity frame
instructions, and prefix headers, saving the final tagged prompt to
``out/animations/<scene>/part-<N>-prompt.md``.

Each segment is generated as its own 10-second clip saved to
``out/animations/<scene>/part-<N>.mp4``. When all segments are present, they are
concatenated with crossfade transitions into ``out/animations/<scene>/full.mp4``.

Usage:
    python src/animator.py --scene frisby_meets_greatowl            # all missing parts
    python src/animator.py --scene frisby_meets_greatowl --parts 2  # only the 3rd segment
"""

from __future__ import annotations

from animator.api import create_video_interaction, extract_video_bytes, wait_for_completion
from animator.cli import main, run
from animator.config import (
    ASPECT,
    ASPECT_RATIO_MAP,
    CONTINUITY_MESSAGE,
    DEFAULT_ANIMATIONS_DIR,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_BLUEPRINT_DIR,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_RESOLUTION,
    DEFAULT_SCRIPTS_DIR,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VIDEO_MODEL,
    FULL_VIDEO_NAME,
    POLL_INTERVAL_SECONDS,
    RESOLUTION,
    TRANSITION_SECONDS,
    get_aspect_ratio,
)
from animator.media import (
    build_crossfade_filter,
    clip_duration,
    combine_parts,
    concat_copy,
    extract_last_frame,
    frame_path,
    part_path,
    previous_frame,
    prompt_path,
)
from animator.models import SceneSegment
from animator.prompt import add_reference_tags, build_direction, build_input_items
from animator.script import (
    find_scene_part_scripts,
    latest_attempt_image,
    normalize_name,
    parse_global_section,
    parse_scene_characters,
    parse_segments,
)

__all__ = [
    "ASPECT",
    "ASPECT_RATIO_MAP",
    "CONTINUITY_MESSAGE",
    "DEFAULT_ANIMATIONS_DIR",
    "DEFAULT_ASPECT_RATIO",
    "DEFAULT_BLUEPRINT_DIR",
    "DEFAULT_DURATION_SECONDS",
    "DEFAULT_RESOLUTION",
    "DEFAULT_SCRIPTS_DIR",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_VIDEO_MODEL",
    "FULL_VIDEO_NAME",
    "POLL_INTERVAL_SECONDS",
    "RESOLUTION",
    "SceneSegment",
    "TRANSITION_SECONDS",
    "add_reference_tags",
    "build_crossfade_filter",
    "build_direction",
    "build_input_items",
    "clip_duration",
    "combine_parts",
    "concat_copy",
    "create_video_interaction",
    "extract_last_frame",
    "extract_video_bytes",
    "find_scene_part_scripts",
    "frame_path",
    "get_aspect_ratio",
    "latest_attempt_image",
    "main",
    "normalize_name",
    "parse_global_section",
    "parse_scene_characters",
    "parse_segments",
    "part_path",
    "previous_frame",
    "prompt_path",
    "run",
    "wait_for_completion",
]

if __name__ == "__main__":
    main()
