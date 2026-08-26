"""CLI entry point and command orchestration for scene script animation."""

from __future__ import annotations

import argparse
import io
import json
import logging
import shlex
import subprocess
import sys
from pathlib import Path

import requests

from animator.config import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_MINIMAX_VIDEO_MODEL,
    DEFAULT_OPENROUTER_VIDEO_MODEL,
    DEFAULT_RESOLUTION,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_VIDEO_PROVIDER,
    FULL_VIDEO_NAME,
    VIDEO_PROVIDERS,
)
from animator.media import (
    combine_parts,
    extract_first_frame,
    extract_last_frame,
    latest_part_path,
    next_part_paths,
    previous_frame,
)
from animator.models import SceneSegment
from animator.prompt import add_reference_tags, build_video_request
from animator.providers import create_video_provider
from animator.script import (
    find_scene_part_scripts,
    parse_scene_characters,
    parse_segments,
    strip_html_comments,
)
from blueprint_generator import slug
from films import film_animations_dir, film_blueprint_dir, film_scripts_dir
from movie_config import (
    get_film,
    get_movie_info,
    get_scene,
    get_story_scene,
    set_film,
)

logger = logging.getLogger("animator")

log_capture_stream = io.StringIO()
log_capture_handler = logging.StreamHandler(log_capture_stream)
log_capture_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
)


def ensure_log_capture() -> None:
    root = logging.getLogger()
    if log_capture_handler not in root.handlers:
        root.addHandler(log_capture_handler)


def get_invocation_cmd() -> str:
    """Return the full CLI command used to call animator."""
    argv = list(sys.argv)
    if not argv:
        return "uv run animator"
    prog = Path(argv[0]).name
    if prog in ("animator", "animator.py", "cli.py", "__main__.py"):
        args = argv[1:]
        if args:
            return f"uv run animator {shlex.join(args)}"
        return "uv run animator"
    return shlex.join(argv)


def format_video_metadata_text(cmd: str, logs: str) -> str:
    """Format metadata text file with the starting CLI command and an <OUTPUT> section."""
    cleaned_logs = logs.strip()
    return f"{cmd}\n\n<OUTPUT>\n{cleaned_logs}\n</OUTPUT>\n"


def write_video_metadata(video_path: Path, cmd: str, logs: str) -> Path:
    """Write the video's accompanying .txt metadata file."""
    txt_path = video_path.with_suffix(".txt")
    txt_path.write_text(format_video_metadata_text(cmd, logs), encoding="utf-8")
    return txt_path


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
        run_blueprint_generator(
            ["uv", "run", "generate-blueprint", "--film", get_film(), "--character", character]
        )
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
        run_blueprint_generator(
            ["uv", "run", "generate-blueprint", "--film", get_film(), "--scene", scene_slug]
        )
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
    ensure_log_capture()
    cmd = get_invocation_cmd()
    generated_videos: list[Path] = []

    try:
        frame_start_value = getattr(args, "frame_start", None)
        frame_end_value = getattr(args, "frame_end", None)
        frame_start = Path(frame_start_value) if frame_start_value else None
        frame_end = Path(frame_end_value) if frame_end_value else None
        for option, frame_path in (("--frame-start", frame_start), ("--frame-end", frame_end)):
            if frame_path is not None and not frame_path.is_file():
                raise ValueError(f"{option} must point to an existing image file: {frame_path}")

        default_scripts_dir = film_scripts_dir(get_film())
        scripts_dir = Path(args.scripts_dir) if args.scripts_dir else default_scripts_dir
        part_scripts = find_scene_part_scripts(scripts_dir, args.scene)

        if not part_scripts:
            # Check for legacy single-file script
            legacy_path = scripts_dir / f"{args.scene}.md"
            if legacy_path.is_file():
                script = strip_html_comments(legacy_path.read_text(encoding="utf-8"))
                segments = parse_segments(script)
                logger.info("Loaded legacy scene script: %s", legacy_path)
            else:
                expected_file = scripts_dir / f"{args.scene}_part0.md"
                raise RuntimeError(
                    f"Scene script {expected_file} not found. "
                    f"Generate it first with: uv run scene-script --name \"{args.scene}\""
                )
        else:
            segments = [
                SceneSegment(index=idx, span="", body=strip_html_comments(path.read_text(encoding="utf-8")))
                for idx, path in part_scripts
            ]
            logger.info(
                "Loaded %d scene segment script(s) for %r", len(segments), args.scene
            )

        default_animations_dir = film_animations_dir(get_film())
        scene_dir = Path(args.output) if args.output else default_animations_dir / args.scene
        scene_dir.mkdir(parents=True, exist_ok=True)

        default_blueprint_dir = film_blueprint_dir(get_film())
        blueprint_dir = Path(args.blueprint_dir) if args.blueprint_dir else default_blueprint_dir

        if args.compose_only:
            present = [
                segment
                for segment in segments
                if latest_part_path(scene_dir, segment.index) is not None
            ]
            missing = [
                segment
                for segment in segments
                if latest_part_path(scene_dir, segment.index) is None
            ]
            if missing:
                logger.info(
                    "Missing part(s) %s — combining only the existing clips.",
                    ", ".join(str(segment.index) for segment in missing),
                )
            full_path = combine_parts(scene_dir, present)
            if full_path:
                generated_videos.append(full_path)
                logger.info("Wrote full scene video: %s", full_path)
                print(f"Wrote full scene video: {full_path}")
            return 0

        characters = parse_scene_characters(segments[0].body)
        logger.info("Characters in scene: %s", ", ".join(characters))

        if args.parts is not None:
            selected = [segment for segment in segments if segment.index == args.parts]
            if not selected:
                available = ", ".join(str(segment.index) for segment in segments)
                raise RuntimeError(
                    f"--parts {args.parts} does not match any segment for {args.scene}. "
                    f"Available segment indices: {available}."
                )
            # When specific part is requested, always generate a new version
            pending = selected
        else:
            selected = segments
            # When all parts are targeted, generate only missing segments
            pending = [
                segment
                for segment in selected
                if latest_part_path(scene_dir, segment.index) is None
            ]
            skipped = [segment for segment in selected if segment not in pending]
            for segment in skipped:
                logger.info(
                    "Part %d already exists at %s; skipping (specify --parts %d to generate a new version).",
                    segment.index,
                    latest_part_path(scene_dir, segment.index),
                    segment.index,
                )

        if pending:
            provider_obj = create_video_provider(
                getattr(args, "provider", DEFAULT_VIDEO_PROVIDER),
                model=args.video_model,
            )
            logger.info("Using video provider: %s", provider_obj.name)

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
                movie_info = get_movie_info()
                aspect_ratio = (movie_info.orientation or DEFAULT_ASPECT_RATIO).strip() or DEFAULT_ASPECT_RATIO
                video_dst, start_dst, end_dst, prompt_dst = next_part_paths(scene_dir, segment.index)
                logger.info(
                    "=== Generating movie=%s film=%s scene=%s part=%d (final part "
                    "script: %s) ===",
                    movie_info.title,
                    get_film(),
                    args.scene,
                    segment.index,
                    prompt_dst,
                )
                continuity_frame = frame_start or previous_frame(scene_dir, segment)
                closing_frame = frame_end
                if frame_start is not None:
                    logger.info(
                        "Using --frame-start override for segment %d: %s",
                        segment.index,
                        frame_start,
                    )
                if frame_end is not None:
                    logger.info(
                        "Using --frame-end override for segment %d: %s",
                        segment.index,
                        frame_end,
                    )
                background_plate = None
                if scene_slug and continuity_frame is None and closing_frame is None:
                    background_plate = ensure_background_plate(scene_slug, blueprint_dir, segment.body)
                    logger.info(
                        "Background plate reference for segment %d: %s",
                        segment.index,
                        background_plate,
                    )

                direction = add_reference_tags(
                    base_prompt=segment.body,
                    characters=characters,
                    has_continuity=continuity_frame is not None,
                    has_background_reference=background_plate is not None,
                    has_closing_continuity=closing_frame is not None,
                    duration=args.duration,
                )
                prompt_dst.write_text(direction, encoding="utf-8")
                logger.info("Saved prompt for segment %d: %s", segment.index, prompt_dst)

                request = build_video_request(
                    direction,
                    references,
                    continuity_frame,
                    background_plate,
                    closing_frame=closing_frame,
                    duration=args.duration,
                    resolution=DEFAULT_RESOLUTION,
                    aspect_ratio=aspect_ratio,
                )
                video_bytes = provider_obj.generate(request, args.timeout)
                video_dst.write_bytes(video_bytes)
                logger.info(
                    "Wrote segment %d clip: %s (%d bytes)",
                    segment.index,
                    video_dst,
                    len(video_bytes),
                )
                generated_videos.append(video_dst)
                extract_first_frame(video_dst, start_dst)
                extract_last_frame(video_dst, end_dst)
        else:
            logger.info("Nothing to generate — all selected parts already exist.")

        present = [
            segment
            for segment in segments
            if latest_part_path(scene_dir, segment.index) is not None
        ]
        missing = [
            segment
            for segment in segments
            if latest_part_path(scene_dir, segment.index) is None
        ]
        if len(present) >= 2:
            if missing:
                logger.info(
                    "Scene is incomplete: missing part(s) %s. Combining existing %d parts anyway.",
                    ", ".join(str(segment.index) for segment in missing),
                    len(present),
                )
            full_path = combine_parts(scene_dir, present)
            if full_path:
                generated_videos.append(full_path)
                logger.info("Wrote full scene video: %s", full_path)
                print(f"Wrote full scene video: {full_path}")
        elif missing:
            logger.info(
                "Scene is incomplete: missing part(s) %s. Run again (optionally with "
                "--parts) to generate them, then the parts will be combined into %s.",
                ", ".join(str(segment.index) for segment in missing),
                scene_dir / FULL_VIDEO_NAME,
            )
        else:
            full_path = combine_parts(scene_dir, segments)
            if full_path:
                generated_videos.append(full_path)
                logger.info("Wrote full scene video: %s", full_path)
                print(f"Wrote full scene video: {full_path}")
        return 0
    finally:
        logs = log_capture_stream.getvalue()
        for v_path in generated_videos:
            if v_path.exists():
                write_video_metadata(v_path, cmd, logs)


def main() -> None:
    """Parse CLI arguments and run animator pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--film", default=None)
    pre_args, _ = pre.parse_known_args()
    try:
        set_film(pre_args.film)
    except ValueError as error:
        pre.error(str(error))
    parser = argparse.ArgumentParser(
        description=(
            f"Generate {DEFAULT_DURATION_SECONDS}-second {DEFAULT_RESOLUTION} 24fps animated clips for a scene script "
            "using a configurable video provider (default: MiniMax H3 via the MiniMax API "
            "at 768P; alternative: OpenRouter alibaba/wan-3.0 at 480p), with the scene's final "
            "character blueprints as reference images. Each script segment becomes "
            "films/<film>/out/animations/<scene>/part-<N>.mp4 (or -v1.mp4, -v2.mp4); the existing parts are then "
            "combined with 0.2s crossfade transitions into "
            "films/<film>/out/animations/<scene>/full.mp4."
        ),
        epilog=(
            "examples:\n"
            "  %(prog)s --scene frisby_visits_mr_ages\n"
            "      Generate every missing segment clip, then combine all parts\n"
            "      into full.mp4.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 2\n"
            "      Generate only segment 2 (the third 10-second part). If\n"
            "      part-1-end.jpg exists it is used as the mandatory opening\n"
            "      frame.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 1\n"
            "      Generate a new version of segment 1 (e.g. part-1-v1.mp4).\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --compose-only\n"
            "      No generation and no API key needed: combine the existing\n"
            "      part-*.mp4 clips into full.mp4 with crossfade transitions.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--film",
        default=get_film(),
        help=(
            "Film slug under films/<film>/ whose movie.yml and out/ to use "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--scene",
        required=True,
        help="Scene name; reads <scripts-dir>/<scene>_part<N>.md (e.g. frisby_meets_greatowl).",
    )
    parser.add_argument(
        "--parts",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Generate only the segment with this index (from 0). E.g. --parts 2 "
            "generates the next version of the 3rd segment. Default: generate every missing segment."
        ),
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
        "--frame-start",
        "--frame_start",
        dest="frame_start",
        default=None,
        metavar="PATH",
        help=(
            "Image to use as the mandatory opening frame for every generated part. "
            "Overrides the automatically discovered previous-part end frame."
        ),
    )
    parser.add_argument(
        "--frame-end",
        "--frame_end",
        dest="frame_end",
        default=None,
        metavar="PATH",
        help=(
            "Image to use as the mandatory closing frame for every generated part."
        ),
    )
    parser.add_argument(
        "--video-model",
        default=None,
        help=(
            "Video generation model ID (override; when omitted each provider "
            "uses its own default: google -> %s, openrouter -> %s, minimax -> %s)."
            % (
                DEFAULT_VIDEO_MODEL,
                DEFAULT_OPENROUTER_VIDEO_MODEL,
                DEFAULT_MINIMAX_VIDEO_MODEL,
            )
        ),
    )
    parser.add_argument(
        "--provider",
        choices=list(VIDEO_PROVIDERS),
        default=DEFAULT_VIDEO_PROVIDER,
        help=(
            "Video generation provider (default: %(default)s, MiniMax H3 via the "
            "MiniMax API at 768P). 'google' (alias 'gemini') uses the Gemini API. "
            "'openrouter' uses the async OpenRouter videos API (alibaba/wan-3.0, "
            "480p default) with the OpenRouter API key. 'minimax' uses the MiniMax "
            "API directly (MiniMax H3, 768P default) with the MINIMAX_API_KEY."
        ),
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION_SECONDS,
        help=f"Clip length in seconds per segment (default: {DEFAULT_DURATION_SECONDS}).",
    )
    parser.add_argument(
        "--scripts-dir",
        default=None,
        help=f"Directory of scene scripts (default: {film_scripts_dir(get_film())}).",
    )
    parser.add_argument(
        "--blueprint-dir",
        default=None,
        help=(
            "Directory of character/scene blueprint outputs "
            f"(default: {film_blueprint_dir(get_film())})."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output directory for clips "
            f"(default: {film_animations_dir(get_film())}/<scene>/)."
        ),
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
