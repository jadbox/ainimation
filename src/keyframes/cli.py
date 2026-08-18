"""Command-line interface and execution orchestration for keyframe generation."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from google import genai

from animator.cli import (
    ensure_background_plate,
    ensure_character_reference,
    find_scene_background_plate,
    resolve_scene_slug,
)
from animator.models import SceneSegment
from animator.script import (
    find_scene_part_scripts,
    parse_scene_characters,
    parse_segments,
    strip_html_comments,
)
from blueprint_generator.utils.env import DEFAULT_IMAGE_MODEL, require_environment
from films import film_animations_dir, film_blueprint_dir, film_scripts_dir
from keyframes.generator import generate_keyframe
from keyframes.paths import next_proposal_paths, resolve_ref_image
from movie_config import get_film, set_film

logger = logging.getLogger("keyframes")


def run(args: argparse.Namespace) -> int:
    """Execute the keyframe proposal generation pipeline."""
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        require_environment("GEMINI_API_KEY", "GOOGLE_API_KEY")

    client = genai.Client(api_key=gemini_key)

    default_scripts_dir = film_scripts_dir(get_film())
    scripts_dir = Path(args.scripts_dir) if args.scripts_dir else default_scripts_dir
    part_scripts = find_scene_part_scripts(scripts_dir, args.scene)

    if not part_scripts:
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
            SceneSegment(
                index=idx, span="", body=strip_html_comments(path.read_text(encoding="utf-8"))
            )
            for idx, path in part_scripts
        ]
        logger.info("Loaded %d scene segment script(s) for %r", len(segments), args.scene)

    default_animations_dir = film_animations_dir(get_film())
    scene_dir = Path(args.output) if args.output else default_animations_dir / args.scene
    scene_dir.mkdir(parents=True, exist_ok=True)

    default_blueprint_dir = film_blueprint_dir(get_film())
    blueprint_dir = Path(args.blueprint_dir) if args.blueprint_dir else default_blueprint_dir

    if args.parts is not None:
        selected = [segment for segment in segments if segment.index == args.parts]
        if not selected:
            available = ", ".join(str(segment.index) for segment in segments)
            raise RuntimeError(
                f"--parts {args.parts} does not match any segment for {args.scene}. "
                f"Available segment indices: {available}."
            )
    else:
        selected = segments

    # Determine keyframe types to generate
    keyframe_types: list[str] = []
    if getattr(args, "both", False) or args.type == "both":
        keyframe_types = ["start", "end"]
    elif getattr(args, "end", False) or args.type == "end":
        keyframe_types = ["end"]
    else:
        keyframe_types = ["start"]

    logger.info(
        "Generating keyframes for scene=%s film=%s parts=%s type=%s model=%s",
        args.scene,
        get_film(),
        [seg.index for seg in selected],
        keyframe_types,
        args.image_model,
    )

    for segment in selected:
        characters = parse_scene_characters(segment.body)
        logger.info("Characters in segment %d: %s", segment.index, ", ".join(characters))

        character_refs = [
            (character, ensure_character_reference(character, blueprint_dir))
            for character in characters
        ]

        scene_slug = resolve_scene_slug(args.scene)

        for ktype in keyframe_types:
            out_img, prompt_file = next_proposal_paths(scene_dir, segment.index, ktype)

            ref_prev: Path | None = None
            ref_prev_arg = (
                getattr(args, "ref_prev", None)
                or getattr(args, "ref_start", None)
                or getattr(args, "ref", None)
            )
            if ref_prev_arg:
                ref_prev = resolve_ref_image(ref_prev_arg, scene_dir, get_film())
                logger.info("Using previous reference image: %s", ref_prev)

            ref_after: Path | None = None
            ref_after_arg = getattr(args, "ref_after", None) or getattr(args, "ref_end", None)
            if ref_after_arg:
                ref_after = resolve_ref_image(ref_after_arg, scene_dir, get_film())
                logger.info("Using after reference image: %s", ref_after)

            background_plate: Path | None = None
            if scene_slug and ref_prev is None and ref_after is None:
                background_plate = find_scene_background_plate(
                    scene_slug, blueprint_dir, segment.body
                )
                if background_plate is None:
                    background_plate = ensure_background_plate(
                        scene_slug, blueprint_dir, segment.body
                    )
                logger.info("Background plate for segment %d: %s", segment.index, background_plate)

            generate_keyframe(
                client=client,
                model=args.image_model,
                scene_name=args.scene,
                segment=segment,
                keyframe_type=ktype,
                characters=characters,
                character_refs=character_refs,
                background_plate=background_plate,
                ref_prev=ref_prev,
                ref_after=ref_after,
                output_path=out_img,
                prompt_file_path=prompt_file,
            )

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for keyframes CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate start and/or end keyframe proposal images for scene script parts "
            "using character blueprints, background plates, and prior/after keyframe references. "
            "Output images are saved to films/<film>/out/animations/<scene>/part-<N>-<start|end>-proposal.jpg "
            "with a direct file link output for human review."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 0 --start\n"
            "      Generate start keyframe proposal for part 0.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 0 --both\n"
            "      Generate both start and end keyframe proposals for part 0.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 1 --start --ref-prev part-0-end-proposal.jpg\n"
            "      Generate start keyframe proposal for part 1 using part-0-end-proposal.jpg as previous reference.\n"
            "\n"
            "  %(prog)s --scene frisby_visits_mr_ages --parts 1 --start --ref-prev part-0-end-proposal.jpg --ref-after part-1-end-proposal.jpg\n"
            "      Generate keyframe bridging between previous and after references.\n"
        ),
    )
    parser.add_argument(
        "--film",
        default=get_film(),
        help="Film slug under films/<film>/ whose movie.yml and out/ to use (default: %(default)s).",
    )
    parser.add_argument(
        "--scene",
        required=True,
        help="Scene name; reads <scripts-dir>/<scene>_part<N>.md (e.g. frisby_visits_mr_ages).",
    )
    parser.add_argument(
        "--parts",
        "--part",
        type=int,
        default=None,
        dest="parts",
        metavar="N",
        help="Generate keyframe proposal(s) only for segment index N (from 0). Default: all segments.",
    )
    parser.add_argument(
        "--type",
        "--frame",
        choices=["start", "end", "both"],
        default="start",
        dest="type",
        help="Keyframe type to generate: 'start' (0:00), 'end' (final pose), or 'both' (default: %(default)s).",
    )
    parser.add_argument(
        "--start",
        action="store_const",
        dest="type",
        const="start",
        help="Shortcut to generate start keyframe proposal (the default).",
    )
    parser.add_argument(
        "--end",
        action="store_const",
        dest="type",
        const="end",
        help="Shortcut to generate end keyframe proposal.",
    )
    parser.add_argument(
        "--both",
        action="store_const",
        dest="type",
        const="both",
        help="Shortcut to generate both start and end keyframe proposals.",
    )
    parser.add_argument(
        "--ref-prev",
        default=None,
        metavar="PATH",
        help=(
            "Image file path to use as the previous / earlier keyframe continuity reference. "
            "Can be an absolute path, relative path, or filename in the scene animations folder."
        ),
    )
    parser.add_argument(
        "--ref-after",
        default=None,
        metavar="PATH",
        help=(
            "Image file path to use as the after / subsequent keyframe continuity reference. "
            "Can be an absolute path, relative path, or filename in the scene animations folder."
        ),
    )
    parser.add_argument(
        "--ref",
        default=None,
        dest="ref_prev",
        metavar="PATH",
        help="Alias for --ref-prev.",
    )
    parser.add_argument(
        "--ref-start",
        default=None,
        dest="ref_prev",
        metavar="PATH",
        help="Alias for --ref-prev.",
    )
    parser.add_argument(
        "--ref-end",
        default=None,
        dest="ref_after",
        metavar="PATH",
        help="Alias for --ref-after.",
    )
    parser.add_argument(
        "--image-model",
        default=DEFAULT_IMAGE_MODEL,
        help=f"Gemini image model ID (default: {DEFAULT_IMAGE_MODEL}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output directory for keyframe proposals "
            f"(default: {film_animations_dir(get_film())}/<scene>/)."
        ),
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
            "Directory of character/scene blueprints "
            f"(default: {film_blueprint_dir(get_film())})."
        ),
    )
    return parser


def main() -> None:
    """Parse CLI arguments and run keyframe generator."""
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

    parser = build_parser()
    args = parser.parse_args()

    try:
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
