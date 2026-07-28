#!/usr/bin/env python3
"""Animate a scene script into 720p clips with Gemini Omni Flash.

Reads the scene design document at ``out/scripts/<scene>.md`` (produced by
``src/scene_script.py``), collects the final character blueprint images for
just the characters appearing in the scene (the last ``attempt-*.jpg`` in each
character's ``out/blueprint/<character-slug>/`` folder), and sends the script
plus reference images to Google Gemini Omni Flash.

The scene script is split into clearly marked 10-second segments
(``## Segment 0 (0:00-0:10)`` ...). Each segment is self-contained (its own
blocking, camera, animation, dialogue, and sound/music sub-sections); the
video prompt for a part contains ONLY the shared ``## Setting & Light``
section plus that one segment, so the model is never confused by other
segments. Each segment is generated as its own 10-second, 720p, 24fps clip and
saved to ``out/animations/<scene>/part-<N>.mp4``. Use ``--parts N`` to generate
only one segment; without it, every missing segment is generated. When all
segments are present in the output folder at the end of a run, they are
concatenated (in order) into ``out/animations/<scene>/full.mp4``.

Usage:
    python src/animator.py --scene frisby_meets_greatowl            # all missing parts
    python src/animator.py --scene frisby_meets_greatowl --parts 2  # only the 3rd segment

Continuity: after each part clip is written, its last frame is extracted to
``part-<N>.jpg`` (requires ffmpeg). When generating segment N, if
``part-<N-1>.jpg`` exists it is sent as an extra reference image with an
instruction to continue the video from that exact frame, so consecutive
segments match in look, composition, and pose.
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
    DEFAULT_SCRIPTS_DIR,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VIDEO_MODEL,
    FULL_VIDEO_NAME,
    POLL_INTERVAL_SECONDS,
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
)
from animator.models import SceneSegment
from animator.prompt import build_direction, build_input_items
from animator.script import (
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
    "DEFAULT_SCRIPTS_DIR",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_VIDEO_MODEL",
    "FULL_VIDEO_NAME",
    "POLL_INTERVAL_SECONDS",
    "SceneSegment",
    "TRANSITION_SECONDS",
    "build_crossfade_filter",
    "build_direction",
    "build_input_items",
    "clip_duration",
    "combine_parts",
    "concat_copy",
    "create_video_interaction",
    "extract_last_frame",
    "extract_video_bytes",
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
    "run",
    "wait_for_completion",
]

if __name__ == "__main__":
    main()
