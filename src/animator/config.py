"""Configuration constants for scene script animation."""

from __future__ import annotations

from pathlib import Path

DEFAULT_VIDEO_MODEL = "gemini-omni-flash-preview"
DEFAULT_DURATION_SECONDS = 10
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_SCRIPTS_DIR = Path("out") / "scripts"
DEFAULT_BLUEPRINT_DIR = Path("out") / "blueprint"
DEFAULT_ANIMATIONS_DIR = Path("out") / "animations"
DEFAULT_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5

FULL_VIDEO_NAME = "full.mp4"
TRANSITION_SECONDS = 0.8
"""Duration of the transparent crossfade between clips (~6 frames at 30fps)."""

CONTINUITY_MESSAGE = (
    "MANDATORY OPENING FRAME: the attached reference image is the final frame "
    "of the previous shot, and it IS frame 0 of your output. The very first "
    "frame of the generated video must be a pixel-faithful reproduction of this "
    "exact image. This applies to EVERYTHING in the frame — the characters "
    "(design, pose, expression, scale) AND the entire background scene: the "
    "exact same set, architecture, props, spatial layout, lighting, and color "
    "palette. The environment is the identical physical space continuing across "
    "shots and must be inherited from this reference — never redesigned, "
    "repainted, relocated, re-dressed, or re-lit. Do NOT reinterpret, re-frame, "
    "re-light, re-angle, zoom, or redesign any element. All motion must begin "
    "from this exact state, with the characters moving within the SAME "
    "unchanged background, and carry the action forward seamlessly from it. "
    "This requirement overrides any conflicting framing described elsewhere."
)
