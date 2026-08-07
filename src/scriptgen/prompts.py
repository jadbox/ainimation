"""Prompt builders that turn an abridged story beat into a scene design request."""

from __future__ import annotations

from movie_config import (
    CHARACTERS,
    SceneSpec,
    StorySceneSpec,
    get_movie_info,
    list_character_names,
)
from scriptgen.config import MAX_SCRIPT_CHARS, MAX_SCRIPT_PROMPT_CHARS, SEGMENT_SPANS


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

DIALOGUE CRAFT & LITERARY ELEGANCE (required — dialogue must be simple, thoughtful, and deeply character-driven):
- GROUNDED IN THE STORY BEAT (required): Every line must come directly from the beat's actions, talking points, and emotions — the request, the answer, or the warning happening NOW in this scene. STRICTLY NO invented backstory, past events, deaths, casualties, or implications beyond what the beat states (e.g. NEVER write lines like "The boy was always too stubborn to die quietly" or "I've seen it take three before the frost"). Simple and clear beats poetic invention: a line is good when it plainly moves this scene forward.
- BANNED DIALOGUE TROPES: STRICTLY FORBID generic TV scolding, modern slang, melodrama, or harsh outbursts (e.g. NEVER write lines like "I told you...", "woman!", "calm down!", "hey you").
- FEATURE ANIMATION TONE: Dialogue must carry a theatrical, feature-animation register that matches the tone mandated by the film's style ({movie_info.style}) and the hard direction rules — but never at the cost of inventing story content.
- CHARACTER-SPECIFIC VOCABULARY & SUBTEXT:
{char_voices}
- SUBTEXT OVER EXPOSITION: Lines must convey feeling and stakes through subtext rather than blunt facts, using ONLY what the beat provides (e.g. instead of "Will you help my son or not?", write "His breath rattles like dry leaves, sir... I have no one else to ask.").
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
- MAXIMUM CONCISION (required): Write the most economical version possible — every sentence must earn its place, every detail must be filmable and non-redundant, and no moment may be repeated or padded. Keep each Segment section's body as short as it can be while still obeying all the rules above. HARD CHARACTER LIMIT: each Segment section body MUST stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters — the final saved prompt file (fixed style/camera header + shared sections + segment body) cannot exceed {MAX_SCRIPT_CHARS} characters, and anything over is rejected and regenerated at your expense.
- Be FULLY SELF-CONTAINED: every production detail lives inside a Segment's paragraphs. Tooling extracts each Segment individually (with only the Logline and Setting & Light attached) to prompt a video model, so a Segment must NEVER reference information defined in another Segment or in a section that no longer exists.
- Chain into the three-act arc described above; each Segment must state in its opening paragraph the exact pose/composition it begins on (matching the previous Segment's final frame) so the generated clips can be concatenated seamlessly.

Be specific and cinematic. Every visual choice must be filmable under the direction rules above, and every element must serve the story."""


def build_scene_context(story: StorySceneSpec, scene: SceneSpec) -> str:
    """Render the canonical story-beat context block used in every part prompt."""
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
        "These beats are the COMPLETE story of this scene: invent no events, "
        "history, or implications beyond them."
    )


def build_part0_prompt(story: StorySceneSpec, scene: SceneSpec) -> str:
    """Prompt for segment 0, which also establishes the shared scene sections."""
    span = SEGMENT_SPANS[0]
    return (
        build_scene_context(story, scene)
        + "\n\nExpand this abridged story beat into a production-ready scene design "
        "and output ONLY this structure, in this order:\n"
        "# <evocative scene title>\n"
        "## Logline\n"
        "## Characters in Scene\n"
        "## Setting & Light\n"
        f"## Segment 0 ({span})\n"
        "<segment 0 chronological shooting plan body>\n\n"
        f"Write Segment 0 ONLY. Segments 1 and 2 are generated separately and will "
        f"reference this output, so keep the shared sections self-contained and "
        "maximally concise. Obey every direction rule. HARD LIMIT: the Segment 0 "
        f"body must stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters."
    )


def build_next_part_prompt(
    story: StorySceneSpec,
    scene: SceneSpec,
    part_index: int,
    prev_body: str,
    logline: str,
    setting: str,
    characters: list[str],
) -> str:
    """Prompt for a later segment, chaining the previous segment as a reference."""
    span = SEGMENT_SPANS.get(part_index, "")
    shared = (
        f"Logline: {logline}\n"
        f"Characters in scene: {', '.join(characters)}\n"
        f"Setting & Light: {setting}"
    )
    return (
        build_scene_context(story, scene)
        + "\n\nESTABLISHED SHARED CONTENT (already set for this scene; keep it "
        "consistent, do not restate it):\n"
        + shared
        + "\n\n<REFERENCE> (the previous segment's content you already wrote — "
        "continue seamlessly from its final frame; match pose, composition, "
        "blocking, and lighting):\n"
        f"{prev_body}\n</REFERENCE>\n\n"
        f"Produce ONLY this section, writing segment {part_index}'s chronological "
        f"shooting plan:\n"
        f"## Segment {part_index} ({span})\n<segment body>\n\n"
        "Do NOT restate the title, Logline, Characters, or Setting & Light. "
        "Follow all direction rules and MAXIMUM CONCISION. HARD LIMIT: the "
        f"segment body must stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters."
    )


def build_condense_prompt(previous_doc: str, current_chars: int, target_chars: int) -> str:
    """Prompt to rewrite the previous document shorter while keeping its structure."""
    reduce_by = current_chars - target_chars
    return (
        f"Your previous document is {current_chars} characters; the limit is "
        f"{target_chars} characters. Rewrite it, cutting at least {reduce_by} "
        "characters while keeping the same section structure and story beats. "
        f"Return ONLY the rewritten document.\n\n{previous_doc}"
    )