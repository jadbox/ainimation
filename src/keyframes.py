#!/usr/bin/env python3
"""Generate keyframe proposal images for scene script parts ahead of animation.

Reads the scene segment script files at ``films/<film>/out/scripts/<scene>_part<N>.md``,
collects character blueprints, scene background plates, and optional prior keyframe
references, then generates 16:9 start and/or end frame proposal images saved to
``films/<film>/out/animations/<scene>/part-<N>-<start|end>-proposal.jpg``.

Usage:
    python src/keyframes.py --scene frisby_visits_mr_ages --parts 0 --start
    python src/keyframes.py --scene frisby_visits_mr_ages --parts 0 --both
    python src/keyframes.py --scene frisby_visits_mr_ages --parts 1 --start --ref part-0-end-proposal.jpg
"""

from __future__ import annotations

from keyframes.cli import build_parser, main, run
from keyframes.generator import generate_keyframe
from keyframes.paths import (
    next_proposal_paths,
    proposal_metadata_path,
    proposal_path,
    proposal_prompt_path,
    resolve_ref_image,
)
from keyframes.prompt import build_keyframe_prompt

__all__ = [
    "build_keyframe_prompt",
    "build_parser",
    "generate_keyframe",
    "main",
    "next_proposal_paths",
    "proposal_metadata_path",
    "proposal_path",
    "proposal_prompt_path",
    "resolve_ref_image",
    "run",
]

if __name__ == "__main__":
    main()
