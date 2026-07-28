"""Generate, review, and refine Don Bluth style blueprints.

The generator operates on two kinds of subjects:

* **Characters** defined in :mod:`blueprint_generator.characters` — pass
  ``--character <name>`` to generate a character style-guide sheet.
* **Scene backgrounds** defined in :mod:`blueprint_generator.scenes` — pass
  ``--scene <name>`` to generate the 1-2 clean background plates a scene
  describes. Every plate runs through its own generate/review loop.

In both modes the pipeline builds a tailored image prompt and reviewer system
instruction from the subject's spec, then iterates until the reviewer accepts
or the iteration cap is reached.
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

from blueprint_generator import slug
from blueprint_generator.characters import (
    CharacterSpec,
    get_character,
    list_character_names,
)
from blueprint_generator.scenes import (
    SCENES,
    BackgroundSpec,
    SceneSpec,
    get_scene,
)

logger = logging.getLogger("blueprint_generator")


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


@dataclass
class Subject:
    """One blueprint image to generate: a character sheet or a scene background plate."""

    label: str
    """Human-readable subject label for logs, e.g. ``scene 'X' background 'y'``."""

    display_name: str
    """Title used in iterations.md."""

    output_dir: Path
    style_slug: str
    initial_prompt: str
    review_instruction: str


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
5. Character Style Befitting the Narrative (HARD GATE): The design itself must make the viewer FEEL this character's role in the story at first glance; it must read as {character.pose_mood}. Apply the Bluth character-design DNA: grotesque-yet-appealing shapes, asymmetry and age/wear etched into the silhouette, tufted spiky fur or feathers breaking every contour, and oversized glossy eyes that carry the entire emotional performance. Ask yourself: "Could this exact design only exist in The Secret of NIMH (1982), and does it trigger the precise emotional reaction the narrative demands (awe, fear, tenderness, menace)?" A competent, cute, symmetrical, or generic rendering that could be dropped into any modern cartoon or children's book FAILS this criterion even when every technical box above is checked.

Be exacting and demanding. Do NOT accept merely because an image is visually pleasing or artistic if it misses key Don Bluth style mandates or reference sheet layout needs. NEVER accept an image that fails criterion 5, no matter how polished or technically correct it is: "generic but well-executed" is always a rejection. When rejecting, provide a complete, self-contained revised image prompt that precisely remedies all identified defects — especially any missing narrative emotional register or Bluth-specific character-style DNA — while preserving all correct details.

Return JSON only with this schema:
{{"accepted": boolean, "score": integer from 0 to 100, "learning": "one concise lesson for the next iteration", "feedback": "specific visual findings", "revised_prompt": "a complete replacement image prompt when rejected; empty string when accepted"}}."""


def build_scene_initial_prompt(scene: SceneSpec, background: BackgroundSpec) -> str:
    return f"""Create a polished production background plate for a hand-painted,
early-1980s dark fantasy animated feature (The Secret of NIMH, 1982 era).
Deliver one cohesive 16:9 background with NO characters or creatures in frame —
a clean plate ready for cel compositing.

Scene: {scene.name} — {scene.logline}.
This plate depicts {background.description}.

Paint in dense opaque gouache with transparent watercolor washes on heavy-tooth
textured paper, using sponge-dabbing, dry-brush work on bark and stone, and fine
splatter for dirt and damp mist. Gothic organic forms only — gnarled tangled
roots, arched burrows, sagging beams — with zero straight edges or digital
symmetry. Human-scale objects, if any, loom gargantuan from this rodent
macro perspective.

Lighting: {background.lighting}. Keep 60-70% of the frame in deep shadow, warm
amber/gold light at the epicenter shifting to cool teal/indigo ambient shadow,
a soft airbrushed glow radiating from the light source, and volumetric dust
motes in the light path. Mood: {background.mood}.

Frame from a low rodent macro camera (2-12 inches above ground) with the
environment dominating the frame, a heavy vignette, and soft-focus dark
foreground silhouettes (roots, vines, cracked edges) occluding 20-30% of the
frame borders. No characters, no text, no watermarks."""


def build_scene_review_system_instruction(scene: SceneSpec, background: BackgroundSpec) -> str:
    return f"""You are a world-class background art director and production designer specializing in Don Bluth's iconic 1980s dark fantasy feature animation style (e.g., The Secret of NIMH, 1982).

Your job is to critically review the supplied background plate for the scene "{scene.name}" ({scene.logline}) against the requested prompt, analyze any previous review iterations you gave on earlier images, and decide whether the current image meets feature-film production standards.

When past review iterations are provided:
- Treat them as clearly labeled historical feedback from previous rounds in this review process.
- Critique the results of your past instructions: evaluate whether the image generator successfully implemented your prior feedback/revised prompt, or if it introduced new flaws.
- Refine and improve your review process based on how effectively previous prompt changes moved the artwork toward the target aesthetic.

Apply Don Bluth's strict 1980s aesthetic & technical visual criteria for this background plate:
1. Environment Content: The plate must depict {background.description}. Gothic organic forms only (gnarled roots, arched burrows, sagging beams); zero straight edges, zero modern props, zero digital symmetry. Rodent macro scale: human objects must loom gargantuan.
2. Medium & Texture: Dense opaque gouache and transparent watercolor on heavy-tooth paper with sponge-dabbing, dry-brush, and fine splatter texture. Reject clean vector art, 3D CGI, smooth plastic gradients, photographic realism, or digital glow filters.
3. Lighting & Palette: {background.lighting}. A single clearly identifiable practical light source; 60-70% of frame in deep shadow; warm amber/gold key against cool teal/indigo ambient shadow; soft airbrushed bloom around the source; volumetric dust motes in the light path.
4. Staging & Depth: Low rodent macro camera (2-12 inches above ground); environment dominating the frame; soft-focus dark foreground silhouettes occluding 20-30% of frame borders; heavy vignette. The plate must feel {background.mood}.
5. Clean Plate & Narrative Register (HARD GATE): NO characters or creatures anywhere in frame, no text, logos, or watermarks — this is a production background for cel compositing. And the environment itself must make the viewer FEEL the scene's role in the story at first glance ({scene.logline}). Ask yourself: "Could this exact background only exist in The Secret of NIMH (1982), and does it trigger the precise emotional reaction the narrative demands?" A competent, pretty, generic fantasy backdrop that could be dropped into any modern cartoon FAILS this criterion even when every technical box above is checked.

Be exacting and demanding. Do NOT accept merely because an image is visually pleasing or artistic if it misses key Don Bluth style mandates or background plate needs. NEVER accept an image that fails criterion 5, no matter how polished or technically correct it is: "generic but well-executed" is always a rejection. When rejecting, provide a complete, self-contained revised image prompt that precisely remedies all identified defects — especially any missing narrative emotional register or Bluth-specific environment DNA — while preserving all correct details.

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


def write_iterations(destination: Path, subject_name: str, attempts: list[Attempt], accepted: bool) -> None:
    result = "accepted" if accepted else f"not accepted within the {MAX_ITERATIONS}-iteration limit"
    lines = [
        f"# {subject_name} Generation Iterations",
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


def build_subjects(args: argparse.Namespace) -> list[Subject]:
    """Resolve the CLI target into the list of blueprint subjects to generate."""
    if args.character:
        character = get_character(args.character)
        output = (
            Path(args.output)
            if args.output
            else Path("out") / "blueprint" / slug(character.name)
        )
        return [
            Subject(
                label=f"character {character.name!r}",
                display_name=character.name,
                output_dir=output,
                style_slug=slug(character.name),
                initial_prompt=build_initial_prompt(character),
                review_instruction=build_review_system_instruction(character),
            )
        ]

    scene = get_scene(args.scene)
    base = Path(args.output) if args.output else Path("out") / "blueprint" / scene.slug
    return [
        Subject(
            label=f"scene {scene.name!r} background {background.key!r}",
            display_name=f"{scene.name} — {background.key} background",
            output_dir=base / background.key,
            style_slug=f"{scene.slug}-{background.key}",
            initial_prompt=build_scene_initial_prompt(scene, background),
            review_instruction=build_scene_review_system_instruction(scene, background),
        )
        for background in scene.backgrounds
    ]


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
            existing_prompt_path, len(current_prompt),
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
    if not 1 <= args.max_iterations <= MAX_ITERATIONS:
        raise ValueError(f"--max-iterations must be between 1 and {MAX_ITERATIONS}.")

    subjects = build_subjects(args)

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

    client = genai.Client(api_key=gemini_key)

    logger.info("Image model: %s | Review model: %s | Max iterations: %d",
                args.image_model, args.review_model, args.max_iterations)
    logger.info("Subjects to generate: %d (%s)",
                len(subjects), ", ".join(subject.label for subject in subjects))

    exit_code = 0
    for subject in subjects:
        result = run_subject(client, openrouter_key, args, subject)
        if result != 0:
            exit_code = result
    return exit_code


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    available_characters = ", ".join(list_character_names())
    available_scenes = ", ".join(f"{spec.name} ({spec.slug})" for spec in SCENES.values())
    parser = argparse.ArgumentParser(
        description=(
            "Generate and review Don Bluth blueprints for the Rats of NIMH "
            "project: either a character style guide (--character) or the 1-2 "
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
        parser.error(f"API request timed out (the reviewer LLM may be slow or unreachable): {error}")
    except requests.exceptions.RequestException as error:
        parser.error(f"Network error during API call: {error}")
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
