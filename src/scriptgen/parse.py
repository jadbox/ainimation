"""Parsing helpers for generated scene documents in :mod:`scriptgen`."""

from __future__ import annotations

import re
from pathlib import Path

from movie_config import CHARACTERS, standardize_name


def slugify_name(name: str) -> str:
    """Validate/normalize a scene name into a filesystem-safe slug."""
    slug = name.strip().lower().replace(" ", "-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
        raise ValueError(
            f"Scene name {name!r} must start with a letter or digit and contain "
            "only lowercase letters, digits, hyphens, and underscores."
        )
    return slug


def parse_section(document: str, header_pattern: str) -> str:
    """Extract body text from a section heading matching header_pattern."""
    match = re.search(
        rf"^##\s+{header_pattern}\s*$", document, flags=re.MULTILINE | re.IGNORECASE
    )
    if not match:
        return ""
    body = document[match.end():]
    next_heading = re.search(r"^##\s", body, flags=re.MULTILINE)
    if next_heading:
        body = body[: next_heading.start()]
    return body.strip()


def parse_characters_in_scene(document: str) -> list[str]:
    """Extract roster character names from '## Characters in Scene'."""
    match = re.search(
        r"^##\s*Characters in Scene\s*$", document, flags=re.MULTILINE | re.IGNORECASE
    )
    if not match:
        return []
    section_lines: list[str] = []
    for line in document[match.end():].splitlines():
        if line.strip().startswith("##"):
            break
        section_lines.append(line)

    roster = {standardize_name(spec.name): spec.name for spec in CHARACTERS.values()}
    found: list[str] = []
    for line in section_lines:
        bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s*(.+?)\s*$", line)
        if not bullet:
            continue
        cleaned = re.sub(r"<VOICE>.*?</VOICE>", "", bullet.group(1), flags=re.IGNORECASE)
        candidate = standardize_name(cleaned)
        if candidate in roster and roster[candidate] not in found:
            found.append(roster[candidate])
    return found


def parse_segments_from_document(document: str) -> list[tuple[int, str, str]]:
    """Extract (index, span, body) tuples for each segment in document."""
    header_re = re.compile(
        r"^##\s+Segment\s+(\d+)\s*\(([^)]*)\)\s*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    matches = list(header_re.finditer(document))
    if not matches:
        return [(0, "0:00-0:30", document.strip())]

    segments: list[tuple[int, str, str]] = []
    for position, match in enumerate(matches):
        idx = int(match.group(1))
        span = match.group(2).strip()
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(document)
        body = document[start:end]
        next_heading = re.search(r"^##\s", body, flags=re.MULTILINE)
        if next_heading:
            body = body[: next_heading.start()]
        segments.append((idx, span, body.strip()))

    segments.sort(key=lambda s: s[0])
    return segments


def part_index_from_path(path: Path) -> int:
    """Extract the segment index from a ``<base>_part<N>.md`` path."""
    match = re.search(r"_part(\d+)\.md$", path.name)
    if not match:
        raise ValueError(f"Cannot determine part index from path: {path}")
    return int(match.group(1))


def part_file_path(base_path: Path, idx: int) -> Path:
    """Return the file path for a scene segment part index."""
    return Path(f"{base_path}_part{idx}.md")


def extract_segment_body(part_content: str) -> str:
    """Extract the segment body from a saved part file.

    The body is everything from the first MiniMax core field label
    (``integrated_multimodal_description:``) to the end of the file.
    """
    lines = part_content.splitlines()
    body_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("integrated_multimodal_description:"):
            body_start = i
            break
    if body_start is None:
        return part_content.strip()
    return "\n".join(lines[body_start:]).strip()


def parse_part_file(content: str) -> tuple[str, str, list[str], str]:
    """Parse a saved part file into (logline, setting, characters, segment_body)."""
    logline = ""
    match = re.search(r'^Scene: "[^"]*"\s*—\s*(.*)$', content, flags=re.MULTILINE)
    if match:
        logline = match.group(1).strip()

    setting = ""
    match = re.search(
        r"^=== SHARED SETTING & LIGHT[^\n]*\n(.*?)^integrated_multimodal_description:",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match:
        setting = match.group(1).strip()

    characters: list[str] = []
    match = re.search(
        r"^Characters appearing:\s*(.+?)\s*\.?\s*$",
        content,
        flags=re.MULTILINE,
    )
    if match:
        # Strip <VOICE>...</VOICE> tags before splitting on commas — voice
        # descriptions contain commas that are not character separators.
        cleaned = re.sub(r"<VOICE>.*?</VOICE>", "", match.group(1), flags=re.IGNORECASE)
        for chunk in cleaned.split(","):
            name = standardize_name(chunk)
            if name:
                characters.append(name)

    return logline, setting, characters, extract_segment_body(content)