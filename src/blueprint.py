#!/usr/bin/env python3
"""Generate, review, and refine style guide blueprints for characters and scene backgrounds.

Runs the generate/review loop for a character style guide (--character) or a
scene's background plates (--scene), writing artifacts to
``out/blueprint/<subject-slug>/``.

Usage:
    python src/blueprint.py --character "Mrs Brisby"
    python src/blueprint.py --scene great-owl-hollow
"""

from __future__ import annotations

import argparse
import json
import logging
import os

import requests
from google import genai

from blueprint_generator.utils.characters import get_character, list_character_names
from blueprint_generator.utils.scenes import SCENES, get_scene
from blueprint_generator.utils import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_REVIEW_MODEL,
    MAX_ITERATIONS,
    REVIEW_MODEL_GEMINI_FLASH_3_6,
    REVIEW_MODEL_KIMI_K3,
    Attempt,
    Subject,
    build_subjects,
    fallback_revision,
    generate_image,
    require_environment,
    review_image,
    save_jpeg,
    to_jpeg,
    write_iterations,
)
from movie_config import get_movie_info

logger = logging.getLogger("blueprint_generator")


def run_subject(
    client: genai.Client,
    openrouter_key: str | None,
    args: argparse.Namespace,
    subject: Subject,
) -> int:
    """Run the generate/review loop for one blueprint subject.

    Returns 0 when the reviewer accepts an image, 2 when the iteration cap is
    reached without acceptance.
    """
    output = subject.output_dir
    output.mkdir(parents=True, exist_ok=True)
    for old_attempt in output.glob("attempt-*.jpg"):
        logger.info("Removing old attempt file: %s", old_attempt)
        old_attempt.unlink()

    existing_prompt_path = output / "prompt.txt"
    existing_prompt = (
        existing_prompt_path.read_text(encoding="utf-8").strip()
        if existing_prompt_path.is_file()
        else ""
    )
    if existing_prompt:
        current_prompt = existing_prompt
        logger.info(
            "Loaded existing %s as the initial prompt (%d chars)",
            existing_prompt_path,
            len(current_prompt),
        )
    else:
        current_prompt = subject.initial_prompt
        logger.info("No existing prompt.txt found; built initial prompt from the subject spec")
    last_used_prompt = current_prompt
    attempts: list[Attempt] = []
    history: list[tuple[Attempt, bytes]] = []
    accepted = False

    logger.info("=== Starting generation pipeline for %s ===", subject.label)
    logger.info("Output directory: %s", output)

    for number in range(1, args.max_iterations + 1):
        logger.info("--- Iteration %d of %d ---", number, args.max_iterations)
        last_used_prompt = current_prompt
        logger.info(
            "Prompt for this iteration (%d chars):\n%s",
            len(current_prompt),
            current_prompt[:800] + ("..." if len(current_prompt) > 800 else ""),
        )

        generated_image = generate_image(client, args.image_model, current_prompt)
        image_data = to_jpeg(generated_image)
        attempt_image = output / f"attempt-{number:02d}.jpg"
        save_jpeg(image_data, attempt_image)
        logger.info("Saved attempt image: %s (%d bytes)", attempt_image, len(image_data))

        logger.info(
            "Running reviewer LLM (model=%s) on iteration %d ...", args.review_model, number
        )
        review = review_image(
            client=client,
            openrouter_key=openrouter_key,
            model=args.review_model,
            system_instruction=subject.review_instruction,
            prompt=current_prompt,
            image_data=image_data,
            history=history,
        )
        logger.info("Reviewer response for iteration %d: %s", number, json.dumps(review, indent=2))
        score_value = review.get("score")
        score = score_value if isinstance(score_value, int) else None
        accepted = review.get("accepted") is True
        learning = str(review.get("learning") or "No specific lesson supplied.").strip()
        feedback = str(review.get("feedback") or "No specific feedback supplied.").strip()
        revised_prompt = review.get("revised_prompt")
        if accepted:
            prompt_change = "None; the reviewer accepted this image."
        elif isinstance(revised_prompt, str) and revised_prompt.strip():
            current_prompt = revised_prompt.strip()
            prompt_change = "Replaced with the reviewer's complete revised prompt."
        else:
            current_prompt = fallback_revision(current_prompt, feedback)
            prompt_change = (
                "Appended the review feedback because no replacement prompt was supplied."
            )

        attempt_record = Attempt(
            number=number,
            score=score,
            accepted=accepted,
            learning=learning,
            feedback=feedback,
            prompt_change=prompt_change,
            prompt_used=last_used_prompt,
        )
        attempts.append(attempt_record)
        history.append((attempt_record, image_data))

        save_jpeg(image_data, output / f"{subject.style_slug}-style.jpg")
        write_iterations(output / "iterations.md", subject.display_name, attempts, accepted)

        if accepted:
            logger.info("✓ Iteration %d ACCEPTED (score: %s). Pipeline complete.", number, score)
            break
        else:
            logger.info("✗ Iteration %d REJECTED (score: %s). %s", number, score, prompt_change)
            logger.info("Updated prompt for next iteration (%d chars)", len(current_prompt))

    (output / "prompt.txt").write_text(last_used_prompt + "\n", encoding="utf-8")
    print(
        f"Wrote {output / f'{subject.style_slug}-style.jpg'}, {output / 'prompt.txt'}, and "
        f"{output / 'iterations.md'} after {len(attempts)} iteration(s)."
    )
    return 0 if accepted else 2


def run(args: argparse.Namespace) -> int:
    """Execute the blueprint generation and review pipeline across selected subjects."""
    if not 1 <= args.max_iterations <= MAX_ITERATIONS:
        raise ValueError(f"--max-iterations must be between 1 and {MAX_ITERATIONS}.")

    subjects = build_subjects(args)

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if "/" in args.review_model:
        if not openrouter_key:
            raise RuntimeError(
                "Set OPENROUTER_API_KEY before running with an OpenRouter review model."
            )
    else:
        if not gemini_key:
            require_environment("GEMINI_API_KEY", "GOOGLE_API_KEY")

    if not gemini_key:
        require_environment("GEMINI_API_KEY", "GOOGLE_API_KEY")

    client = genai.Client(api_key=gemini_key)

    logger.info(
        "Image model: %s | Review model: %s | Max iterations: %d",
        args.image_model,
        args.review_model,
        args.max_iterations,
    )
    logger.info(
        "Subjects to generate: %d (%s)",
        len(subjects),
        ", ".join(subject.label for subject in subjects),
    )

    exit_code = 0
    for subject in subjects:
        result = run_subject(client, openrouter_key, args, subject)
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
    available_characters = ", ".join(list_character_names())
    available_scenes = ", ".join(f"{spec.name} ({spec.slug})" for spec in SCENES.values())
    movie_info = get_movie_info()
    parser = argparse.ArgumentParser(
        description=(
            f"Generate and review blueprints for {movie_info.title}: "
            "either a character style guide (--character) or the 1-2 "
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
        "--output",
        default=None,
        help=(
            "Output directory (default: auto-derived from the subject name, "
            "e.g. ./out/blueprint/mr-ages/ for a character or "
            "./out/blueprint/great-owl-hollow/ for a scene, with one "
            "subdirectory per background plate)."
        ),
    )
    parser.add_argument(
        "--image-model",
        default=DEFAULT_IMAGE_MODEL,
        help=f"Gemini image model (default: {DEFAULT_IMAGE_MODEL}).",
    )
    parser.add_argument(
        "--review-model",
        default=DEFAULT_REVIEW_MODEL,
        help=f"Review model, either Gemini (e.g. {REVIEW_MODEL_GEMINI_FLASH_3_6}) or OpenRouter (e.g. {REVIEW_MODEL_KIMI_K3}) (default: {DEFAULT_REVIEW_MODEL}).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=MAX_ITERATIONS,
        help=f"Maximum generation/review attempts per subject, 1-{MAX_ITERATIONS} (default: {MAX_ITERATIONS}).",
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
    except requests.exceptions.Timeout as error:
        parser.error(
            f"API request timed out (the reviewer LLM may be slow or unreachable): {error}"
        )
    except requests.exceptions.RequestException as error:
        parser.error(f"Network error during API call: {error}")
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
