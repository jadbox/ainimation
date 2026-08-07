"""Multi-film project layout helpers.

Each film lives in its own folder under ``films/<film>/`` containing its
``movie.yml`` (the single source of truth for story, style, characters, and
scenes) and rendered ``out/`` assets. All pipeline tools
accept a ``--film`` flag (or the ``FILM`` environment variable) to select
which film to work on; the default is the first film under ``films/``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILMS_DIR = PROJECT_ROOT / "films"


def list_films() -> list[str]:
    """Return the sorted names of films that have a ``movie.yml``."""
    if not FILMS_DIR.is_dir():
        return []
    return sorted(
        entry.name
        for entry in FILMS_DIR.iterdir()
        if entry.is_dir() and (entry / "movie.yml").is_file()
    )


def default_film() -> str:
    """Return the default film: the first available film folder."""
    available = list_films()
    if not available:
        raise ValueError(f"No films found in {FILMS_DIR}: create films/<slug>/movie.yml.")
    return available[0]


def resolve_film(name: str | None = None) -> str:
    """Resolve a film name, falling back to ``$FILM`` then the default.

    Raises ``ValueError`` when the resolved film folder does not exist.
    """
    film = (name or os.environ.get("FILM") or default_film()).strip()
    available = list_films()
    if film not in available:
        listing = ", ".join(available) if available else "(none found)"
        raise ValueError(
            f"Unknown film {film!r}. Available films in {FILMS_DIR}: {listing}."
        )
    return film


def select_film_from_argv(argv: list[str] | None = None) -> str:
    """Apply a ``--film`` flag from the command line to the process.

    Scans ``argv`` (default: ``sys.argv[1:]``) for ``--film`` without
    consuming any other arguments, then calls :func:`set_film` on the
    resolved name so every later ``movie_config`` lookup targets it.
    Returns the resolved film name.
    """
    args = sys.argv[1:] if argv is None else argv
    film: str | None = None
    for index, arg in enumerate(args):
        if arg == "--film" and index + 1 < len(args):
            film = args[index + 1]
            break
        if arg.startswith("--film="):
            film = arg.split("=", 1)[1]
            break
    from movie_config import set_film

    return set_film(film)


def film_dir(film: str) -> Path:
    return FILMS_DIR / film


def film_movie_yml(film: str) -> Path:
    return FILMS_DIR / film / "movie.yml"


def film_out_dir(film: str) -> Path:
    return FILMS_DIR / film / "out"


def film_scripts_dir(film: str) -> Path:
    return film_out_dir(film) / "scripts"


def film_blueprint_dir(film: str) -> Path:
    return film_out_dir(film) / "blueprint"


def film_animations_dir(film: str) -> Path:
    return film_out_dir(film) / "animations"
