#!/usr/bin/env python3
"""Generate keyframe proposal images for scene script parts ahead of animation.

Reads the scene segment script files at ``films/<film>/out/scripts/<scene>_part<N>.md``,
collects character blueprints, scene background plates, and optional prior keyframe
references, then generates 16:9 start and/or end frame proposal images saved to
``films/<film>/out/animations/<scene>/part-<N>-<start|end>-proposal.jpg``.

Usage:
    python src/keyframes.py --scene frisby_visits_mr_ages --parts 0 --start
    python src/keyframes.py --scene frisby_visits_mr_ages --parts 0 --both
    python src/keyframes.py --scene frisby_visits_mr_ages --parts 1 --start --ref part-0-end-proposal.jpg
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

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
from blueprint_generator.utils.image import (
    aspect_ratio_to_dimensions,
    generate_image,
    normalize_aspect_ratio,
    save_jpeg,
    to_jpeg,
)
from blueprint_generator.utils.prompts import render_style_checklist
from films import film_animations_dir, film_blueprint_dir, film_scripts_dir
from movie_config import (
    get_character,
    get_film,
    get_movie_info,
    get_scene,
    set_film,
    standardize_name,
)

logger = logging.getLogger("keyframes")


def proposal_path(scene_dir: Path, segment_index: int, keyframe_type: str) -> Path:
    """Return the output proposal image file path for a given segment and type."""
    return scene_dir / f"part-{segment_index}-{keyframe_type}-proposal.jpg"


def proposal_prompt_path(scene_dir: Path, segment_index: int, keyframe_type: str) -> Path:
    """Return the saved prompt text path for a given segment and keyframe type."""
    return scene_dir / f"part-{segment_index}-{keyframe_type}-proposal-prompt.txt"


def resolve_ref_image(ref_arg: str, scene_dir: Path, film: str) -> Path:
    """Resolve a reference image path specified via --ref."""
    direct_path = Path(ref_arg)
    if direct_path.is_file():
        return direct_path.resolve()

    scene_path = scene_dir / ref_arg
    if scene_path.is_file():
        return scene_path.resolve()

    film_anim_path = film_animations_dir(film) / ref_arg
    if film_anim_path.is_file():
        return film_anim_path.resolve()

    raise ValueError(
        f"Reference image not found: {ref_arg!r}. Checked direct path ({direct_path}), "
        f"scene dir ({scene_path}), and animations dir ({film_anim_path})."
    )


def discover_continuity_ref(
    scene_dir: Path, segment_index: int, keyframe_type: str
) -> Path | None:
    """Find prior keyframe or frame file for automatic continuity reference."""
    if keyframe_type == "start":
        if segment_index == 0:
            return None
        prev_idx = segment_index - 1
        candidates = [
            scene_dir / f"part-{prev_idx}-end-proposal.jpg",
            scene_dir / f"part-{prev_idx}-end.jpg",
            scene_dir / f"part-{prev_idx}.jpg",
        ]
        for candidate in candidates:
            if candidate.is_file():
                logger.info("Found prior segment end frame for continuity: %s", candidate)
                return candidate.resolve()
        return None
    elif keyframe_type == "end":
        candidates = [
            scene_dir / f"part-{segment_index}-start-proposal.jpg",
            scene_dir / f"part-{segment_index}-start.jpg",
        ]
        for candidate in candidates:
            if candidate.is_file():
                logger.info("Found start frame of current segment for continuity: %s", candidate)
                return candidate.resolve()
        return None
    return None


def build_keyframe_prompt(
    scene_name: str,
    segment: SceneSegment,
    keyframe_type: str,
    characters: list[str],
    has_background: bool = False,
    has_ref_image: bool = False,
) -> str:
    """Build the textual direction prompt for keyframe image generation."""
    movie_info = get_movie_info()
    aspect_ratio = normalize_aspect_ratio(movie_info.orientation)
    width, height = aspect_ratio_to_dimensions(aspect_ratio)

    # Style checklist
    checklist = render_style_checklist(movie_info)
    checklist_block = (
        f"\nFilm Style Checklist (Mandatory Do's and Don'ts):\n{checklist}\n"
        if checklist
        else ""
    )

    # Character roster details
    char_specs: list[str] = []
    for i, char in enumerate(characters):
        clean_name = standardize_name(char)
        try:
            spec = get_character(char)
            desc = f"{clean_name} (<IMAGE_REF_{i}>): a {spec.species} — {spec.identity}. Appearance: {spec.appearance}."
            if spec.avoid:
                desc += f" Avoid: {spec.avoid}."
        except ValueError:
            desc = f"{clean_name} (<IMAGE_REF_{i}>)"
        char_specs.append(desc)
    characters_block = "\n".join(f"- {item}" for item in char_specs) if char_specs else "None."

    # Target keyframe objective instructions
    if keyframe_type == "start":
        target_instruction = (
            "KEYFRAME TARGET: START FRAME (Time 0:00 / Opening Beat of this segment)\n"
            "Depict the exact opening moment, initial character positions, starting poses, "
            "and initial lighting/composition at the very beginning (0:00) of this scene part."
        )
    else:
        target_instruction = (
            "KEYFRAME TARGET: END FRAME (Closing Beat / Final Held Pose of this segment)\n"
            "Depict the culmination of the action, final character emotional poses, "
            "held expressions, and closing composition at the very end of this scene part."
        )

    # Reference alignment instructions
    ref_instructions: list[str] = []
    if characters:
        ref_indices = ", ".join(f"<IMAGE_REF_{i}>" for i in range(len(characters)))
        ref_instructions.append(
            f"1. Character Reference Images ({ref_indices}): Match character designs, proportions, "
            "fur/feather texturing, anatomy, and garments EXACTLY to their respective reference model sheets."
        )
    if has_background:
        ref_instructions.append(
            "2. Background Plate Reference (<IMAGE_REF_BG>): The environment set, architecture, depth "
            "layering, and lighting atmosphere must match the background reference plate exactly."
        )
    if has_ref_image:
        ref_instructions.append(
            "3. Previous Keyframe Reference (<IMAGE_REF_PREV>): Maintain strict visual continuity with the "
            "previous keyframe — character placement, lighting direction, camera perspective, and narrative state."
        )

    alignment_block = "\n".join(ref_instructions) if ref_instructions else "No external image references."

    return f"""Create a single, highly polished, true {aspect_ratio} hand-painted 2D animation production keyframe illustration in {movie_info.style}.

{target_instruction}

Scene: "{scene_name}"
Camera Rules: {movie_info.camera_rules}

Hard Direction Rules:
{chr(10).join(f"- {rule}" for rule in movie_info.hard_direction_rules)}
{checklist_block}
Characters in Scene:
{characters_block}

Reference Image Alignment:
{alignment_block}

Scene Script & Setting:
{segment.body}

MANDATES:
- Output ONE clean, cohesive {aspect_ratio} production keyframe image for cel animation ({width}x{height}).
- Hand-painted 2D cel animation look with rich cel shading, gouache backgrounds, and rim lighting.
- Rodent eye-level perspective; characters interact within the scene and NEVER look into the camera lens.
- STRICTLY NO text, dialogue subtitles, sound effect labels, watermarks, UI overlays, storyboard borders, split screens, turnaround lineup layouts, or collage elements."""


def generate_keyframe(
    client: genai.Client,
    model: str,
    scene_name: str,
    segment: SceneSegment,
    keyframe_type: str,
    characters: list[str],
    character_refs: list[tuple[str, Path]],
    background_plate: Path | None,
    ref_image: Path | None,
    output_path: Path,
    prompt_file_path: Path,
) -> Path:
    """Assemble multimodal contents, prompt Gemini, and save the keyframe proposal."""
    movie_info = get_movie_info()
    aspect_ratio = normalize_aspect_ratio(movie_info.orientation)

    logger.info(
        "--- Generating %s keyframe proposal for %s part %d (aspect_ratio=%s) ---",
        keyframe_type.upper(),
        scene_name,
        segment.index,
        aspect_ratio,
    )

    prompt_text = build_keyframe_prompt(
        scene_name=scene_name,
        segment=segment,
        keyframe_type=keyframe_type,
        characters=characters,
        has_background=background_plate is not None,
        has_ref_image=ref_image is not None,
    )

    prompt_file_path.write_text(prompt_text, encoding="utf-8")
    logger.info("Saved keyframe prompt (%d chars) to: %s", len(prompt_text), prompt_file_path)

    # Build Gemini multimodal contents list
    contents: list[Any] = []
    for i, (name, img_path) in enumerate(character_refs):
        contents.append(f"[Character Reference <IMAGE_REF_{i}>: {name}]")
        contents.append(types.Part.from_bytes(data=img_path.read_bytes(), mime_type="image/jpeg"))

    if background_plate is not None:
        contents.append("[Scene Background Plate Reference <IMAGE_REF_BG>]")
        contents.append(
            types.Part.from_bytes(data=background_plate.read_bytes(), mime_type="image/jpeg")
        )

    if ref_image is not None:
        contents.append(f"[Previous Keyframe Reference <IMAGE_REF_PREV>: {ref_image.name}]")
        contents.append(types.Part.from_bytes(data=ref_image.read_bytes(), mime_type="image/jpeg"))

    contents.append(prompt_text)

    raw_image_bytes = generate_image(client, model, contents, aspect_ratio=aspect_ratio)
    jpeg_bytes = to_jpeg(raw_image_bytes, aspect_ratio=aspect_ratio)
    save_jpeg(jpeg_bytes, output_path)

    file_uri = output_path.resolve().as_uri()
    print(f"\nWrote keyframe proposal: {output_path}")
    print(f"Review proposal image: {file_uri}")
    print(f"Prompt saved to: {prompt_file_path}\n")
    return output_path


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
        background_plate = None
        if scene_slug:
            background_plate = find_scene_background_plate(
                scene_slug, blueprint_dir, segment.body
            )
            if background_plate is None:
                background_plate = ensure_background_plate(
                    scene_slug, blueprint_dir, segment.body
                )
            logger.info("Background plate for segment %d: %s", segment.index, background_plate)

        for ktype in keyframe_types:
            out_img = proposal_path(scene_dir, segment.index, ktype)
            prompt_file = proposal_prompt_path(scene_dir, segment.index, ktype)

            if out_img.is_file() and not args.force:
                logger.info(
                    "Keyframe proposal %s already exists; skipping (use --force to overwrite).",
                    out_img,
                )
                print(f"Keyframe proposal already exists: {out_img.resolve().as_uri()}")
                continue

            ref_image: Path | None = None
            if args.ref:
                ref_image = resolve_ref_image(args.ref, scene_dir, get_film())
                logger.info("Using specified --ref image: %s", ref_image)
            else:
                ref_image = discover_continuity_ref(scene_dir, segment.index, ktype)

            generate_keyframe(
                client=client,
                model=args.image_model,
                scene_name=args.scene,
                segment=segment,
                keyframe_type=ktype,
                characters=characters,
                character_refs=character_refs,
                background_plate=background_plate,
                ref_image=ref_image,
                output_path=out_img,
                prompt_file_path=prompt_file,
            )

    return 0


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

    parser = argparse.ArgumentParser(
        description=(
            "Generate start and/or end keyframe proposal images for scene script parts "
            "using character blueprints, background plates, and prior keyframe references. "
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
            "  %(prog)s --scene frisby_visits_mr_ages --parts 1 --start --ref part-0-end-proposal.jpg\n"
            "      Generate start keyframe proposal for part 1 using part-0-end-proposal.jpg as reference.\n"
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
        "--ref",
        default=None,
        metavar="PATH",
        help=(
            "Image file path to use as the previous keyframe / continuity reference. "
            "Can be an absolute path, relative path, or filename in the scene animations folder."
        ),
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate keyframe proposal even if output image already exists.",
    )

    args = parser.parse_args()

    try:
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
