"""Character specifications loaded dynamically from movie.yml for blueprint generation."""

from __future__ import annotations

from movie_config import (
    CHARACTERS,
    CharacterSpec,
    get_character,
    list_character_names,
)

__all__ = [
    "CHARACTERS",
    "CharacterSpec",
    "get_character",
    "list_character_names",
]
