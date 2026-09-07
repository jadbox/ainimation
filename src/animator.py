#!/usr/bin/env python3
"""Animate a scene script into clips via a pluggable video provider.

Reads the scene segment prompt files at ``films/<film>/out/scripts/<scene>_part<N>.md``
(produced by ``src/scriptgen.py``), collects the final character blueprint
images for the characters appearing in the scene, and sends the prompt plus
reference images to a configured video provider (MiniMax H3 via the MiniMax
API by default, or OpenRouter's async videos API e.g. ``alibaba/wan-3.0``).

Each segment prompt file is mostly complete and self-contained; ``animator`` adds
the necessary image reference tags (<IMAGE_REF_N>), opening/closing continuity
frame instructions, and prefix headers, saving the final tagged prompt to
``films/<film>/out/animations/<scene>/part-<N>-prompt.md``.

Each segment is generated as its own 10-second clip saved to
``films/<film>/out/animations/<scene>/part-<N>.mp4``, with its first and last frames exported
as ``part-<N>-start.jpg`` and ``part-<N>-end.jpg``. When all segments are
present, they are concatenated with crossfade transitions into
``films/<film>/out/animations/<scene>/full.mp4``.

Usage:
    python src/animator.py --scene frisby_meets_greatowl            # all missing parts
    python src/animator.py --scene frisby_meets_greatowl --parts 2  # only the 3rd segment
    python src/animator.py --scene frisby_meets_greatowl --parts 1 --frame_start path/to/start.jpg --frame_end path/to/end.jpg
"""

from __future__ import annotations

from animator.cli import main, run
from animator.providers.gemini import GeminiVideoProvider, extract_video_bytes
from animator.config import (
    ASPECT,
    ASPECT_RATIO_MAP,
    CONTINUITY_MESSAGE,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_OPENROUTER_RESOLUTION,
    DEFAULT_OPENROUTER_VIDEO_MODEL,
    DEFAULT_RESOLUTION,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_GOOGLE_VIDEO_MODEL,
    DEFAULT_VIDEO_PROVIDER,
    FULL_VIDEO_NAME,
    POLL_INTERVAL_SECONDS,
    RESOLUTION,
    TRANSITION_SECONDS,
    VIDEO_PROVIDERS,
    get_aspect_ratio,
)
from animator.media import (
    build_crossfade_filter,
    clip_duration,
    combine_parts,
    concat_copy,
    end_frame_path,
    extract_first_frame,
    extract_last_frame,
    latest_end_frame_path,
    latest_part_path,
    latest_start_frame_path,
    metadata_path,
    next_frame,
    next_part_paths,
    part_path,
    previous_frame,
    prompt_path,
    start_frame_path,
)
from animator.models import SceneSegment
from animator.prompt import add_reference_tags, build_direction, build_video_request
from animator.providers import (
    GeminiVideoProvider,
    MiniMaxVideoProvider,
    OpenRouterVideoProvider,
    ReferenceImage,
    VideoProvider,
    VideoRequest,
    create_video_provider,
)
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
    "DEFAULT_ASPECT_RATIO",
    "DEFAULT_DURATION_SECONDS",
    "DEFAULT_OPENROUTER_RESOLUTION",
    "DEFAULT_OPENROUTER_VIDEO_MODEL",
    "DEFAULT_RESOLUTION",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_GOOGLE_VIDEO_MODEL",
    "DEFAULT_VIDEO_PROVIDER",
    "FULL_VIDEO_NAME",
    "GeminiVideoProvider",
    "MiniMaxVideoProvider",
    "OpenRouterVideoProvider",
    "POLL_INTERVAL_SECONDS",
    "RESOLUTION",
    "ReferenceImage",
    "SceneSegment",
    "TRANSITION_SECONDS",
    "VIDEO_PROVIDERS",
    "VideoProvider",
    "VideoRequest",
    "add_reference_tags",
    "build_crossfade_filter",
    "build_direction",
    "build_video_request",
    "clip_duration",
    "combine_parts",
    "concat_copy",
    "create_video_provider",
    "end_frame_path",
    "extract_first_frame",
    "extract_last_frame",
    "extract_video_bytes",
    "find_scene_part_scripts",
    "get_aspect_ratio",
    "latest_attempt_image",
    "latest_end_frame_path",
    "latest_part_path",
    "latest_start_frame_path",
    "main",
    "metadata_path",
    "next_frame",
    "next_part_paths",
    "normalize_name",
    "parse_global_section",
    "parse_scene_characters",
    "parse_segments",
    "part_path",
    "previous_frame",
    "prompt_path",
    "run",
    "start_frame_path",
]

if __name__ == "__main__":
    main()
