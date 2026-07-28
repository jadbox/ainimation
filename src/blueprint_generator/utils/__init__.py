"""Blueprint generator utility modules."""

from __future__ import annotations

from blueprint_generator.utils.characters import (
    CHARACTERS,
    CharacterSpec,
    get_character,
    list_character_names,
)
from blueprint_generator.utils.env import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_REVIEW_MODEL,
    MAX_ITERATIONS,
    REVIEW_MODEL_GEMINI_FLASH_3_6,
    REVIEW_MODEL_KIMI_K3,
    require_environment,
)
from blueprint_generator.utils.image import generate_image, save_jpeg, to_jpeg
from blueprint_generator.utils.models import Attempt, Subject
from blueprint_generator.utils.prompts import (
    build_history_context,
    build_initial_prompt,
    build_review_system_instruction,
    build_scene_initial_prompt,
    build_scene_review_system_instruction,
    build_subjects,
    fallback_revision,
)
from blueprint_generator.utils.reviewer import review_image, write_iterations
from blueprint_generator.utils.scenes import (
    SCENES,
    BackgroundSpec,
    SceneSpec,
    get_scene,
    list_scene_names,
)

__all__ = [
    "CHARACTERS",
    "DEFAULT_IMAGE_MODEL",
    "DEFAULT_REVIEW_MODEL",
    "MAX_ITERATIONS",
    "REVIEW_MODEL_GEMINI_FLASH_3_6",
    "REVIEW_MODEL_KIMI_K3",
    "SCENES",
    "Attempt",
    "BackgroundSpec",
    "CharacterSpec",
    "SceneSpec",
    "Subject",
    "build_history_context",
    "build_initial_prompt",
    "build_review_system_instruction",
    "build_scene_initial_prompt",
    "build_scene_review_system_instruction",
    "build_subjects",
    "fallback_revision",
    "generate_image",
    "get_character",
    "get_scene",
    "list_character_names",
    "list_scene_names",
    "require_environment",
    "review_image",
    "save_jpeg",
    "to_jpeg",
    "write_iterations",
]
