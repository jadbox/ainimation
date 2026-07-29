"""CLI entry point and command orchestration for scene script animation."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
from pathlib import Path

from google import genai
import requests

from animator.api import create_video_interaction, extract_video_bytes, wait_for_completion
from animator.config import (
    DEFAULT_ANIMATIONS_DIR,
    DEFAULT_BLUEPRINT_DIR,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_RESOLUTION,
    DEFAULT_SCRIPTS_DIR,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VIDEO_MODEL,
    FULL_VIDEO_NAME,
)
from animator.media import combine_parts, extract_last_frame, frame_path, part_path, previous_frame, prompt_path
from animator.prompt import build_direction, build_input_items
from animator.script import (
    parse_global_section,
    parse_scene_characters,
    parse_segments,
)
from blueprint_generator import slug
from movie_config import get_scene, get_story_scene

logger = logging.getLogger("animator")


def latest_attempt(folder: Path) -> Path | None:
    """Return the newest attempt-*.jpg directly in a blueprint folder, if any."""
    attempts = sorted(folder.glob("attempt-*.jpg"))
    return attempts[-1] if attempts else None


def run_blueprint_generator(command: list[str]) -> None:
    """Run the blueprint generator CLI, echoing the exact command first."""
    printable = " ".join(f'"{part}"' if " " in part else part for part in command)
    print(f"CREATING BLUEPRINT: {printable}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Blueprint generation failed (exit {error.returncode}): {printable}"
        ) from error


def ensure_character_reference(character: str, blueprint_dir: Path) -> Path:
    """Return the character's latest blueprint image, generating it if missing."""
    folder = blueprint_dir / slug(character)
    image = latest_attempt(folder)
    if image is None:
        run_blueprint_generator(["uv", "run", "generate-blueprint", "--character", character])
        image = latest_attempt(folder)
    if image is None:
        raise RuntimeError(
            f"Blueprint generation produced no attempt-*.jpg in {folder} for {character!r}."
        )
    return image


def resolve_scene_slug(script_name: str) -> str | None:
    """Map a scene-script name to its scene-location slug in movie.yml, if any."""
    try:
        location = get_story_scene(script_name).scene
        if location:
            return get_scene(location).slug
    except ValueError:
        pass
    try:
        return get_scene(script_name).slug
    except ValueError:
        return None


def find_scene_background_plate(
    scene_slug: str, blueprint_dir: Path, script_text: str = ""
) -> Path | None:
    """Find the newest background plate in subfolders defined by movie.yml for a scene."""
    try:
        scene = get_scene(scene_slug)
    except ValueError:
        scene = None

    if scene and scene.backgrounds:
        ordered_backgrounds = sorted(
            scene.backgrounds,
            key=lambda bg: 0 if bg.key in script_text else 1,
        )
        for bg in ordered_backgrounds:
            folder = blueprint_dir / scene_slug / bg.key
            plate = latest_attempt(folder)
            if plate is not None:
                return plate

    return latest_attempt(blueprint_dir / scene_slug)


def ensure_background_plate(
    scene_slug: str, blueprint_dir: Path, script_text: str = ""
) -> Path:
    """Return the scene's latest background plate, generating it if missing."""
    plate = find_scene_background_plate(scene_slug, blueprint_dir, script_text)
    if plate is None:
        run_blueprint_generator(["uv", "run", "generate-blueprint", "--scene", scene_slug])
        plate = find_scene_background_plate(scene_slug, blueprint_dir, script_text)
    if plate is None:
        try:
            scene = get_scene(scene_slug)
            expected_paths = ", ".join(
                str(blueprint_dir / scene_slug / bg.key) for bg in scene.backgrounds
            )
        except ValueError:
            expected_paths = str(blueprint_dir / scene_slug)
        raise RuntimeError(
            f"Blueprint generation produced no attempt-*.jpg in {expected_paths} "
            f"for scene {scene_slug!r}."
        )
    return plate


def run(args: argparse.Namespace) -> int:
    """Execute the animation generation or composition pipeline."""
    script_path = Path(args.scripts_dir) / f"{args.scene}.md"
    if not script_path.is_file():
        raise RuntimeError(
            f"Scene script {script_path} not found. "
            f"Generate it first with: uv run scene-script --name \"{args.scene}\""
        )
    script = script_path.read_text(encoding="utf-8")
    logger.info("Loaded scene script: %s (%d chars)", script_path, len(script))

    segments = parse_segments(script)
    scene_dir = Path(args.output) if args.output else DEFAULT_ANIMATIONS_DIR / args.scene
    scene_dir.mkdir(parents=True, exist_ok=True)

    if args.compose_only:
        present = [segment for segment in segments if part_path(scene_dir, segment).exists()]
        missing = [segment for segment in segments if not part_path(scene_dir, segment).exists()]
        if missing:
            logger.info(
                "Missing part(s) %s — combining only the existing clips.",
                ", ".join(str(segment.index) for segment in missing),
            )
        full_path = combine_parts(scene_dir, present)
        if full_path:
            print(f"Wrote full scene video: {full_path}")
        return 0

    characters = parse_scene_characters(script)
    logger.info("Characters in scene: %s", ", ".join(characters))

    logline = parse_global_section(script, r"Logline")
    setting = parse_global_section(script, r"Setting[^\n]*")
    if not setting:
        logger.info("No '## Setting & Light' section found; segments will be prompted as-is.")

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

    pending = [
        segment
        for segment in selected
        if args.force or not part_path(scene_dir, segment).exists()
    ]
    skipped = [segment for segment in selected if segment not in pending]
    for segment in skipped:
        logger.info(
            "Part %d already exists at %s; skipping (use --force to regenerate).",
            segment.index,
            part_path(scene_dir, segment),
        )

    if pending:
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not gemini_key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this command.")
        client = genai.Client(api_key=gemini_key)

        references = [
            (character, ensure_character_reference(character, blueprint_dir))
            for character in characters
        ]
        for character, image_path in references:
            logger.info("Reference for %s: %s", character, image_path)

        scene_slug = resolve_scene_slug(args.scene)
        if scene_slug:
            logger.info("Scene location for the background plate: %s", scene_slug)
        else:
            logger.info(
                "No movie.yml scene location matches %r; generating without a "
                "background plate reference.",
                args.scene,
            )

        for segment in pending:
            logger.info(
                "=== Generating segment %d of %d (%s) ===",
                segment.index,
                len(segments) - 1,
                segment.span or "whole script",
            )
            continuity_frame = previous_frame(scene_dir, segment)
            background_plate = None
            if scene_slug and segment.index == segments[0].index and continuity_frame is None:
                background_plate = ensure_background_plate(scene_slug, blueprint_dir, script)
                logger.info(
                    "Background plate reference for segment %d: %s",
                    segment.index,
                    background_plate,
                )
            direction = build_direction(
                args.scene,
                logline,
                setting,
                segment,
                characters,
                args.duration,
                has_continuity=continuity_frame is not None,
                has_background_reference=background_plate is not None,
            )
            prompt_file = prompt_path(scene_dir, segment.index)
            prompt_file.write_text(direction, encoding="utf-8")
            logger.info("Saved prompt for segment %d: %s", segment.index, prompt_file)

            input_items = build_input_items(
                direction, references, continuity_frame, background_plate
            )
            interaction = create_video_interaction(
                client, args.video_model, input_items, args.duration
            )
            interaction = wait_for_completion(client, interaction, args.timeout)
            video_bytes = extract_video_bytes(interaction)
            destination = part_path(scene_dir, segment)
            destination.write_bytes(video_bytes)
            logger.info(
                "Wrote segment %d clip: %s (%d bytes)",
                segment.index,
                destination,
                len(video_bytes),
            )
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
    """Parse CLI arguments and run animator pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description=(
            f"Generate 10-second {DEFAULT_RESOLUTION} 24fps animated clips for a scene script "
            "using Google Gemini Omni Flash, with the scene's final character "
            "blueprints as reference images. Each script segment becomes "
            "out/animations/<scene>/part-<N>.mp4; the existing parts are then "
            "combined with 0.2s crossfade transitions into "
            "out/animations/<scene>/full.mp4."
        ),
        epilog=(
            "examples:\n"
            "  %(prog)s --scene frisby_visits_mr_ages\n"
            "      Generate every missing segment clip, then combine all parts\n"
            "      into full.mp4.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 2\n"
            "      Generate only segment 2 (the third 10-second part). If\n"
            "      part-1.jpg exists it is used as the mandatory opening frame.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 1 --force\n"
            "      Regenerate segment 1 even though part-1.mp4 already exists\n"
            "      (new paid API call; without --force existing parts are skipped).\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --compose-only\n"
            "      No generation and no API key needed: combine the existing\n"
            "      part-*.mp4 clips into full.mp4 with crossfade transitions.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "--compose-only",
        action="store_true",
        help=(
            "Skip all generation: only combine the existing part-*.mp4 clips "
            "into full.mp4 with crossfade transitions (no API key needed)."
        ),
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
