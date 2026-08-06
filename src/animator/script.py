"""Scene script parsing and character blueprint lookup utilities."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from blueprint_generator import slug
from blueprint_generator.utils.characters import CHARACTERS
from movie_config import standardize_name

from animator.models import SceneSegment

logger = logging.getLogger("animator.script")

SEGMENT_HEADER_RE = re.compile(
    r"^##\s+Segment\s+(\d+)\s*\(([^)]*)\)\s*$",
    flags=re.MULTILINE | re.IGNORECASE,
)

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)


def strip_html_comments(script: str) -> str:
    """Remove ``<!-- ... -->`` comment blocks (e.g. scriptgen's header) from script text."""
    return HTML_COMMENT_RE.sub("", script).strip()


def normalize_name(name: str) -> str:
    """Normalize a character name for fuzzy roster matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_scene_part_scripts(scripts_dir: Path, scene_name: str) -> list[tuple[int, Path]]:
    """Find all matching part script files for scene_name in scripts_dir.

    Looks for files named ``<scene_name>_part<N>.md``.
    Returns a list of ``(index, path)`` sorted by index.
    """
    pattern = re.compile(rf"^{re.escape(scene_name)}_part(\d+)\.md$", re.IGNORECASE)
    found: list[tuple[int, Path]] = []
    if not scripts_dir.exists():
        return found
    for path in scripts_dir.iterdir():
        if path.is_file():
            match = pattern.match(path.name)
            if match:
                idx = int(match.group(1))
                found.append((idx, path))
    found.sort(key=lambda item: item[0])
    return found


def parse_scene_characters(script_text: str) -> list[str]:
    """Extract roster character names from prompt or script text."""
    roster = {normalize_name(spec.name): spec.name for spec in CHARACTERS.values()}
    found: list[str] = []

    match = re.search(r"Characters appearing:\s*([^.\n]+)", script_text, flags=re.IGNORECASE)
    if match:
        line = match.group(1)
        cleaned = re.sub(r"<VOICE>.*?</VOICE>", "", line, flags=re.IGNORECASE)
        for spec in CHARACTERS.values():
            if normalize_name(spec.name) in normalize_name(cleaned):
                if spec.name not in found:
                    found.append(spec.name)

    if not found:
        # Fallback to searching entire text
        norm_text = normalize_name(script_text)
        for spec in CHARACTERS.values():
            if normalize_name(spec.name) in norm_text:
                if spec.name not in found:
                    found.append(spec.name)

    return found


def parse_global_section(script: str, header_pattern: str) -> str:
    """Extract the body of a scene-wide ``##`` section (e.g. Logline, Setting)."""
    match = re.search(
        rf"^##\s+{header_pattern}\s*$", script, flags=re.MULTILINE | re.IGNORECASE
    )
    if not match:
        return ""
    body = script[match.end():]
    next_heading = re.search(r"^##\s", body, flags=re.MULTILINE)
    if next_heading:
        body = body[: next_heading.start()]
    return body.strip()


def parse_segments(script: str) -> list[SceneSegment]:
    """Split a scene script into its marked 10-second segments."""
    matches = list(SEGMENT_HEADER_RE.finditer(script))
    if not matches:
        logger.info("No segment headers found; treating the whole script as one segment.")
        return [SceneSegment(index=0, span="", body=script.strip())]

    segments: list[SceneSegment] = []
    for position, match in enumerate(matches):
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(script)
        body = script[start:end]
        next_heading = re.search(r"^##\s", body, flags=re.MULTILINE)
        if next_heading:
            body = body[: next_heading.start()]
        segments.append(
            SceneSegment(index=int(match.group(1)), span=match.group(2).strip(), body=body.strip())
        )

    segments.sort(key=lambda segment: segment.index)
    return segments


def latest_attempt_image(character_name: str, blueprint_dir: Path) -> Path:
    """Return the last attempt-*.jpg in the character's blueprint folder."""
    folder = blueprint_dir / slug(character_name)
    attempts = sorted(folder.glob("attempt-*.jpg"))
    if not attempts:
        raise RuntimeError(
            f"No attempt-*.jpg found in {folder} for {character_name!r}. "
            f"Run `uv run generate-character --character \"{character_name}\"` first."
        )
    return attempts[-1]

