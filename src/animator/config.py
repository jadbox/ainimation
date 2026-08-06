"""Configuration constants for scene script animation."""

from __future__ import annotations

from pathlib import Path

ASPECT = "landscape"
"""Static configuration for aspect ratio orientation. Options: 'landscape' or 'portrait'."""

RESOLUTION = "480p"
"""Static configuration for video resolution. Options: e.g. '720p', '480p', '360p', '1080p'."""

ASPECT_RATIO_MAP = {
    "landscape": "16:9",
    "portrait": "9:16",
}


def get_aspect_ratio(aspect: str = ASPECT) -> str:
    """Return the aspect ratio string ('16:9' or '9:16') based on the orientation option."""
    key = aspect.lower().strip()
    if key not in ASPECT_RATIO_MAP:
        valid = ", ".join(f"{k!r}" for k in ASPECT_RATIO_MAP)
        raise ValueError(f"Invalid ASPECT configuration {aspect!r}. Expected one of {valid}.")
    return ASPECT_RATIO_MAP[key]


DEFAULT_VIDEO_MODEL = "gemini-omni-flash-preview"
"""Default video model for the Gemini provider."""

DEFAULT_VIDEO_PROVIDER = "google"
"""Default video generation provider (Google Gemini Omni Flash).
Options: 'google' (or its 'gemini' alias), 'openrouter' or 'minimax'."""

VIDEO_PROVIDERS = ("google", "openrouter", "minimax", "gemini")
"""Valid video provider names usable with the ``--provider`` CLI flag.
'gemini' is a backward-compatible alias for 'google'."""

DEFAULT_OPENROUTER_VIDEO_MODEL = "minimax/hailuo-3"
"""Default OpenRouter video model (MiniMax H3)."""

DEFAULT_OPENROUTER_RESOLUTION = "768p"
"""Output resolution requested for the OpenRouter video provider (MiniMax H3)."""

DEFAULT_MINIMAX_VIDEO_MODEL = "MiniMax-H3"
"""Default MiniMax video model (H3), used directly via the MiniMax API."""

DEFAULT_MINIMAX_RESOLUTION = "768P"
"""Output resolution requested for the MiniMax video provider (MiniMax H3)."""

DEFAULT_DURATION_SECONDS = 10
DEFAULT_RESOLUTION = RESOLUTION
DEFAULT_ASPECT_RATIO = get_aspect_ratio(ASPECT)
DEFAULT_SCRIPTS_DIR = Path("out") / "scripts"
DEFAULT_BLUEPRINT_DIR = Path("out") / "blueprint"
DEFAULT_ANIMATIONS_DIR = Path("out") / "animations"
DEFAULT_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5

FULL_VIDEO_NAME = "full.mp4"
TRANSITION_SECONDS = 0.5
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

CLOSING_MESSAGE = (
    "MANDATORY CLOSING FRAME: the attached reference image is the opening frame "
    "of the next shot, and it IS the final frame of your output. The very last "
    "frame of the generated video must be a pixel-faithful reproduction of this "
    "exact image. This applies to EVERYTHING in the frame — the characters "
    "(design, pose, expression, scale) AND the entire background scene: the "
    "exact same set, architecture, props, spatial layout, lighting, and color "
    "palette. The environment is the identical physical space continuing across "
    "shots and must be inherited from this reference — never redesigned, "
    "repainted, relocated, re-dressed, or re-lit. Do NOT reinterpret, re-frame, "
    "re-light, re-angle, zoom, or redesign any element. All motion must resolve "
    "into this exact state, with the characters moving within the SAME "
    "unchanged background, and hand off the action seamlessly to it. "
    "This requirement overrides any conflicting framing described elsewhere."
)
