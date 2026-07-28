"""Scene background specifications loaded dynamically from movie.yml for blueprint generation."""

from __future__ import annotations

from movie_config import (
    SCENES,
    BackgroundSpec,
    SceneSpec,
    get_scene,
    list_scene_names,
)

__all__ = [
    "SCENES",
    "BackgroundSpec",
    "SceneSpec",
    "get_scene",
    "list_scene_names",
]
