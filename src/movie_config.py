"""Movie configuration loader for story, character, scene, and style specifications."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from films import film_movie_yml, resolve_film

DEFAULT_ORIENTATION = "16:9"
"""Default film orientation (aspect ratio) when movie.yml omits ``orientation``."""


def standardize_name(name: str) -> str:
    """Standardize a character name to ALL CAPS with no punctuation marks."""
    clean = re.sub(r"[^\w\s]", "", name)
    return " ".join(clean.split()).upper()


@dataclass(frozen=True)
class StyleChecklistItem:
    """A single do/don't style-checklist entry from the film's style bible."""

    category: str
    do: str
    don_t: str


@dataclass(frozen=True)
class MovieInfo:
    """Movie and visual style metadata."""

    title: str
    headline: str
    style: str
    camera_rules: str
    hard_direction_rules: tuple[str, ...]
    orientation: str = DEFAULT_ORIENTATION
    style_checklist: tuple[StyleChecklistItem, ...] = ()
    prompt_template: str = ""


@dataclass(frozen=True)
class CharacterSpec:
    """A single character blueprint spec."""

    name: str
    species: str
    identity: str
    appearance: str
    voice: str = ""
    avoid: str = ""

    def display_name(self) -> str:
        return standardize_name(self.name)


@dataclass(frozen=True)
class BackgroundSpec:
    """A single background plate within a scene."""

    key: str
    description: str
    lighting: str
    mood: str


@dataclass(frozen=True)
class SceneSpec:
    """A scene blueprint containing background plates."""

    name: str
    slug: str
    logline: str
    backgrounds: tuple[BackgroundSpec, ...]


@dataclass(frozen=True)
class StorySceneSpec:
    """An abridged story beat that ``scriptgen`` expands into a full scene design."""

    name: str
    title: str
    scene: str
    characters: tuple[str, ...]
    emotions: tuple[str, ...]
    actions: tuple[str, ...]
    looks: tuple[str, ...]


def _find_movie_file() -> Path:
    env_path = os.environ.get("MOVIE_YML_PATH")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
    candidate = film_movie_yml(_FILM)
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(
        f"movie.yml not found for film {_FILM!r} (expected at {candidate})."
    )


def load_movie_config(
    path: Path | None = None,
) -> tuple[MovieInfo, dict[str, CharacterSpec], dict[str, SceneSpec], dict[str, StorySceneSpec]]:
    movie_path = path or _find_movie_file()
    with movie_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    movie_raw = raw.get("movie", {})
    movie_info = MovieInfo(
        title=movie_raw.get("title", ""),
        headline=movie_raw.get("headline", ""),
        style=movie_raw.get("style", ""),
        camera_rules=movie_raw.get("camera_rules", ""),
        hard_direction_rules=tuple(movie_raw.get("hard_direction_rules", [])),
        orientation=movie_raw.get("orientation", DEFAULT_ORIENTATION),
        style_checklist=tuple(
            StyleChecklistItem(
                category=item.get("category", ""),
                do=item.get("do", ""),
                don_t=item.get("don_t", ""),
            )
            for item in movie_raw.get("style_checklist", [])
        ),
        prompt_template=movie_raw.get("prompt_template", ""),
    )

    characters: dict[str, CharacterSpec] = {}
    for char_raw in raw.get("characters", []):
        spec = CharacterSpec(
            name=char_raw["name"],
            species=char_raw.get("species", ""),
            identity=char_raw.get("identity", ""),
            appearance=char_raw.get("appearance", ""),
            voice=char_raw.get("voice", ""),
            avoid=char_raw.get("avoid", ""),
        )
        characters[spec.name.lower()] = spec

    scenes: dict[str, SceneSpec] = {}
    for scene_raw in raw.get("scenes", []):
        backgrounds = tuple(
            BackgroundSpec(
                key=bg["key"],
                description=bg["description"],
                lighting=bg["lighting"],
                mood=bg["mood"],
            )
            for bg in scene_raw.get("backgrounds", [])
        )
        spec = SceneSpec(
            name=scene_raw["name"],
            slug=scene_raw["slug"],
            logline=scene_raw.get("logline", ""),
            backgrounds=backgrounds,
        )
        scenes[spec.slug] = spec

    story: dict[str, StorySceneSpec] = {}
    for story_raw in raw.get("story", []):
        spec = StorySceneSpec(
            name=story_raw["name"],
            title=story_raw.get("title", ""),
            scene=story_raw.get("scene", ""),
            characters=tuple(story_raw.get("characters", [])),
            emotions=tuple(story_raw.get("emotions", [])),
            actions=tuple(story_raw.get("actions", [])),
            looks=tuple(story_raw.get("looks", [])),
        )
        story[spec.name] = spec

    return movie_info, characters, scenes, story


_FILM = resolve_film()
_MOVIE_INFO, CHARACTERS, SCENES, STORY = load_movie_config()


def get_film() -> str:
    """Return the film slug all movie_config lookups currently target."""
    return _FILM


def set_film(name: str | None = None) -> str:
    """Point all movie_config lookups at ``films/<name>/movie.yml``.

    ``None`` falls back to the ``FILM`` environment variable, then the
    default film. Reloading mutates the shared ``CHARACTERS``/``SCENES``/
    ``STORY`` dicts in place so every importer sees the new film's data.
    Returns the resolved film slug.
    """
    global _MOVIE_INFO, _FILM
    film = resolve_film(name)
    if film != _FILM or not CHARACTERS:
        _FILM = film
        movie_info, characters, scenes, story = load_movie_config()
        _MOVIE_INFO = movie_info
        CHARACTERS.clear()
        CHARACTERS.update(characters)
        SCENES.clear()
        SCENES.update(scenes)
        STORY.clear()
        STORY.update(story)
    return film


def get_movie_info() -> MovieInfo:
    return _MOVIE_INFO


def list_character_names() -> list[str]:
    return [spec.display_name() for spec in CHARACTERS.values()]


def get_character(name: str) -> CharacterSpec:
    key = name.strip().lower()
    if key in CHARACTERS:
        return CHARACTERS[key]
    clean = standardize_name(name).lower()
    for spec in CHARACTERS.values():
        if standardize_name(spec.name).lower() == clean:
            return spec
    available = ", ".join(list_character_names())
    raise ValueError(f"No character named {name!r}. Available characters: {available}.")


def list_scene_names() -> list[str]:
    return [spec.name for spec in SCENES.values()]


def get_scene(name: str) -> SceneSpec:
    from blueprint_generator import slug

    key = slug(name.strip())
    if key in SCENES:
        return SCENES[key]
    normalized = "".join(ch for ch in name.lower() if ch.isalnum())
    for spec in SCENES.values():
        if normalized == "".join(ch for ch in spec.name.lower() if ch.isalnum()):
            return spec
    available = ", ".join(f"{spec.name} ({spec.slug})" for spec in SCENES.values())
    raise ValueError(f"No scene named {name!r}. Available scenes: {available}.")


def list_story_scenes() -> list[StorySceneSpec]:
    return list(STORY.values())


def get_story_scene(name: str) -> StorySceneSpec:
    key = name.strip().lower().replace(" ", "-")
    if key in STORY:
        return STORY[key]
    normalized = "".join(ch for ch in name.lower() if ch.isalnum())
    for spec in STORY.values():
        if normalized == "".join(ch for ch in spec.name.lower() if ch.isalnum()):
            return spec
    available = ", ".join(spec.name for spec in STORY.values())
    raise ValueError(f"No story scene named {name!r}. Available story scenes: {available}.")
