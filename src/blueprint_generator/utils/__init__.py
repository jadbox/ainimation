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
    IMAGE_MODEL_NANO_BANANA_2,
    require_environment,
)
from blueprint_generator.utils.image import generate_image, save_jpeg, to_jpeg
from blueprint_generator.utils.models import Subject
from blueprint_generator.utils.prompts import (
    build_initial_prompt,
    build_scene_initial_prompt,
    build_subjects,
)
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
    "IMAGE_MODEL_NANO_BANANA_2",
    "SCENES",
    "BackgroundSpec",
    "CharacterSpec",
    "SceneSpec",
    "Subject",
    "build_initial_prompt",
    "build_scene_initial_prompt",
    "build_subjects",
    "generate_image",
    "get_character",
    "get_scene",
    "list_character_names",
    "list_scene_names",
    "require_environment",
    "save_jpeg",
    "to_jpeg",
]
