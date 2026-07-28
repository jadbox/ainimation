#!/usr/bin/env python3
"""Animate a scene script into 720p clips with Gemini Omni Flash.

Reads the scene design document at ``out/scripts/<scene>.md`` (produced by
``src/scene_script.py``), collects the final character blueprint images for
just the characters appearing in the scene (the last ``attempt-*.jpg`` in each
character's ``out/blueprint/<character-slug>/`` folder), and sends the script
plus reference images to Google Gemini Omni Flash.

The scene script is split into clearly marked 10-second segments
(``## Segment 0 (0:00-0:10)`` ...). Each segment is self-contained (its own
blocking, camera, animation, dialogue, and sound/music sub-sections); the
video prompt for a part contains ONLY the shared ``## Setting & Light``
section plus that one segment, so the model is never confused by other
segments. Each segment is generated as its own 10-second, 720p, 24fps clip and
saved to ``out/animations/<scene>/part-<N>.mp4``. Use ``--parts N`` to generate
only one segment; without it, every missing segment is generated. When all
segments are present in the output folder at the end of a run, they are
concatenated (in order) into ``out/animations/<scene>/full.mp4``.

Usage:
    python src/animator.py --scene frisby_meets_greatowl            # all missing parts
    python src/animator.py --scene frisby_meets_greatowl --parts 2  # only the 3rd segment

Continuity: after each part clip is written, its last frame is extracted to
``part-<N>.jpg`` (requires ffmpeg). When generating segment N, if
``part-<N-1>.jpg`` exists it is sent as an extra reference image with an
instruction to continue the video from that exact frame, so consecutive
segments match in look, composition, and pose.
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from google import genai

from blueprint_generator import slug
from blueprint_generator.characters import CHARACTERS

logger = logging.getLogger("animator")

DEFAULT_VIDEO_MODEL = "gemini-omni-flash-preview"
DEFAULT_DURATION_SECONDS = 10
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_SCRIPTS_DIR = Path("out") / "scripts"
DEFAULT_BLUEPRINT_DIR = Path("out") / "blueprint"
DEFAULT_ANIMATIONS_DIR = Path("out") / "animations"
DEFAULT_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5

SEGMENT_HEADER_RE = re.compile(
    r"^##\s+Segment\s+(\d+)\s*\(([^)]*)\)\s*$",
    flags=re.MULTILINE | re.IGNORECASE,
)
FULL_VIDEO_NAME = "full.mp4"

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


@dataclass(frozen=True)
class SceneSegment:
    """One 10-second segment of a scene script."""

    index: int
    span: str
    """The time span written in the header, e.g. ``0:10-0:20`` (may be empty)."""
    body: str


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


def build_direction(
    scene_name: str,
    logline: str,
    setting: str,
    segment: SceneSegment,
    characters: list[str],
    duration: int,
    has_continuity: bool = False,
) -> str:
    span_note = f" (story time {segment.span})" if segment.span else ""
    setting_block = (
        f"=== SHARED SETTING & LIGHT (constant across the whole scene) ===\n{setting}\n\n"
        if setting
        else ""
    )
    if has_continuity:
        opening_instruction = (
            "The final attached reference image is the mandatory opening frame "
            "of this video: reproduce it exactly as frame 0 — the characters AND "
            "the background scene alike (see the MANDATORY OPENING FRAME "
            "instruction below) — then end on a clean held final pose. The "
            "background must remain the exact same set, with the same props, "
            "layout, and lighting, throughout the clip."
        )
    else:
        opening_instruction = (
            "Begin from the exact starting pose/composition stated in the Shot "
            "Steps and end on a clean held final pose."
        )
    return f"""Animate one continuous {duration}-second, 720p, 24fps, 16:9 hand-painted 2D cel
animation clip in the style of a 1982 Don Bluth feature (The Secret of NIMH):
hand-inked tapered lines, 2-tone cel shading, painterly gouache backgrounds,
warm amber key light against deep teal/indigo shadow, 360-degree rim lighting,
heavy vignette, soft-focus dark foreground occlusion on 20-30% of the frame
borders, film grain.

Scene: "{scene_name}" — {logline or 'see script below.'}

Characters appearing (reference images attached, in order): {", ".join(characters)}.
Match each character's design EXACTLY to its reference image — same fur colors,
garment, eyes, and proportions. Keep the camera at rodent eye-level
(2-12 inches high) around a single dominant practical light source.
{opening_instruction}

{setting_block}=== SCENE SCRIPT{span_note} ===
{segment.body}"""


def build_input_items(
    direction: str,
    references: list[tuple[str, Path]],
    continuity_frame: Path | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [{"type": "text", "text": direction}]
    for character_name, image_path in references:
        items.append({"type": "text", "text": f"Character reference image: {character_name}"})
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(image_path.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    if continuity_frame is not None:
        items.append({"type": "text", "text": CONTINUITY_MESSAGE})
        items.append(
            {
                "type": "image",
                "data": base64.b64encode(continuity_frame.read_bytes()).decode("utf-8"),
                "mime_type": "image/jpeg",
            }
        )
    return items


def create_video_interaction(
    client: genai.Client,
    model: str,
    input_items: list[dict[str, Any]],
    duration: int,
) -> Any:
    """Request the video from Omni Flash, falling back to a minimal request.

    The full request asks for the reference_to_video task with an inline 16:9
    video response; if the API rejects those parameters, retry with just the
    model and input (the documented minimal usage).
    """
    logger.info("Requesting video generation from model=%s ...", model)
    t0 = time.monotonic()
    try:
        interaction = client.interactions.create(
            model=model,
            input=input_items,
            response_modalities=["video"],
            generation_config={"video_config": {"task": "reference_to_video"}},
            response_format={
                "type": "video",
                "aspect_ratio": DEFAULT_ASPECT_RATIO,
                "delivery": "inline",
                "duration": f"{duration}s",
            },
        )
    except Exception as error:
        logger.warning(
            "Full video request was rejected (%s: %s). Retrying with the minimal "
            "model+input request.", type(error).__name__, error,
        )
        interaction = client.interactions.create(model=model, input=input_items)
    logger.info("Video request accepted in %.1fs (interaction id: %s, status: %s)",
                time.monotonic() - t0,
                getattr(interaction, "id", None), getattr(interaction, "status", None))
    return interaction


def wait_for_completion(client: genai.Client, interaction: Any, timeout: int) -> Any:
    """Poll the interaction until it completes, fails, or the timeout elapses."""
    terminal_ok = {"completed"}
    terminal_bad = {"failed", "cancelled", "incomplete", "budget_exceeded"}
    deadline = time.monotonic() + timeout
    while getattr(interaction, "status", None) not in terminal_ok | terminal_bad:
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Video generation did not finish within {timeout}s "
                f"(interaction id: {getattr(interaction, 'id', None)})."
            )
        logger.info("Status: %s — polling again in %ds ...",
                    getattr(interaction, "status", "unknown"), POLL_INTERVAL_SECONDS)
        time.sleep(POLL_INTERVAL_SECONDS)
        interaction = client.interactions.get(interaction.id)
    status = getattr(interaction, "status", None)
    if status in terminal_bad:
        raise RuntimeError(f"Video generation ended with status {status!r}.")
    return interaction


def extract_video_bytes(interaction: Any) -> bytes:
    video = getattr(interaction, "output_video", None)
    if video is None:
        raise RuntimeError("Gemini Omni Flash returned no output video.")
    data = getattr(video, "data", None)
    if data:
        return base64.b64decode(data)
    uri = getattr(video, "uri", None)
    if uri:
        logger.info("Downloading generated video from %s ...", uri)
        response = requests.get(uri, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(f"Could not download generated video ({response.status_code}).")
        return response.content
    raise RuntimeError("Gemini Omni Flash returned a video with neither data nor a URI.")


def part_path(scene_dir: Path, segment: SceneSegment) -> Path:
    return scene_dir / f"part-{segment.index}.mp4"


def frame_path(scene_dir: Path, segment_index: int) -> Path:
    return scene_dir / f"part-{segment_index}.jpg"


def extract_last_frame(video_path: Path, destination: Path) -> bool:
    """Extract the last frame of a clip to a JPEG next to it (requires ffmpeg)."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found; cannot extract the last frame of %s.", video_path)
        return False
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-sseof", "-0.1",
                "-i", video_path.name,
                "-frames:v", "1",
                "-q:v", "2",
                destination.name,
            ],
            cwd=video_path.parent,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        logger.warning("ffmpeg failed to extract the last frame of %s:\n%s",
                       video_path, error.stderr)
        return False
    logger.info("Saved last frame: %s", destination)
    return True


def previous_frame(scene_dir: Path, segment: SceneSegment) -> Path | None:
    """Return the previous segment's last-frame image for continuity, if available.

    Falls back to extracting it from the previous segment's existing clip.
    """
    if segment.index == 0:
        return None
    previous_index = segment.index - 1
    frame = frame_path(scene_dir, previous_index)
    if frame.exists():
        logger.info("Continuity: using previous segment's last frame %s", frame)
        return frame
    previous_video = scene_dir / f"part-{previous_index}.mp4"
    if previous_video.exists():
        logger.info("Continuity: extracting last frame from existing %s ...", previous_video)
        if extract_last_frame(previous_video, frame):
            return frame
        return None
    logger.info(
        "Continuity: no part-%d.jpg or part-%d.mp4 found; generating segment %d "
        "without a continuity reference.", previous_index, previous_index, segment.index,
    )
    return None


def combine_parts(scene_dir: Path, segments: list[SceneSegment]) -> Path | None:
    """Concatenate all part clips in order into full.mp4 with ffmpeg.

    full.mp4 is always (re)written so it reflects the current part clips.
    Returns the combined file path, or None when ffmpeg is unavailable.
    """
    full_path = scene_dir / FULL_VIDEO_NAME
    if shutil.which("ffmpeg") is None:
        logger.warning(
            "All scene parts are present, but ffmpeg is not installed — skipping "
            "combination. Install ffmpeg and re-run to produce %s.", full_path,
        )
        return None

    concat_file = scene_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{part_path(scene_dir, segment).name}'\n" for segment in segments),
        encoding="utf-8",
    )
    logger.info("Combining %d parts into %s ...", len(segments), full_path)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file.name,
                "-c", "copy",
                full_path.name,
            ],
            cwd=scene_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ffmpeg failed to combine the scene parts:\n{error.stderr}")
    finally:
        concat_file.unlink(missing_ok=True)
    logger.info("Combined video written: %s", full_path)
    return full_path


def run(args: argparse.Namespace) -> int:
    script_path = Path(args.scripts_dir) / f"{args.scene}.md"
    if not script_path.is_file():
        raise RuntimeError(
            f"Scene script {script_path} not found. "
            f"Generate it first with src/scene_script.py --name \"{args.scene}\" --prompt \"...\"."
        )
    script = script_path.read_text(encoding="utf-8")
    logger.info("Loaded scene script: %s (%d chars)", script_path, len(script))

    characters = parse_scene_characters(script)
    logger.info("Characters in scene: %s", ", ".join(characters))

    logline = parse_global_section(script, r"Logline")
    setting = parse_global_section(script, r"Setting[^\n]*")
    if not setting:
        logger.info("No '## Setting & Light' section found; segments will be prompted as-is.")

    segments = parse_segments(script)
    if args.parts is not None:
        selected = [segment for segment in segments if segment.index == args.parts]
        if not selected:
            available = ", ".join(str(segment.index) for segment in segments)
            raise RuntimeError(
                f"--parts {args.parts} does not match any segment in {script_path}. "
                f"Available segment indices: {available}."
            )
    else:
        selected = segments

    blueprint_dir = Path(args.blueprint_dir)
    references = [
        (character, latest_attempt_image(character, blueprint_dir))
        for character in characters
    ]
    for character, image_path in references:
        logger.info("Reference for %s: %s", character, image_path)

    scene_dir = Path(args.output) if args.output else DEFAULT_ANIMATIONS_DIR / args.scene
    scene_dir.mkdir(parents=True, exist_ok=True)

    pending = [
        segment for segment in selected
        if args.force or not part_path(scene_dir, segment).exists()
    ]
    skipped = [segment for segment in selected if segment not in pending]
    for segment in skipped:
        logger.info("Part %d already exists at %s; skipping (use --force to regenerate).",
                    segment.index, part_path(scene_dir, segment))

    if pending:
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not gemini_key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this command.")
        client = genai.Client(api_key=gemini_key)

        for segment in pending:
            logger.info("=== Generating segment %d of %d (%s) ===",
                        segment.index, len(segments) - 1, segment.span or "whole script")
            continuity_frame = previous_frame(scene_dir, segment)
            direction = build_direction(
                args.scene, logline, setting, segment, characters, args.duration,
                has_continuity=continuity_frame is not None,
            )
            input_items = build_input_items(direction, references, continuity_frame)
            interaction = create_video_interaction(client, args.video_model, input_items, args.duration)
            interaction = wait_for_completion(client, interaction, args.timeout)
            video_bytes = extract_video_bytes(interaction)
            destination = part_path(scene_dir, segment)
            destination.write_bytes(video_bytes)
            logger.info("Wrote segment %d clip: %s (%d bytes)",
                        segment.index, destination, len(video_bytes))
            extract_last_frame(destination, frame_path(scene_dir, segment.index))
    else:
        logger.info("Nothing to generate — all selected parts already exist.")

    missing = [segment for segment in segments if not part_path(scene_dir, segment).exists()]
    if missing:
        logger.info(
            "Scene is incomplete: missing part(s) %s. Run again (optionally with "
            "--parts) to generate them, then the parts will be combined into %s.",
            ", ".join(str(segment.index) for segment in missing),
            scene_dir / FULL_VIDEO_NAME,
        )
    else:
        full_path = combine_parts(scene_dir, segments)
        if full_path:
            print(f"Wrote full scene video: {full_path}")
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description=(
            "Generate 10-second 720p 24fps animated clips for a scene script "
            "using Google Gemini Omni Flash, with the scene's final character "
            "blueprints as reference images. Each script segment becomes "
            "out/animations/<scene>/part-<N>.mp4; once every part exists, they "
            "are concatenated into out/animations/<scene>/full.mp4."
        )
    )
    parser.add_argument(
        "--scene",
        required=True,
        help="Scene name; reads out/scripts/<scene>.md (e.g. frisby_meets_greatowl).",
    )
    parser.add_argument(
        "--parts",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Generate only the segment with this index (from 0). E.g. --parts 2 "
            "generates only the 3rd segment. Default: generate every missing segment."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate parts even if they already exist (full.mp4 is always rebuilt).",
    )
    parser.add_argument(
        "--video-model",
        default=DEFAULT_VIDEO_MODEL,
        help=f"Gemini Omni Flash video model (default: {DEFAULT_VIDEO_MODEL}).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION_SECONDS,
        help=f"Clip length in seconds per segment (default: {DEFAULT_DURATION_SECONDS}).",
    )
    parser.add_argument(
        "--scripts-dir",
        default=str(DEFAULT_SCRIPTS_DIR),
        help=f"Directory of scene scripts (default: {DEFAULT_SCRIPTS_DIR}).",
    )
    parser.add_argument(
        "--blueprint-dir",
        default=str(DEFAULT_BLUEPRINT_DIR),
        help=f"Directory of character/scene blueprint outputs (default: {DEFAULT_BLUEPRINT_DIR}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory for clips (default: out/animations/<scene>/).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Maximum seconds to wait for each video generation (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    args = parser.parse_args()

    try:
        raise SystemExit(run(args))
    except requests.exceptions.RequestException as error:
        parser.error(f"Network error during API call: {error}")
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
