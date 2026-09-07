"""Configuration constants for scene script animation."""

from __future__ import annotations

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


DEFAULT_GOOGLE_VIDEO_MODEL = "gemini-omni-1.1-flash"
"""Default video model for the Gemini provider (Google Gemini Omni 1.1 Flash)."""

SUPPORTED_GOOGLE_RESOLUTIONS = ("360p", "720p", "1080p", "4k")
"""Output resolutions accepted by Gemini Omni's ``response_format``."""

DEFAULT_GOOGLE_RESOLUTION = "720p"
"""Default output resolution for the Gemini provider (Omni 1.1 default)."""

DEFAULT_VIDEO_PROVIDER = "minimax"
"""Default video generation provider (MiniMax H3 via the MiniMax API directly).
Options: 'google' (or its 'gemini' alias), 'openrouter', 'minimax' or 'fal'."""

VIDEO_PROVIDERS = ("google", "openrouter", "minimax", "gemini", "fal")
"""Canonical video provider names. 'gemini' is a backward-compatible alias for
'google'. See :data:`MODEL_SHORTCUTS` and :func:`parse_model_spec` for the
unified ``--model provider:model`` interface."""

DEFAULT_OPENROUTER_VIDEO_MODEL = "alibaba/wan-3.0"
"""Default OpenRouter video model (Alibaba Wan 3.0)."""

DEFAULT_OPENROUTER_RESOLUTION = "480p"
"""Output resolution requested for the OpenRouter video provider (Alibaba Wan 3.0 at 480p)."""

DEFAULT_MINIMAX_VIDEO_MODEL = "MiniMax-H3"
"""Default MiniMax video model (H3), used directly via the MiniMax API."""

DEFAULT_MINIMAX_RESOLUTION = "768P"
"""Output resolution requested for the MiniMax video provider (MiniMax H3)."""

DEFAULT_FAL_VIDEO_MODEL = "minimax/h3-max/image-to-video"
"""Default Fal.ai video model (MiniMax H3 Max image-to-video)."""

DEFAULT_FAL_RESOLUTION = "480P"
"""Default output resolution for the Fal provider (480P)."""

PROVIDER_ALIASES = {"gemini": "google"}
"""Alternative provider names accepted in model specs, mapped to canonical names."""

MODEL_SHORTCUTS = {
    "google": f"google:{DEFAULT_GOOGLE_VIDEO_MODEL}",
    "gemini": f"google:{DEFAULT_GOOGLE_VIDEO_MODEL}",
    "minimax": f"minimax:{DEFAULT_MINIMAX_VIDEO_MODEL}",
    "openrouter": f"openrouter:{DEFAULT_OPENROUTER_VIDEO_MODEL}",
    "fal": f"fal:{DEFAULT_FAL_VIDEO_MODEL}",
}
"""Bare ``--model`` shortcuts expanded to canonical ``provider:model`` specs."""

DEFAULT_MODEL_SPEC = MODEL_SHORTCUTS[DEFAULT_VIDEO_PROVIDER]
"""Default model spec: MiniMax H3 via the MiniMax API (``minimax:MiniMax-H3``)."""


def parse_model_spec(spec: str | None = None) -> tuple[str, str]:
    """Resolve a ``--model`` value into a ``(provider, model_id)`` pair.

    Accepts a ``provider:model`` spec (e.g. ``openrouter:alibaba/wan-3.0``),
    a bare shortcut (``google``, ``gemini``, ``minimax``, ``openrouter``, ``fal``),
    or a bare model ID (assumed to belong to the default provider). Raises
    :class:`ValueError` on an unknown provider prefix or an empty model ID.
    """
    value = (spec or DEFAULT_MODEL_SPEC).strip()
    if not value:
        value = DEFAULT_MODEL_SPEC
    if ":" not in value:
        shortcut = MODEL_SHORTCUTS.get(value.lower())
        if shortcut:
            value = shortcut
        else:
            value = f"{DEFAULT_VIDEO_PROVIDER}:{value}"
    provider, _, model = value.partition(":")
    provider = PROVIDER_ALIASES.get(provider.lower(), provider.lower())
    if provider not in ("google", "minimax", "openrouter", "fal"):
        shortcuts = ", ".join(f"'{k}'" for k in ("google", "minimax", "openrouter", "fal"))
        raise ValueError(
            f"Unknown video provider {provider!r} in --model {spec!r}. "
            f"Use a 'provider:model' spec or one of the shortcuts {shortcuts} "
            "(e.g. 'openrouter:alibaba/wan-3.0', 'fal:minimax/h3-max/reference-to-video')."
        )
    if not model:
        raise ValueError(f"Missing model ID after ':' in --model {spec!r}.")
    return provider, model

DEFAULT_DURATION_SECONDS = 5
DEFAULT_RESOLUTION = RESOLUTION
DEFAULT_ASPECT_RATIO = get_aspect_ratio(ASPECT)
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
