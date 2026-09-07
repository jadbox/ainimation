#!/usr/bin/env python3
"""Generate style guide blueprints for characters and scene backgrounds.

Generates character model sheets (--character) or scene background plates (--scene)
using Google's Nano Banana 2 image model (gemini-3.1-flash-image-preview), baking all visual
production standards directly into the prompt. Output artifacts are written to
``films/<film>/out/blueprint/<subject-slug>/``.

Usage:
    python src/blueprint.py --character "Mrs Brisby"
    python src/blueprint.py --scene old-barn-field
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from google import genai

from blueprint_generator.utils.characters import get_character, list_character_names
from blueprint_generator.utils.scenes import SCENES, get_scene
from blueprint_generator.utils import (
    DEFAULT_IMAGE_MODEL,
    Subject,
    build_subjects,
    generate_image,
    require_environment,
    save_jpeg,
    to_jpeg,
)
from films import film_blueprint_dir
from movie_config import get_film, get_movie_info, set_film

logger = logging.getLogger("blueprint_generator")


def run_subject(
    client: genai.Client,
    args: argparse.Namespace,
    subject: Subject,
) -> int:
    """Generate the style guide blueprint for one subject."""
    output = subject.output_dir
    output.mkdir(parents=True, exist_ok=True)

    existing_style = output / f"{subject.style_slug}-style.jpg"
    existing_prompt_path = output / "prompt.txt"

    if (
        existing_style.is_file()
        and not getattr(args, "force", False)
        and not getattr(args, "new", False)
    ):
        logger.info(
            "Blueprint already exists for %s at %s. Pass --force or --new to regenerate.",
            subject.label,
            existing_style,
        )
        print(f"Blueprint already exists: {existing_style} (pass --force to regenerate)")
        return 0

    # Clean out any old attempt files
    for old_attempt in output.glob("attempt-*.jpg"):
        old_attempt.unlink()

    existing_prompt = (
        existing_prompt_path.read_text(encoding="utf-8").strip()
        if existing_prompt_path.is_file()
        else ""
    )
    if existing_prompt and not getattr(args, "new", False):
        prompt = existing_prompt
        logger.info(
            "Loaded existing %s as generation prompt (%d chars)",
            existing_prompt_path,
            len(prompt),
        )
    else:
        if getattr(args, "new", False):
            logger.info(
                "--new: ignoring %s; starting from a fresh prompt", existing_prompt_path
            )
        prompt = subject.initial_prompt
        logger.info("Built prompt from the subject spec (%d chars)", len(prompt))

    logger.info("=== Generating blueprint for %s ===", subject.label)
    logger.info("Output directory: %s", output)
    logger.info(
        "Prompt (%d chars):\n%s",
        len(prompt),
        prompt[:800] + ("..." if len(prompt) > 800 else ""),
    )

    generated_image = generate_image(client, args.image_model, prompt)
    image_data = to_jpeg(generated_image)

    # Save both attempt-01.jpg (for animator tool compatibility) and <style_slug>-style.jpg
    attempt_image = output / "attempt-01.jpg"
    save_jpeg(image_data, attempt_image)
    style_image = output / f"{subject.style_slug}-style.jpg"
    save_jpeg(image_data, style_image)

    existing_prompt_path.write_text(prompt + "\n", encoding="utf-8")

    iterations_file = output / "iterations.md"
    iterations_content = (
        f"# Blueprint Style Guide: {subject.display_name}\n\n"
        f"- **Model**: `{args.image_model}`\n"
        f"- **Output Style Image**: `{subject.style_slug}-style.jpg`\n"
        f"- **Primary Reference Plate**: `attempt-01.jpg` ({len(image_data)} bytes)\n\n"
        "## Production Prompt\n\n"
        "```\n"
        f"{prompt}\n"
        "```\n"
    )
    iterations_file.write_text(iterations_content, encoding="utf-8")

    print(
        f"Wrote {style_image}, {attempt_image}, and {existing_prompt_path}."
    )
    return 0


def run(args: argparse.Namespace) -> int:
    """Execute the blueprint generation pipeline across selected subjects."""
    subjects = build_subjects(args)

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        require_environment("GEMINI_API_KEY", "GOOGLE_API_KEY")

    client = genai.Client(api_key=gemini_key)

    logger.info(
        "Image model: %s | Subjects to generate: %d (%s)",
        args.image_model,
        len(subjects),
        ", ".join(subject.label for subject in subjects),
    )

    exit_code = 0
    for subject in subjects:
        result = run_subject(client, args, subject)
        if result != 0:
            exit_code = result
    return exit_code


def main() -> None:
    """Parse CLI arguments and run blueprint generator."""
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

    available_characters = ", ".join(list_character_names())
    available_scenes = ", ".join(f"{spec.name} ({spec.slug})" for spec in SCENES.values())
    movie_info = get_movie_info()
    parser = argparse.ArgumentParser(
        description=(
            f"Generate blueprints for {movie_info.title}: "
            "either a character style guide (--character) or the "
            "background plates of a scene (--scene)."
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--character",
        default=None,
        help=f"Name of the character to generate. Available characters: {available_characters}.",
    )
    target.add_argument(
        "--scene",
        default=None,
        help=f"Name or slug of the scene whose background plates to generate. Available scenes: {available_scenes}.",
    )
    parser.add_argument(
        "--film",
        default=get_film(),
        help="Film slug under films/<film>/ whose movie.yml and out/ to use (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output directory (default: auto-derived from the subject name, "
            f"e.g. {film_blueprint_dir(get_film()) / 'mr-ages'}/ for a character or "
            f"{film_blueprint_dir(get_film()) / 'great-owl-hollow'}/ for a scene, with one "
            "subdirectory per background plate)."
        ),
    )
    parser.add_argument(
        "--image-model",
        default=DEFAULT_IMAGE_MODEL,
        help=f"Gemini image model (Nano Banana 2: {DEFAULT_IMAGE_MODEL}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate the blueprint even if an existing style image already exists.",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Ignore the previous run's prompt.txt and start from a fresh prompt.",
    )

    args = parser.parse_args()

    # Validate the subject name early so a bad name lists all available
    # subjects in a clean error message before any API work begins.
    try:
        if args.character:
            get_character(args.character)
        else:
            get_scene(args.scene)
    except ValueError as error:
        parser.error(str(error))

    try:
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
