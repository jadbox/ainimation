#!/usr/bin/env python3
"""Expand a short scene idea into a detailed 30-second scene design document.

Uses Gemini 3.6 Flash to turn a one-line scene description into a
production-ready scene script covering character locations, camera location,
camera movement, scene animations, sounds, and music — all held to the Don
Bluth direction and lighting rules in ``readme.md``. The scene is structured
as three clearly marked 10-second segments (``## Segment 0 (0:00-0:10)`` ...)
so ``src/animator.py`` can generate each segment as its own clip.

The result is written to ``out/scripts/<name>.md``.

Usage:
    python src/scene_script.py --prompt "Mrs. Brisby meets the Great Owl" \
        --name "frisby_meets_greatowl"
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from pathlib import Path

from google import genai
from google.genai import types

from blueprint_generator.characters import list_character_names

logger = logging.getLogger("scene_script")

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_SCRIPTS_DIR = Path("out") / "scripts"


def build_system_instruction() -> str:
    roster = ", ".join(list_character_names())
    return f"""You are a world-class animation director and production designer specializing in Don Bluth's iconic 1980s dark fantasy feature animation (The Secret of NIMH, 1982). You are designing a scene for a short film adaptation of The Rats of NIMH.

Expand the user's short scene description into a detailed, production-ready scene design document tailored for exactly 30 seconds of screen time, structured as THREE 10-second segments. The document must cover character locations, camera location, camera movement, scene animations, sounds, and music.

HARD DIRECTION RULES (from the project style bible — every choice must obey them):
- Camera height stays at rodent eye-level (2-12 inches above ground) unless a shot is deliberately a predator POV. Environments dominate ~70% of frame volume; characters occupy the lower third.
- Every shot orbits a single identifiable practical light source (candle, lantern, amulet glow, moonlight shaft). 60-70% of the frame sits in deep shadow.
- Warm key light (amber/gold, 2000K-3200K) against cool ambient shadow (teal/indigo/slate purple, 7000K-10000K). 360-degree rim lighting separates character silhouettes from dark backgrounds.
- Soft-focus dark foreground elements (roots, vines, cobwebs, cracked glass) obscure 20-30% of frame borders for a "peeping into a secret world" feel.
- Animation mechanics: animating on twos (12fps) for dialogue/moderate motion, on ones (24fps) for action climaxes; deep anticipation crouches before major actions; heavy recoil on landing; drag and follow-through on ears, whiskers, tails, and capes; held emotional poses with micro-movements (trembling fingers, double-blinks, chest breathing, whisker twitches).
- Tone: cozy danger, reverence and awe, vulnerability at small scale, storybook gothic.
- Sound and music must match the register: hushed, tender, mournful; sparse orchestration with music-box/celesta colors for sanctuary, low strings and choir for awe, percussive dread for danger.

CHARACTER ROSTER (use only these characters, spelled exactly as listed):
{roster}

DRAMATIC ARCHITECTURE (required — this is what makes the scene a powerful short film, not a moving postcard):
- Identify the scene's DRAMATIC QUESTION (e.g., "Will Mr Ages give her the cure?") and state it in the Logline section.
- Structure the three segments as a miniature three-act arc:
  * Segment 0 = ARRIVAL & WANT: the protagonist enters the space; we feel what they need before anyone speaks.
  * Segment 1 = CONFRONTATION & TURN: the obstacle or revelation; the scene's emotional register pivots here (fear -> hope, hope -> dread, distance -> intimacy).
  * Segment 2 = RESOLUTION & HOOK: the dramatic question is answered through action (a gift, a decision, a warning), and the final held image points toward the next story movement.
- Give the scene ONE key story object (e.g., a glowing medicine vial) that embodies its meaning; the camera and lighting must treat it as sacred when it appears.
- Design ONE unforgettable story image — the single frame a viewer would remember — and build a held beat around it.
- WORK ALL THE ELEMENTS AT THE TURN: when the emotion pivots, the camera distance, lighting temperature/pool size, sound bed, and music must all shift together to tell the story wordlessly.
- Dialogue is minimal and essential: 2-4 short lines total, each carrying story weight.

OUTPUT FORMAT — return Markdown with EXACTLY these section headers, in this order:
# <evocative scene title>
## Logline
(one or two sentences naming the protagonist, their want, and the scene's dramatic question)
## Characters in Scene
(one bullet per character, using the exact roster names, e.g. "- Mrs Brisby")
## Setting & Light
(the shared stage, kept brief: the environment and its key props, the scene's ONE story object if any, the single dominant practical light source, and the baseline warm-vs-cool palette — everything here is constant across all three segments)
## Segment 0 (0:00-0:10)
### Story Beat
(one sentence: this segment's role in the three-act arc and its emotional register)
### Blocking & Character Locations
(where each character is and how they move within this segment — blocking must express the power dynamic between them)
### Camera
(camera placement/height for this segment plus every movement — push-ins, tracking, cuts, held beats — with timings; note how camera distance closes or widens with the emotion)
### Animation & Acting
(the animation beats for this segment, noting ones/twos, anticipation, drag, follow-through, held poses, and micro-movements; acting must externalize what each character feels but does not say)
### Dialogue
(the line(s) spoken in this segment, attributed, e.g. `MRS BRISBY: "..."` — or the word None)
### Sound & Music
(the sound bed, key sync sounds, and music behavior inside this segment; both must shift with the emotional turn)
### Shot Steps
(3-5 numbered, timed steps covering the full 10 seconds, e.g. `1. (0:00-0:03) ...`)
## Segment 1 (0:10-0:20)
(the same seven ### sub-sections)
## Segment 2 (0:20-0:30)
(the same seven ### sub-sections)

SEGMENT RULES — the three Segment sections are the shooting plan and must:
- Use the exact headers shown above (`## Segment 0 (0:00-0:10)`, etc.) so tooling can parse the 10-second boundaries.
- Be FULLY SELF-CONTAINED: every production detail lives inside a Segment's own ### sub-sections. Tooling extracts each Segment individually (with only the Logline and Setting & Light attached) to prompt a video model, so a Segment must NEVER reference information defined in another Segment or in a section that no longer exists.
- Chain into the three-act arc described above; each Segment must state in its Shot Steps the exact pose/composition it begins on (matching the previous Segment's final frame) so the generated clips can be concatenated seamlessly.

Be specific and cinematic. Every visual choice must be filmable under the direction rules above, and every element must serve the story."""


def build_user_prompt(scene_name: str, prompt: str) -> str:
    return (
        f"Scene name (production slug): {scene_name}\n"
        f"Short scene description: {prompt}\n\n"
        "Expand this into the full 30-second scene design document now, "
        "following the exact output format (including the three 10-second "
        "Segment sections) and direction rules."
    )


def slugify_name(name: str) -> str:
    """Validate/normalize a scene name into a filesystem-safe slug."""
    slug = name.strip().lower().replace(" ", "-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
        raise ValueError(
            f"Scene name {name!r} must start with a letter or digit and contain "
            "only lowercase letters, digits, hyphens, and underscores."
        )
    return slug


def require_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this command.")
    return key


def run(args: argparse.Namespace) -> int:
    scene_name = slugify_name(args.name)
    output = Path(args.output) if args.output else DEFAULT_SCRIPTS_DIR / f"{scene_name}.md"
    if output.exists() and not args.force:
        raise RuntimeError(
            f"{output} already exists. Pass --force to overwrite it."
        )

    client = genai.Client(api_key=require_api_key())

    logger.info("=== Expanding scene %r with model=%s ===", scene_name, args.model)
    logger.info("Short prompt: %s", args.prompt)
    response = client.models.generate_content(
        model=args.model,
        contents=build_user_prompt(scene_name, args.prompt),
        config=types.GenerateContentConfig(
            system_instruction=build_system_instruction(),
            temperature=0.7,
        ),
    )
    document = (response.text or "").strip()
    if not document:
        raise RuntimeError("Gemini returned an empty scene document.")
    if not re.search(r"^##\s*Segment\s+0\s*\(", document, flags=re.MULTILINE | re.IGNORECASE):
        logger.warning(
            "The generated document has no '## Segment 0 (...)' header; "
            "src/animator.py will treat it as a single segment."
        )

    header = (
        f"<!-- Generated by scene_script.py (model: {args.model}) from prompt: "
        f"{args.prompt!r} -->\n\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header + document + "\n", encoding="utf-8")
    print(f"Wrote scene script: {output}")
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description=(
            "Expand a short scene description into a detailed 30-second Don "
            "Bluth scene design document (three 10-second segments) written "
            "to out/scripts/<name>.md."
        )
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Short scene description to expand, e.g. 'Mrs. Brisby meets the Great Owl'.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help=(
            "Production slug for the scene; the script is written to "
            "out/scripts/<name>.md (e.g. frisby_meets_greatowl)."
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini text model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: out/scripts/<name>.md).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing scene script.",
    )
    args = parser.parse_args()

    try:
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
