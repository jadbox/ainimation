"""Generate, review, and refine a Don Bluth character style guide.

The generator is generic over any character defined in
:mod:`character_blueprint_generator.characters`. Pass ``--character <name>`` to
select the subject; the pipeline builds a tailored image prompt and reviewer
system instruction from that character's spec.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from google import genai
from google.genai import types
from PIL import Image

from character_blueprint_generator.characters import (
    CharacterSpec,
    get_character,
    list_character_names,
)

logger = logging.getLogger("character_blueprint_generator")


# Review model constants
REVIEW_MODEL_GEMINI_FLASH_3_6 = "gemini-3.6-flash"
REVIEW_MODEL_KIMI_K3 = "moonshotai/kimi-k3"

# Static configuration variables
REVIEW_MODEL = REVIEW_MODEL_KIMI_K3
MAX_ITERATIONS = 4

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_REVIEW_MODEL = REVIEW_MODEL


@dataclass
class Attempt:
    number: int
    score: int | None
    accepted: bool
    learning: str
    feedback: str
    prompt_change: str
    prompt_used: str = ""


def build_initial_prompt(character: CharacterSpec) -> str:
    return f"""Create a polished {character.name} character style guide for a hand-painted,
early-1980s dark fantasy animated feature. Deliver one cohesive 16:9 reference
image with a large three-quarter hero pose plus smaller front, profile, and back
turnaround views, detail callouts for key features, and a clear silhouette read.

{character.name} is {character.identity}: {character.appearance}. Give the
character {character.garment}. Keep the animal anatomy visible beneath it.

Use hand-inked tapered dark-brown linework, two-tone cel shading, dense gouache
and watercolor texture on paper, and deliberately irregular fur/feather
silhouettes. Stage the hero pose at {character.staging}. The pose should feel
{character.pose_mood}. Avoid {character.avoid}."""


def build_review_system_instruction(character: CharacterSpec) -> str:
    return f"""You are a world-class visual development director and production designer specializing in Don Bluth's iconic 1980s dark fantasy feature animation style (e.g., The Secret of NIMH, 1982).

Your job is to critically review the supplied {character.name} character reference sheet image against the requested prompt, analyze any previous review iterations you gave on earlier images, and decide whether the current image meets feature-film production standards.

When past review iterations are provided:
- Treat them as clearly labeled historical feedback from previous rounds in this review process.
- Critique the results of your past instructions: evaluate whether the image generator successfully implemented your prior feedback/revised prompt, or if it introduced new flaws.
- Refine and improve your review process based on how effectively previous prompt changes moved the artwork toward the target aesthetic.

Apply Don Bluth's strict 1980s aesthetic & technical visual criteria for {character.name}:
1. Character Identity & Anatomy: {character.identity}. Must read as a real {character.species} first and a person second. Required features: {character.appearance}. Garment: {character.garment}. Must retain true animal anatomy under garments.
2. Linework & Rendering: Expressive hand-inked tapered lines (dark brown, not black/vector), rich 2-tone cel shading, dense gouache/watercolor textured paint effect. Reject clean vector art, 3D CGI, smooth plastic gradients, or digital glow filters.
3. Staging & Lighting: Low rodent-eye perspective (2-12 inches high). Strong single practical light source producing rich amber/gold highlights contrasted with deep teal/indigo shadows and continuous cool-gold rim lighting. Dark, soft-focus foreground elements framing 20-30% of edges. Target staging: {character.staging}.
4. Sheet Organization & Quality: Clear 16:9 reference sheet with a prominent three-quarter hero pose plus turnaround views (front, profile, back) and detail callouts. Zero anatomy glitches, zero extra limbs, zero text/logos/watermarks/labels.

Be exacting and demanding. Do NOT accept merely because an image is visually pleasing or artistic if it misses key Don Bluth style mandates or reference sheet layout needs. When rejecting, provide a complete, self-contained revised image prompt that precisely remedies all identified defects while preserving all correct details.

Return JSON only with this schema:
{{"accepted": boolean, "score": integer from 0 to 100, "learning": "one concise lesson for the next iteration", "feedback": "specific visual findings", "revised_prompt": "a complete replacement image prompt when rejected; empty string when accepted"}}."""


def require_environment(name: str, alternate: str | None = None) -> str:
    value = os.environ.get(name) or (os.environ.get(alternate) if alternate else None)
    if not value:
        names = f"{name} or {alternate}" if alternate else name
        raise RuntimeError(f"Set {names} before running this command.")
    return value


def extract_image(response: Any) -> bytes:
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and getattr(inline_data, "data", None):
                return inline_data.data
    raise RuntimeError("Gemini returned no inline image data.")


def generate_image(client: genai.Client, model: str, prompt: str) -> bytes:
    logger.info("Generating image with model=%s ...", model)
    logger.debug("Image generation prompt:\n%s", prompt[:500] + ("..." if len(prompt) > 500 else ""))
    t0 = time.monotonic()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio="16:9"),
        ),
    )
    data = extract_image(response)
    elapsed = time.monotonic() - t0
    logger.info("Image generated successfully in %.1fs (%d bytes raw)", elapsed, len(data))
    return data


def to_jpeg(image_data: bytes) -> bytes:
    with Image.open(io.BytesIO(image_data)) as image:
        converted = image.convert("RGB")
        converted.thumbnail((1280, 720), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        converted.save(buf, format="JPEG", quality=95, optimize=True)
        return buf.getvalue()


def save_jpeg(image_data: bytes, destination: Path) -> None:
    destination.write_bytes(image_data)


def parse_json_response(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Reviewer did not return a JSON object.")
    payload = json.loads(content[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Reviewer response was not a JSON object.")
    return payload


def build_history_context(history: list[tuple[Attempt, bytes]]) -> str:
    if not history:
        return ""
    lines = ["=== PREVIOUS REVIEW ITERATIONS HISTORY ==="]
    for attempt, _ in history:
        verdict = "accepted" if attempt.accepted else "rejected"
        lines.append(f"--- Iteration {attempt.number} ({verdict}) ---")
        lines.append(f"Prompt provided to image generator:\n{attempt.prompt_used}")
        lines.append(f"Your score: {attempt.score if attempt.score is not None else 'N/A'}/100")
        lines.append(f"Your feedback: {attempt.feedback}")
        lines.append(f"Your lesson learned: {attempt.learning}")
        lines.append(f"Prompt change applied: {attempt.prompt_change}\n")
    return "\n".join(lines)


def review_image_gemini(
    client: genai.Client,
    model: str,
    system_instruction: str,
    prompt: str,
    image_data: bytes,
    history: list[tuple[Attempt, bytes]] | None = None,
) -> dict[str, Any]:
    logger.info("Starting Gemini review with model=%s ...", model)
    contents: list[Any] = []
    if history:
        history_text = build_history_context(history)
        contents.append(history_text)
        for attempt, prev_img in history:
            contents.append(f"[Past Image for Iteration {attempt.number}]")
            contents.append(types.Part.from_bytes(data=prev_img, mime_type="image/jpeg"))

    contents.append(
        f"=== CURRENT ITERATION TO REVIEW ===\n"
        f"Prompt used for image generation:\n{prompt}\n\n"
        f"Please review the image below against the prompt and previous iteration history."
    )
    contents.append(types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini review returned empty response.")
    logger.info("Gemini review completed. Raw response length: %d chars", len(response.text))
    return parse_json_response(response.text)


def review_image_openrouter(
    openrouter_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    image_data: bytes,
    history: list[tuple[Attempt, bytes]] | None = None,
) -> dict[str, Any]:
    logger.info("Starting OpenRouter review with model=%s ...", model)
    logger.info("Encoding image for OpenRouter (image size: %d bytes, %d history items)...",
                len(image_data), len(history) if history else 0)
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
    }
    user_content: list[dict[str, Any]] = []

    if history:
        history_text = build_history_context(history)
        user_content.append({"type": "text", "text": history_text})
        for attempt, prev_img in history:
            prev_b64 = base64.b64encode(prev_img).decode("utf-8")
            user_content.append(
                {"type": "text", "text": f"[Past Image for Iteration {attempt.number}]"}
            )
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{prev_b64}"},
                }
            )

    image_b64 = base64.b64encode(image_data).decode("utf-8")
    user_content.append(
        {
            "type": "text",
            "text": (
                f"=== CURRENT ITERATION TO REVIEW ===\n"
                f"Prompt used for image generation:\n{prompt}\n\n"
                f"Please review the image below against the prompt and previous iteration history."
            ),
        }
    )
    user_content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        }
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_instruction,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    logger.info("Sending OpenRouter review request (payload size: ~%d KB)...",
                len(json.dumps(payload)) // 1024)
    t0 = time.monotonic()
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    elapsed = time.monotonic() - t0
    logger.info("OpenRouter responded in %.1fs with status %d", elapsed, response.status_code)
    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter API error ({response.status_code}): {response.text}")
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected OpenRouter response format: {data}")
    if not content:
        raise RuntimeError("OpenRouter review returned empty response.")
    logger.info("OpenRouter review completed. Response content length: %d chars", len(content))
    return parse_json_response(content)


def review_image(
    client: genai.Client | None,
    openrouter_key: str | None,
    model: str,
    system_instruction: str,
    prompt: str,
    image_data: bytes,
    history: list[tuple[Attempt, bytes]] | None = None,
) -> dict[str, Any]:
    if "/" in model:
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is required for OpenRouter models.")
        return review_image_openrouter(openrouter_key, model, system_instruction, prompt, image_data, history)
    else:
        if not client:
            raise RuntimeError("Gemini client is required for Gemini models.")
        return review_image_gemini(client, model, system_instruction, prompt, image_data, history)


def fallback_revision(prompt: str, feedback: str) -> str:
    return f"{prompt}\n\nCorrection focus from visual review: {feedback.strip()}"


def write_iterations(destination: Path, character_name: str, attempts: list[Attempt], accepted: bool) -> None:
    result = "accepted" if accepted else f"not accepted within the {MAX_ITERATIONS}-iteration limit"
    lines = [
        f"# {character_name} Generation Iterations",
        "",
        f"- Iterations run: {len(attempts)}",
        f"- Final result: {result}",
        "",
    ]
    for attempt in attempts:
        verdict = "accepted" if attempt.accepted else "rejected"
        score = str(attempt.score) if attempt.score is not None else "not supplied"
        lines.extend(
            [
                f"## Iteration {attempt.number} ({verdict})",
                f"- Reviewer score: {score}/100",
                f"- Learned: {attempt.learning}",
                f"- Feedback: {attempt.feedback}",
                f"- Prompt change: {attempt.prompt_change}",
                "",
                "### Prompt Used for Image Generation",
                "```",
                attempt.prompt_used,
                "```",
                "",
            ]
        )
    destination.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    if not 1 <= args.max_iterations <= MAX_ITERATIONS:
        raise ValueError(f"--max-iterations must be between 1 and {MAX_ITERATIONS}.")

    character = get_character(args.character)

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if "/" in args.review_model:
        if not openrouter_key:
            raise RuntimeError("Set OPENROUTER_API_KEY before running with an OpenRouter review model.")
    else:
        if not gemini_key:
            require_environment("GEMINI_API_KEY", "GOOGLE_API_KEY")

    if not gemini_key:
        require_environment("GEMINI_API_KEY", "GOOGLE_API_KEY")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for old_attempt in output.glob("attempt-*.jpg"):
        logger.info("Removing old attempt file: %s", old_attempt)
        old_attempt.unlink()

    client = genai.Client(api_key=gemini_key)
    current_prompt = build_initial_prompt(character)
    last_used_prompt = current_prompt
    review_system_instruction = build_review_system_instruction(character)
    attempts: list[Attempt] = []
    history: list[tuple[Attempt, bytes]] = []
    accepted = False

    logger.info("=== Starting %s generation pipeline ===", character.name)
    logger.info("Image model: %s | Review model: %s | Max iterations: %d",
                args.image_model, args.review_model, args.max_iterations)
    logger.info("Output directory: %s", output)

    for number in range(1, args.max_iterations + 1):
        logger.info("--- Iteration %d of %d ---", number, args.max_iterations)
        last_used_prompt = current_prompt
        logger.info("Prompt for this iteration (%d chars):\n%s",
                    len(current_prompt), current_prompt[:800] + ("..." if len(current_prompt) > 800 else ""))

        generated_image = generate_image(client, args.image_model, current_prompt)
        image_data = to_jpeg(generated_image)
        attempt_image = output / f"attempt-{number:02d}.jpg"
        save_jpeg(image_data, attempt_image)
        logger.info("Saved attempt image: %s (%d bytes)", attempt_image, len(image_data))

        logger.info("Running reviewer LLM (model=%s) on iteration %d ...", args.review_model, number)
        review = review_image(
            client=client,
            openrouter_key=openrouter_key,
            model=args.review_model,
            system_instruction=review_system_instruction,
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
            prompt_change = "Appended the review feedback because no replacement prompt was supplied."

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

        save_jpeg(image_data, output / f"{slug(character.name)}-style.jpg")
        write_iterations(output / "iterations.md", character.name, attempts, accepted)

        if accepted:
            logger.info("✓ Iteration %d ACCEPTED (score: %s). Pipeline complete.", number, score)
            break
        else:
            logger.info("✗ Iteration %d REJECTED (score: %s). %s", number, score, prompt_change)
            logger.info("Updated prompt for next iteration (%d chars)", len(current_prompt))

    (output / "prompt.txt").write_text(last_used_prompt + "\n", encoding="utf-8")
    style_path = output / f"{slug(character.name)}-style.jpg"
    print(
        f"Wrote {style_path}, {output / 'prompt.txt'}, and "
        f"{output / 'iterations.md'} after {len(attempts)} iteration(s)."
    )
    return 0 if accepted else 2


def slug(name: str) -> str:
    """Return a filesystem-safe lowercase slug for a character name."""
    return name.lower().replace(" ", "-").replace(".", "")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    available = ", ".join(list_character_names())
    parser = argparse.ArgumentParser(
        description=(
            "Generate and review a Don Bluth character style guide for any "
            "character defined in the Rats of NIMH project."
        )
    )
    parser.add_argument(
        "--character",
        required=True,
        help=(
            f"Name of the character to generate (required). "
            f"Available characters: {available}."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output directory (default: auto-derived from the character name, "
            "e.g. ./mr-ages/)."
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
        help=f"Maximum generation/review attempts, 1-{MAX_ITERATIONS} (default: {MAX_ITERATIONS}).",
    )

    args = parser.parse_args()

    # Validate the character name early so a bad name lists all available
    # characters in a clean error message before any API work begins.
    try:
        character = get_character(args.character)
    except ValueError as error:
        parser.error(str(error))

    if args.output is None:
        args.output = slug(character.name)

    try:
        raise SystemExit(run(args))
    except requests.exceptions.Timeout as error:
        parser.error(f"API request timed out (the reviewer LLM may be slow or unreachable): {error}")
    except requests.exceptions.RequestException as error:
        parser.error(f"Network error during API call: {error}")
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
