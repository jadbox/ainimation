"""Scene script parsing and character blueprint lookup utilities."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from blueprint_generator import slug
from blueprint_generator.utils.characters import CHARACTERS

from animator.models import SceneSegment

logger = logging.getLogger("animator.script")

SEGMENT_HEADER_RE = re.compile(
    r"^##\s+Segment\s+(\d+)\s*\(([^)]*)\)\s*$",
    flags=re.MULTILINE | re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Normalize a character name for fuzzy roster matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_scene_characters(script: str) -> list[str]:
    """Extract roster character names from the '## Characters in Scene' section."""
    match = re.search(r"^##\s*Characters in Scene\s*$", script, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        raise RuntimeError(
            "Scene script has no '## Characters in Scene' section. "
            "Regenerate it with src/scene_script.py."
        )
    section_lines: list[str] = []
    for line in script[match.end():].splitlines():
        if line.strip().startswith("##"):
            break
        section_lines.append(line)

    roster = {normalize_name(spec.name): spec.name for spec in CHARACTERS.values()}
    found: list[str] = []
    for line in section_lines:
        bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s*(.+?)\s*$", line)
        if not bullet:
            continue
        candidate = normalize_name(bullet.group(1))
        if candidate in roster and roster[candidate] not in found:
            found.append(roster[candidate])
    if not found:
        raise RuntimeError(
            "No roster characters found in the '## Characters in Scene' section. "
            f"Available characters: {', '.join(spec.name for spec in CHARACTERS.values())}."
        )
    return found


def parse_global_section(script: str, header_pattern: str) -> str:
    """Extract the body of a scene-wide ``##`` section (e.g. Logline, Setting).

    ``header_pattern`` is a case-insensitive regex matched against the header
    text. Returns an empty string when the section is absent.
    """
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
    """Split a scene script into its marked 10-second segments.

    Scripts without ``## Segment N (...)`` headers are treated as a single
    segment (index 0) covering the whole script.
    """
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
    indices = [segment.index for segment in segments]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise RuntimeError(
            f"Segment indices in the scene script are not contiguous: {indices}."
        )
    logger.info(
        "Parsed %d scene segment(s): %s",
        len(segments),
        ", ".join(f"Segment {s.index} ({s.span or 'whole script'})" for s in segments),
    )
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
