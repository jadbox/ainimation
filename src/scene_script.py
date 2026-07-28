#!/usr/bin/env python3
"""Expand an abridged story scene from ``movie.yml`` into a detailed 30-second scene design document.

Uses Gemini 3.6 Flash to turn the ``story:`` section's abridged scene beats
(scene reference, characters, key emotions, important actions/talking points,
and character eyelines/expressions) into a production-ready scene script
covering character locations, camera location, camera movement, scene
animations, sounds, and music — all held to the direction and lighting rules in
``movie.yml``. The scene is structured as three clearly marked 10-second
segments (``## Segment 0 (0:00-0:10)`` ...) so ``animator`` can generate each
segment as its own clip.

The result is written to ``out/scripts/<name>.md``.

Usage:
    python src/scene_script.py                      # list available story scenes
    python src/scene_script.py --name "frisby_visits_mr_ages"
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from pathlib import Path

from google import genai
from google.genai import types

from movie_config import (
    SceneSpec,
    StorySceneSpec,
    get_movie_info,
    get_scene,
    get_story_scene,
    list_character_names,
    list_story_scenes,
)

logger = logging.getLogger("scene_script")

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_SCRIPTS_DIR = Path("out") / "scripts"


def build_system_instruction() -> str:
    movie_info = get_movie_info()
    roster = ", ".join(list_character_names())
    rules = "\n".join(f"- {rule}" for rule in movie_info.hard_direction_rules)
    return f"""You are a world-class animation director and production designer specializing in {movie_info.style}. You are designing a scene for {movie_info.adaptation}.

Expand the user's abridged story beat into a detailed, production-ready scene design document tailored for exactly 30 seconds of screen time, structured as THREE 10-second segments. The document must cover character locations, camera location, camera movement, scene animations, sounds, and music. Every detail matters — nothing in the document may be generic or interchangeable.

HARD DIRECTION RULES (from the project style bible — every choice must obey them):
{rules}

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

MOMENT-BY-MOMENT CHRONOLOGICAL PARAGRAPHS (required — merge camera, actions, speech, and sound into unified chronological paragraphs separated ONLY by double line breaks):
- INITIAL SPATIAL OBJECT MAPPING (required — first sentence of every segment MUST define scene spatial layout relative to camera): The VERY FIRST SENTENCE of every Segment MUST be a semi-colon separated (`;`) list explicitly defining all characters, key props, and light sources in frame in reference to camera coordinates (left, right, center, top-left, middle, bottom-right, etc.). Example: `MRS BRISBY enters on the right; MR AGES is sitting at the reading desk on the left; an oil lantern provides lighting to the room near the middle-left; towering book stacks fill the background.`
- DIRECT, LITERAL DIRECTIONAL LANGUAGE (required — assume video generator needs clear, direct, 100% literal direction): STRICTLY BAN abstract poetry or figurative lighting phrases inside segment actions (e.g. NEVER write "From the deep indigo shadows" or "shadow lanes"). Instead, use direct physical directives like `MRS BRISBY, emerging from the dark right exterior of the room, steps forward into the illuminated center floor...` or `MR AGES, sitting at the desk on the left, turns his head 45 degrees to look right...`.
- NO SUB-HEADINGS INSIDE SEGMENTS: Inside each `## Segment N (span)` section, write the chronological moments as paragraphs separated ONLY by double line breaks (`\n\n`). Do NOT include `### Moment` headers or bullet point lists within segments.
- SINGLE CONTINUOUS CAMERA CUT: Each segment must represent a single continuous camera shot with a consistent camera perspective — strictly NO sudden scene cuts, jump cuts, or camera angle changes during the segment.
- MERGE ALL DETAILS INTO EACH MOMENT PARAGRAPH: Each moment paragraph must be an elegant, concise, chronological paragraph that seamlessly merges ALL relevant facts for that exact timeframe as they happen in real time:
  1. What the camera is doing (height, smooth continuous movement, composition, lens framing).
  2. Character locations, ground planes, depth planes (midground/foreground/background, left/right), and eyelines.
  3. Ongoing physical tasks and physical engagement with props/environment (e.g. reading a book, tracing text with a claw, wringing a cape, sorting herbs).
  4. Physical reactions to dialogue and arrivals (body language, paws freezing mid-gesture, head turns, chest breathing, whisker/ear twitches).
  5. Attributed dialogue spoken during that moment.
  6. Sounds and music occurring in sync with the action.

DIALOGUE ATTRIBUTION FORMAT (required — explicitly identify speaker species/descriptor and frame location):
- Whenever a character speaks, ALWAYS attribute dialogue with their species/descriptor and frame position: e.g. `MRS BRISBY (field mouse on the right): "..."` or `MR AGES (mouse on the left): "..."` or `NICODEMUS (rat on the left): "..."`. This ensures the video generator never confuses which character is speaking.

EYELINES, BODY & CAMERA AS NARRATIVE (required — the audience reads the story in the eyes, the body, and the lens):
- STATE WHERE EVERY CHARACTER IS LOOKING IN EVERY BEAT: name the exact object of each gaze (the other character's eyes, the story object, the shadows). Characters MUST look at each other or at scene objects — NEVER look directly into the camera lens unless explicitly instructed as a direct POV shot.
- SHARED DEPTH & STAGING FOR INTERACTIONS: interacting characters MUST be staged on the SAME GENERAL DEPTH PLANE (e.g., both in the MIDGROUND side-by-side or at a 3/4 angle across a shared desk) so both characters' faces and eyelines align naturally in 3/4 profile or profile view. NEVER place one character far in the background directly behind another foreground character during dialogue or interaction, which forces one character to face away from the camera or stare into the lens.
- CONTINUOUS LIVING SECONDARY ANIMATION: every character in frame MUST be actively alive with continuous secondary motion in every second of the clip (rhythmic chest breathing, shuffling papers/herbs, ear or whisker twitches, weight shifts, finger twitches). NEVER describe a character as "doing nothing", "standing rigid", or behaving like a static robot.
- CHARACTER ACTING, ENGAGEMENT & MULTI-TASKING: Every character must be actively engaged in a specific physical task with their environment or props (e.g. Mr Ages reading a large yellowed book, tracing lines with his claw and turning pages; Mrs Brisby wringing her red cape while stepping forward). Describe how characters balance ongoing physical tasks with reacting to dialogue and arrivals (e.g. "Mr Ages is reading a book when Mrs Brisby enters; at first he remains focused on tracing the text with his claw, speaking politely without immediately looking up, before pausing his claw over the page and peering up over his spectacles").
- ACTIVE LISTENING & PHYSICAL IMPACT OF WORDS: Describe how a character's body, hands, eyes, and posture react when hearing dialogue (paws freezing mid-gesture over a book page, shoulders drooping, head turning, breath catching in the chest).
- STATE WHAT EVERY CHARACTER DOES WITH THEIR BODY: posture, weight shifts, hands, ears, tail, breath. The body must externalize what each character feels but does not say (a wrung tail, a guarded turned shoulder, a lean-in that betrays hope).
- MAKE THE CAMERA AN ACTIVE STORYTELLER: every placement, push-in, track, hold, and pull-back must be emotionally motivated and stated with its reason — camera distance mirrors emotional distance; a slow push-in grows intimacy or dread; a frozen, held frame is reverence. Where the characters look and what their bodies do must work together with the camera's movement to tell the narrative.

DEPTH & OCCLUSION (required — generative video flattens space unless depth is spelled out):
- Assign every character and every key set piece an explicit depth plane in every Moment: FOREGROUND (soft-focus occluders at the frame edges), MIDGROUND (furniture and props the camera looks past), or BACKGROUND (walls, stacks, deep shadow).
- State the exact ground plane each character stands on (the floor, a path, a ledge). Characters NEVER stand on top of furniture or props (tables, desks, jars, lanterns, books) unless the scene specifically calls for climbing; when in doubt, feet stay on the floor.
- For every set piece sitting between the camera and a character, state the occlusion explicitly — what it hides and when.

DIALOGUE CRAFT & LITERARY ELEGANCE (required — dialogue must be poetic, emotional, and deeply character-driven):
- BANNED DIALOGUE TROPES: STRICTLY FORBID generic TV scolding, modern slang, melodrama, or harsh outbursts (e.g. NEVER write lines like "I told you...", "woman!", "calm down!", "hey you").
- CLASSIC FEATURE ANIMATION TONE: Mimic the elevated, literary, 1980s theatrical tone of classic Don Bluth cinema (The Secret of NIMH). Dialogue must feel poetic, rhythmic, dignified, and emotionally haunting.
- CHARACTER-SPECIFIC VOCABULARY & SUBTEXT:
  * Mr. Ages: An elderly scholar and physician; speaks with weary gravity, precision, and reluctant tenderness. Uses terms like "madam", "child", "lung-fever", "bright eyes". Never barks or insults.
  * Mrs. Brisby: A devoted, vulnerable mother; speaks in breathless, tender, courageous pleas. Every word is weighted with love for her children.
  * Nicodemus: An ancient, monumental leader; speaks with quiet, resonant wisdom and storybook poetry.
- SUBTEXT OVER EXPOSITION: Lines must convey feeling and stakes through subtext rather than blunt facts (e.g. instead of "He has pneumonia and will die", write "Pneumonia... Bright eyes, madam. The lung-fever will take a young one before the morning frost unless we quiet the fire in his chest.").
- MINIMAL & ESSENTIAL: Keep dialogue to 2-4 short, impactful lines total across the entire 30-second scene. Every spoken word must carry immense narrative and emotional weight.

OUTPUT FORMAT — return Markdown with EXACTLY these section headers, in this order:
# <evocative scene title>
## Logline
(one or two sentences naming the protagonist, their want, and the scene's dramatic question)
## Characters in Scene
(one bullet per character, using the exact roster names, e.g. "- Mrs Brisby")
## Setting & Light
(the shared stage, kept brief: the environment and its key props with their depth planes — foreground occluders, midground furniture, background walls — the scene's ONE story object if any, the single dominant practical light source, and the baseline warm-vs-cool palette — everything here is constant across all three segments)
## Segment 0 (0:00-0:10)
(detailed chronological moment paragraphs separated ONLY by double line breaks — NO ### headers or sub-headings within the segment. The camera remains one single continuous cut with consistent framing)

## Segment 1 (0:10-0:20)
(detailed chronological moment paragraphs separated ONLY by double line breaks — NO ### headers or sub-headings within the segment)

## Segment 2 (0:20-0:30)
(detailed chronological moment paragraphs separated ONLY by double line breaks — NO ### headers or sub-headings within the segment)

SEGMENT RULES — the three Segment sections are the shooting plan and must:
- Use the exact headers shown above (`## Segment 0 (0:00-0:10)`, etc.) so tooling can parse the 10-second boundaries.
- Be FULLY SELF-CONTAINED: every production detail lives inside a Segment's paragraphs. Tooling extracts each Segment individually (with only the Logline and Setting & Light attached) to prompt a video model, so a Segment must NEVER reference information defined in another Segment or in a section that no longer exists.
- Chain into the three-act arc described above; each Segment must state in its opening paragraph the exact pose/composition it begins on (matching the previous Segment's final frame) so the generated clips can be concatenated seamlessly.

Be specific and cinematic. Every visual choice must be filmable under the direction rules above, and every element must serve the story."""


def build_user_prompt(story: StorySceneSpec, scene: SceneSpec) -> str:
    characters = ", ".join(story.characters)
    emotions = "\n".join(f"  - {item}" for item in story.emotions)
    actions = "\n".join(f"  - {item}" for item in story.actions)
    looks = "\n".join(f"  - {item}" for item in story.looks)
    backgrounds = "\n".join(
        f"  - ({bg.key}) {bg.description}\n"
        f"    Lighting: {bg.lighting}\n"
        f"    Mood: {bg.mood}"
        for bg in scene.backgrounds
    )
    return (
        f"Scene name (production slug): {story.name}\n"
        f"Story beat: {story.title}\n"
        f"Location: {scene.name} — {scene.logline}\n"
        "Setting reference (production background plates — keep the Setting & Light "
        f"section consistent with them):\n{backgrounds}\n\n"
        f"Characters in scene: {characters}\n"
        f"Key emotions & feelings:\n{emotions}\n"
        f"Important actions & talking points:\n{actions}\n"
        f"Where the characters are looking & their facial expressions:\n{looks}\n\n"
        "Expand this abridged story beat into the full 30-second scene design document now, "
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
    story = get_story_scene(args.name)
    scene = get_scene(story.scene)
    scene_name = slugify_name(story.name)
    output = Path(args.output) if args.output else DEFAULT_SCRIPTS_DIR / f"{scene_name}.md"
    if output.exists() and not args.force:
        raise RuntimeError(
            f"{output} already exists. Pass --force to overwrite it."
        )

    client = genai.Client(api_key=require_api_key())

    logger.info("=== Expanding story scene %r with model=%s ===", scene_name, args.model)
    logger.info("Story beat: %s (location: %s)", story.title, scene.name)
    response = client.models.generate_content(
        model=args.model,
        contents=build_user_prompt(story, scene),
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
        f"<!-- Generated by scene_script.py (model: {args.model}) from story scene: "
        f"{story.name!r} (movie.yml story section) -->\n\n"
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
    movie_info = get_movie_info()
    parser = argparse.ArgumentParser(
        description=(
            f"Expand an abridged story scene from movie.yml for {movie_info.title} "
            "into a detailed 30-second scene design document (three 10-second "
            "segments) written to out/scripts/<name>.md. Run without --name to "
            "list the available story scenes."
        )
    )
    parser.add_argument(
        "--name",
        default=None,
        help=(
            "Story scene name from the movie.yml `story:` section; the script is "
            "written to out/scripts/<name>.md (e.g. frisby_visits_mr_ages). "
            "Omit to list all available story scenes."
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

    if not args.name:
        print("Available story scenes in movie.yml (pass one to --name):\n")
        for spec in list_story_scenes():
            print(f"  {spec.name}")
            if spec.title:
                print(f"      {spec.title}")
            print(f"      scene: {spec.scene} | characters: {', '.join(spec.characters)}")
        return

    try:
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
