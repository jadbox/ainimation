#!/usr/bin/env python3
"""Expand an abridged story scene from ``movie.yml`` into detailed segment design files.

Uses Gemini 3.6 Flash to turn the ``story:`` section's abridged scene beats
(scene reference, characters, key emotions, important actions/talking points,
and character eyelines/expressions) into production-ready segment prompts
covering character locations, camera location, camera movement, scene
animations, sounds, and music — all held to the direction and lighting rules in
``movie.yml``.

The scene is exported as one prompt file per segment:
``out/scripts/<name>_part0.md``, ``out/scripts/<name>_part1.md``, etc.

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
    CHARACTERS,
    SceneSpec,
    StorySceneSpec,
    get_character,
    get_movie_info,
    get_scene,
    get_story_scene,
    list_character_names,
    list_story_scenes,
    standardize_name,
)

logger = logging.getLogger("scene_script")

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_SCRIPTS_DIR = Path("out") / "scripts"


def build_system_instruction() -> str:
    movie_info = get_movie_info()
    roster_names = list_character_names()
    roster = ", ".join(roster_names)
    rules = "\n".join(f"- {rule}" for rule in movie_info.hard_direction_rules)
    sample_speaker1 = roster_names[0] if roster_names else "CHARACTER ONE"
    sample_speaker2 = roster_names[1] if len(roster_names) > 1 else "CHARACTER TWO"
    char_voices = "\n".join(
        f"  * {spec.display_name()}: {spec.identity}; {spec.appearance}."
        + (f" <VOICE>{spec.voice}</VOICE>" if spec.voice else "")
        for spec in CHARACTERS.values()
    )
    return f"""You are a world-class animation director and production designer specializing in {movie_info.style}. You are designing a scene for {movie_info.adaptation}.

Expand the user's abridged story beat into a detailed, production-ready scene design document tailored for exactly 30 seconds of screen time, structured as THREE 10-second segments. The document must cover character blocking (where each character stands or moves to in every beat), camera location, camera movement, scene animations, sounds, and music. Every detail matters — nothing in the document may be generic or interchangeable.

HARD DIRECTION RULES (from the project style bible — every choice must obey them):
{rules}

CHARACTER ROSTER (use only these characters, spelled exactly as listed in ALL CAPS):
{roster}

DRAMATIC ARCHITECTURE (required — this is what makes the scene a powerful short film, not a moving postcard):
- Identify the scene's DRAMATIC QUESTION (e.g., "Will {sample_speaker2} give her the cure?") and state it in the Logline section.
- Structure the three segments as a miniature three-act arc:
  * Segment 0 = ARRIVAL & WANT: the protagonist enters the space; we feel what they need before anyone speaks.
  * Segment 1 = CONFRONTATION & TURN: the obstacle or revelation; the scene's emotional register pivots here (fear -> hope, hope -> dread, distance -> intimacy).
  * Segment 2 = RESOLUTION & HOOK: the dramatic question is answered through action (a gift, a decision, a warning), and the final held image points toward the next story movement.
- Give the scene ONE key story object (e.g., a glowing medicine vial) that embodies its meaning; the camera and lighting must treat it as sacred when it appears.
- Design ONE unforgettable story image — the single frame a viewer would remember — and build a held beat around it.
- WORK ALL THE ELEMENTS AT THE TURN: when the emotion pivots, the camera distance, lighting temperature/pool size, sound bed, and music must all shift together to tell the story wordlessly.

MOMENT-BY-MOMENT CHRONOLOGICAL PARAGRAPHS (required — merge camera, actions, speech, and sound into unified chronological paragraphs separated ONLY by double line breaks):
- TIME-CODED BEATS (required — distribute the full 10 seconds explicitly and mark every change): Open EACH chronological moment paragraph with a bracketed timecode showing its exact sub-window within the segment, e.g. `[0:00-0:03]`. The timecodes across a segment must tile the whole 10 seconds with no gaps and no overlaps, and every discrete change of blocking, body, or expression gets its OWN timecoded beat (so a repositioning, a hand gesture, or an expression shift never shares a beat with a later, different one).
- INITIAL SPATIAL OBJECT MAPPING (required — first sentence of every segment MUST define scene spatial layout relative to camera): The VERY FIRST SENTENCE of every Segment MUST be a semi-colon separated (`;`) list explicitly defining all characters, key props, and light sources in frame in reference to camera coordinates (left, right, center, top-left, middle, bottom-right, etc.). Example: `{sample_speaker1} enters on the right; {sample_speaker2} is sitting at the reading desk on the left; an oil lantern provides lighting to the room near the middle-left; towering book stacks fill the background.`
- DIRECT, LITERAL DIRECTIONAL LANGUAGE (required — assume video generator needs clear, direct, 100% literal direction): STRICTLY BAN abstract poetry or figurative lighting phrases inside segment actions (e.g. NEVER write "From the deep indigo shadows" or "shadow lanes"). Instead, use direct physical directives like `{sample_speaker1}, emerging from the dark right exterior of the room, steps forward into the illuminated center floor...` or `{sample_speaker2}, sitting at the desk on the left, turns his head 45 degrees to look right...`.
- NO SUB-HEADINGS INSIDE SEGMENTS: Inside each `## Segment N (span)` section, write the chronological moments as paragraphs separated ONLY by double line breaks (`\n\n`). Do NOT include `### Moment` headers or bullet point lists within segments.
- SINGLE CONTINUOUS CAMERA CUT: Each segment must represent a single continuous camera shot with a consistent camera perspective — strictly NO sudden scene cuts, jump cuts, or camera angle changes during the segment.
- MERGE ALL DETAILS INTO EACH MOMENT PARAGRAPH: Each moment paragraph must be an elegant, concise, chronological paragraph that seamlessly merges ALL relevant facts for that exact timeframe as they happen in real time:
  1. What the camera is doing (height, smooth continuous movement, composition, lens framing).
  2. Character blocking: where each character currently stands and moves to (ground planes, depth planes (midground/foreground/background, left/right), their hand/arm work, and eyelines).
  3. Ongoing physical tasks and physical engagement with props/environment (e.g. reading a book, tracing text with a claw, wringing a cape, sorting herbs).
  4. Physical reactions to dialogue and arrivals (body language, paws freezing mid-gesture, head turns, chest breathing, whisker/ear twitches).
  5. Attributed dialogue spoken during that moment.
  6. Sounds and music occurring in sync with the action.
  7. EXPRESSION & EMOTIONAL READS (required in every beat): name each character's facial expression and emotional register in that beat (e.g. "his eyes narrow with dry suspicion", "her brow furrows, lips trembling as hope flickers"), and state how that expression changes from the previous beat (e.g. "the suspicion melts from his face into quiet solemnity"). A character must never be un-expressed or reading identically across two consecutive beats unless it is a deliberate frozen reverence beat, which must be stated as such.

BLOCKING & MISE-EN-SCÈNE — DIRECT THE STAGE LIKE A THEATRE DIRECTOR (required — the most common failure is characters frozen in one spot, so treat stage positions as an explicit, ever-evolving choreography):
- STATE WHERE EVERY CHARACTER STANDS OR MOVES TO IN EVERY BEAT: at every moment, explicitly name each character's current ground-plane position and, whenever that position changes, the exact word-driven motion that gets them there (e.g. "standing center-right", "steps two paces toward the desk on the left", "circles around to the far right behind the chair", "backs up one step to the doorframe"). A character should NEVER remain in the exact same spot across an entire segment — reposition, approach, retreat, or shift facing within each beat.
- TRACK BLOCKING ACROSS THE FULL SCENE: as the scene progresses segment to segment, keep characters moving between ground-plane positions (front/mid/back, left/center/right) so their spatial relationship to each other, the camera, and the story object is always precise and never static. State each new position the instant a character starts moving, not only after they arrive.
- DIRECT THE HAND & BODY WORK OF EVERY CHARACTER IN EVERY BEAT: describe concretely what each character is physically DOING with their hands while speaking or listening — wringing or smoothing a cape, tracing a page with a claw, gesturing a point, folding paws, gripping a lantern handle, adjusting spectacles, twisting a button. Pair every spoken line and every moment of listening to an explicit hand/arm action, and describe the body (posture, weight shift, lean, shoulder turn) that goes with it.
- NOTE WHEN BODY MOVEMENT CHANGES: whenever a character's hands, posture, or position shift in response to a line, a beat, or an arrival, call out the change explicitly ("her paws freeze mid-gesture", "he straightens from the desk and turns"), so the video generator animates a new action rather than repeating the same pose.

DIALOGUE ATTRIBUTION FORMAT (required — standardized ALL CAPS speaker name only):
- Whenever a character speaks, attribute dialogue using ONLY their standardized ALL CAPS name followed directly by a colon: e.g. `{sample_speaker1}: "..."` or `{sample_speaker2}: "..."`.
- STRICTLY DO NOT include parentheticals, species descriptors, or location descriptors next to the speaker's name (e.g. NEVER write `{sample_speaker1} (field mouse on the right):`).

EYELINES, BODY & CAMERA AS NARRATIVE (required — the audience reads the story in the eyes, the body, and the lens):
- STATE WHERE EVERY CHARACTER IS LOOKING IN EVERY BEAT: name the exact object of each gaze (the other character's eyes, the story object, the shadows). Characters MUST look at each other or at scene objects — NEVER look directly into the camera lens unless explicitly instructed as a direct POV shot.
- SHARED DEPTH & STAGING FOR INTERACTIONS: interacting characters MUST be staged on the SAME GENERAL DEPTH PLANE (e.g., both in the MIDGROUND side-by-side or at a 3/4 angle across a shared desk) so both characters' faces and eyelines align naturally in 3/4 profile or profile view. NEVER place one character far in the background directly behind another foreground character during dialogue or interaction, which forces one character to face away from the camera or stare into the lens.
- CONTINUOUS LIVING SECONDARY ANIMATION: every character in frame MUST be actively alive with continuous secondary motion in every second of the clip (rhythmic chest breathing, shuffling papers/herbs, ear or whisker twitches, weight shifts, finger twitches). NEVER describe a character as "doing nothing", "standing rigid", or behaving like a static robot.
- PHYSICAL LOCOMOTION & NO TELEPORTING: Describe every change of position, location, or facing direction as explicit, continuous physical locomotion (e.g., stepping forward, walking, turning 45 degrees, pivoting). NEVER write action where characters abruptly appear in new spots or face new directions without describing the physical motion to get there, and NEVER create duplicate or ghost character copies.
- CHARACTER ACTING, ENGAGEMENT & MULTI-TASKING: Every character must be actively engaged in a specific physical task with their environment or props (e.g. {sample_speaker2} reading a large yellowed book, tracing lines with his claw and turning pages; {sample_speaker1} wringing her red cape while stepping forward). Describe how characters balance ongoing physical tasks with reacting to dialogue and arrivals (e.g. "{sample_speaker2} is reading a book when {sample_speaker1} enters; at first he remains focused on tracing the text with his claw, speaking politely without immediately looking up, before pausing his claw over the page and peering up over his spectacles").
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
{char_voices}
- SUBTEXT OVER EXPOSITION: Lines must convey feeling and stakes through subtext rather than blunt facts (e.g. instead of "He has pneumonia and will die", write "Pneumonia... Bright eyes, madam. The lung-fever will take a young one before the morning frost unless we quiet the fire in his chest.").
- MINIMAL & ESSENTIAL: Keep dialogue to 2-4 short, impactful lines total across the entire 30-second scene. Every spoken word must carry immense narrative and emotional weight.

OUTPUT FORMAT — return Markdown with EXACTLY these section headers, in this order:
# <evocative scene title>
## Logline
(one or two sentences naming the protagonist, their want, and the scene's dramatic question)
## Characters in Scene
(one bullet per character, using the exact roster names in ALL CAPS with voice directives in <VOICE> tags, e.g. "- {sample_speaker1} <VOICE>voice description...</VOICE>")
## Setting & Light
(the shared stage, kept brief: the environment and its key props with their depth planes — foreground occluders, midground furniture, background walls — the scene's ONE story object if any, the single dominant practical light source, and the baseline warm-vs-cool palette — everything here is constant across all three segments)
## Segment 0 (0:00-0:10)
(detailed chronological moment paragraphs separated ONLY by double line breaks — each paragraph opens with a [0:00-0:03]-style timecoded beat — NO ### headers or sub-headings within the segment. The camera remains one single continuous cut with consistent framing)

## Segment 1 (0:10-0:20)
(detailed chronological moment paragraphs separated ONLY by double line breaks — each paragraph opens with a [0:10-0:13]-style timecoded beat — NO ### headers or sub-headings within the segment)

## Segment 2 (0:20-0:30)
(detailed chronological moment paragraphs separated ONLY by double line breaks — each paragraph opens with a [0:20-0:23]-style timecoded beat — NO ### headers or sub-headings within the segment)

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


def parse_section(document: str, header_pattern: str) -> str:
    """Extract body text from a section heading matching header_pattern."""
    match = re.search(
        rf"^##\s+{header_pattern}\s*$", document, flags=re.MULTILINE | re.IGNORECASE
    )
    if not match:
        return ""
    body = document[match.end():]
    next_heading = re.search(r"^##\s", body, flags=re.MULTILINE)
    if next_heading:
        body = body[: next_heading.start()]
    return body.strip()


def parse_characters_in_scene(document: str) -> list[str]:
    """Extract roster character names from '## Characters in Scene'."""
    match = re.search(r"^##\s*Characters in Scene\s*$", document, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        return []
    section_lines: list[str] = []
    for line in document[match.end():].splitlines():
        if line.strip().startswith("##"):
            break
        section_lines.append(line)

    roster = {standardize_name(spec.name): spec.name for spec in CHARACTERS.values()}
    found: list[str] = []
    for line in section_lines:
        bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s*(.+?)\s*$", line)
        if not bullet:
            continue
        cleaned = re.sub(r"<VOICE>.*?</VOICE>", "", bullet.group(1), flags=re.IGNORECASE)
        candidate = standardize_name(cleaned)
        if candidate in roster and roster[candidate] not in found:
            found.append(roster[candidate])
    return found


def parse_segments_from_document(document: str) -> list[tuple[int, str, str]]:
    """Extract (index, span, body) tuples for each segment in document."""
    header_re = re.compile(
        r"^##\s+Segment\s+(\d+)\s*\(([^)]*)\)\s*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    matches = list(header_re.finditer(document))
    if not matches:
        return [(0, "0:00-0:30", document.strip())]

    segments: list[tuple[int, str, str]] = []
    for position, match in enumerate(matches):
        idx = int(match.group(1))
        span = match.group(2).strip()
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(document)
        body = document[start:end]
        next_heading = re.search(r"^##\s", body, flags=re.MULTILINE)
        if next_heading:
            body = body[: next_heading.start()]
        segments.append((idx, span, body.strip()))

    segments.sort(key=lambda s: s[0])
    return segments


def format_segment_base_prompt(
    scene_name: str,
    logline: str,
    setting: str,
    characters: list[str],
    span: str,
    segment_body: str,
) -> str:
    """Build the base prompt document for a single scene segment."""
    movie_info = get_movie_info()

    char_items: list[str] = []
    for char in characters:
        name_str = standardize_name(char)
        try:
            spec = get_character(char)
            voice_tag = f" <VOICE>{spec.voice}</VOICE>" if spec.voice else ""
        except ValueError:
            voice_tag = ""
        char_items.append(f"{name_str}{voice_tag}")
    char_header_str = ", ".join(char_items)

    span_note = f" (story time {span})" if span else ""

    setting_block = (
        f"=== SHARED SETTING & LIGHT (constant across the whole scene) ===\n{setting}\n\n"
        if setting
        else ""
    )

    return f"""In a single unbroken scene, in a single continuous shot with no scene cuts. Style: {movie_info.style_summary}

Scene: "{scene_name}" — {logline or 'see script below.'}

Characters appearing: {char_header_str}.
Match character designs EXACTLY to visual reference images. Do NOT use character references as initial frames.
{movie_info.camera_rules}

Depth & Staging (mandatory): Characters stay on ground planes (feet on floor, never standing on furniture/props unless explicitly climbing). 
Midground set pieces MUST occlude characters passing behind them. Interacting characters share the same depth plane in 3/4 or profile view.

Single continuous camera shot (mandatory): One single continuous shot from a consistent camera perspective. 
STRICTLY NO sudden scene cuts, jump cuts, shot transitions, or camera angle changes. Camera moves smoothly in continuous motion.

Eyeline & camera rules (mandatory): Characters MUST look at each other or at scene objects as directed in script — NEVER look directly into camera lens. Maintain 3/4 or profile eyelines.

Dialogue & speaker mandates (mandatory):
- ONLY the character explicitly declared as speaker in a dialogue line moves their mouth and lips to speak.
- All non-speaking characters MUST keep their mouths firmly CLOSED, remaining silent while reacting with active body language.

Continuous character motion & physical locomotion (mandatory):
- Every character in frame MUST be actively alive with continuous secondary movement (rhythmic breathing, weight shifts, ear/whisker twitches). NO character may freeze or stand rigid.
- STRICTLY NO teleporting, sudden position pops, fading in/out of character locations, or creating duplicate/ghost character copies in frame.
- ALWAYS use proper, continuous physical locomotion and movement (stepping, walking, turning, pivoting, climbing) whenever a character or item changes location or facing orientation in the script.

{setting_block}=== SCENE SCRIPT{span_note} ===
{segment_body}"""


def require_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this command.")
    return key


def run(args: argparse.Namespace) -> int:
    story = get_story_scene(args.name)
    scene = get_scene(story.scene)
    scene_name = slugify_name(story.name)

    if args.output:
        out_path = Path(args.output)
        if out_path.suffix == ".md":
            base_path = out_path.with_suffix("")
        else:
            base_path = out_path / scene_name
    else:
        base_path = DEFAULT_SCRIPTS_DIR / scene_name

    base_path.parent.mkdir(parents=True, exist_ok=True)

    part0_file = Path(f"{base_path}_part0.md")
    if part0_file.exists() and not args.force:
        raise RuntimeError(
            f"{part0_file} already exists. Pass --force to overwrite scene scripts."
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

    logline = parse_section(document, r"Logline")
    setting = parse_section(document, r"Setting[^\n]*")
    characters = parse_characters_in_scene(document) or story.characters
    segments = parse_segments_from_document(document)

    header = (
        f"<!-- Generated by scene_script.py (model: {args.model}) from story scene: "
        f"{story.name!r} (movie.yml story section) -->\n\n"
    )

    written_files: list[Path] = []
    for idx, span, body in segments:
        part_file = Path(f"{base_path}_part{idx}.md")
        content = format_segment_base_prompt(
            scene_name=scene_name,
            logline=logline,
            setting=setting,
            characters=characters,
            span=span,
            segment_body=body,
        )
        part_file.write_text(header + content + "\n", encoding="utf-8")
        written_files.append(part_file)
        print(f"Wrote scene segment script: {part_file}")

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
            "into detailed segment design files written to "
            "out/scripts/<name>_part0.md, etc. Run without --name to "
            "list the available story scenes."
        )
    )
    parser.add_argument(
        "--name",
        default=None,
        help=(
            "Story scene name from the movie.yml `story:` section; segment scripts "
            "are written to out/scripts/<name>_part0.md, etc. (e.g. frisby_visits_mr_ages). "
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
        help="Output base path or directory (default: out/scripts/<name>).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing scene scripts.",
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
