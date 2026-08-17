"""Prompt builders that turn an abridged story beat into a scene design request."""

from __future__ import annotations

from movie_config import (
    CHARACTERS,
    SceneSpec,
    StorySceneSpec,
    get_movie_info,
    list_character_names,
)
from scriptgen.config import MAX_SCRIPT_PROMPT_CHARS, segment_span


def build_system_instruction(part_count: int) -> str:
    """System instruction for the per-part shooting-plan generation calls."""
    movie_info = get_movie_info()
    roster_names = list_character_names()
    roster = ", ".join(roster_names)
    rules = "\n".join(f"- {rule}" for rule in movie_info.hard_direction_rules)
    style_bible = ""
    if movie_info.style_checklist:
        checklist = "\n".join(
            f"- {item.category}: DO {item.do} — DON'T {item.don_t}"
            for item in movie_info.style_checklist
        )
        style_bible = (
            "\n\nSTYLE BIBLE — do/don't checklist (every scene must obey it):\n"
            f"{checklist}"
        )
    char_voices = "\n".join(
        f"  * {spec.display_name()}: {spec.identity}; {spec.appearance}."
        + (f" <VOICE>{spec.voice}</VOICE>" if spec.voice else "")
        for spec in CHARACTERS.values()
    )
    total_seconds = part_count * 10
    segment_headers = "\n".join(
        f"## Segment {index} ({segment_span(index)})" for index in range(part_count)
    )
    sample_speaker1 = roster_names[0] if roster_names else "CHARACTER ONE"
    sample_speaker2 = roster_names[1] if len(roster_names) > 1 else "CHARACTER TWO"
    return f"""You are a world-class animation director designing {total_seconds}-second short films for vertical-scroll audiences (Instagram/YouTube). You write for a LITERAL video-generation model: it executes exactly what is physically described and cannot interpret poetry, metaphors, or abstract emotion. Your job is to engineer what a viewer with a 2-second attention span sees, moment by moment.

HARD DIRECTION RULES (every choice must obey them):
{rules}
{style_bible}

CHARACTER ROSTER (use only these characters, spelled exactly in ALL CAPS):
{roster}

CHARACTER VOICES:
{char_voices}

ATTENTION ENGINEERING (required — every frame exists to hold the viewer):
- HOOK: a segment must open on something already in motion, in danger, or visually striking — NEVER on an empty room, an establishing wide, or a character standing still. The first described second is the scroll-stopper.
- ONE FOCAL POINT PER BEAT: state where the viewer's eye must go and why — the brightest point in frame, the only thing moving, a character's eyeline pointing at it, or the story object. Never let two things compete for attention.
- ESCALATION ACROSS PARTS: each part must be MORE than the previous one — closer camera, higher stakes, a shift in light or sound. The treatment's ladder is law.
- PLANT AND PAY OFF: plant a micro-question early (a glance, an unseen sound, an unopened object) and pay it off within the scene.
- THE TURN: when the emotion pivots, camera distance, light, sound, and music must all shift together in the same beat.
- THE UNFORGETTABLE IMAGE: build a held beat (1-2 seconds of still camera) around the single frame a viewer would remember, exactly where the treatment places it.

LITERAL DIRECTION LANGUAGE (required):
- Write only observable physical facts: who is where, what moves, where the camera is and where it goes. The video model animates exactly this and nothing it must infer.
- Express emotion ONLY through visible body action: trembling fingers, ears flattening, a paw freezing mid-gesture, chest heaving. Never write a bare emotion label ("she feels sad", "naked reverence").
- Never write invented numbers — no degrees, kelvin, inches, or percentages; the model ignores them.
- One camera move per segment (a hold counts). Stillness is a deliberate choice; use it for the held beats.

CAMERA MOTION VOCABULARY (required — the video model understands ONLY these motion types, each optionally qualified with an amplitude and/or speed):
- Motion types: Zoom In / Zoom Out (focal length changes, camera body still), Push In / Pull Out (camera moves forward/backward), Pan Left / Pan Right (camera pivots horizontally in place), Truck Left / Truck Right (camera translates horizontally), Tilt Up / Tilt Down (camera pivots vertically in place), Pedestal Up / Pedestal Down (whole camera rises/lowers), Arc Shot (camera arcs around the subject), Tracking Shot (camera follows a moving subject), Static Shot (camera completely still), Shake Slightly / Shake Strongly, POV, Roll Clockwise / Roll Counterclockwise.
- Amplitude (only when meaningful, medium is omitted): "with small amplitude", "with large amplitude".
- Speed (only when meaningful, normal is omitted): "at slow speed", "at fast speed".
- Write camera motion as a natural English action inside the beat, never as stacked labels: "The camera pushes in with small amplitude at slow speed toward the folded letter in her hands." / "The camera holds a static shot as she exits the frame."

SPEAKERS & DIALOGUE ENCODING (required — the video model's exact dialogue format):
- Assign each speaking character a stable speaker ID in the order of the Characters in Scene list: (S1), (S2). A character keeps the same ID for the entire scene; characters who never speak get no ID.
- When a speaker first appears, establish their identity from visual and audio context (character type, age, pitch, timbre, speaking rate, accent — from the character's <VOICE> description).
- Place the speaker's identifying phrase, ID, physical action, and delivery OUTSIDE the dialogue tags. Inside <d> put ONLY the language tag and the spoken words verbatim: `{sample_speaker1}, a soft, breathless field mouse (S1), wrings her cape and says: <d>[English] His breath rattles like dry leaves.</d>`
- Preserve every word and punctuation mark of each line verbatim; never translate or rewrite.

SOUND ARCHITECTURE (required — the video model expects sound split across fields):
- Synchronized diegetic sounds that belong to a specific visible action (a claw scratching parchment, a page turning, a gasp) stay inline in that beat of the multimodal description.
- overall_soundscape (1-4 sentences): summarize the scene's ambient sound, physical action sounds, and non-verbal human sounds across the whole segment — wind, rain, fire crackle, footsteps, fabric, breathing. Do NOT repeat dialogue or music here.
- non_diegetic_music (1-3 sentences): the score only the audience hears. Describe instrumentation, tempo, rhythm, and dynamics ONLY — no abstract mood words, no emotional explanations ("sparse music-box notes at a slow tempo, joined by a low cello that swells before fading"). Use N/A if there is no score.
- Diegetic music the characters hear (a music box playing IN the scene) belongs in the multimodal description, not in non_diegetic_music.

SPATIAL & PHYSICAL LAWS (required):
- First sentence of every segment: a semicolon-separated list placing every character, key prop, and light source relative to the camera (left, right, center, foreground, background).
- One continuous unbroken shot per segment — no cuts, no angle jumps.
- Every position or facing change is continuous physical locomotion (step, walk, turn, pivot, climb). No teleporting, no position pops, no duplicate characters.
- Characters never stand on furniture unless the beat calls for climbing; feet stay on the floor.
- Interacting characters share one depth plane so both faces read in 3/4 or profile.
- Every character is alive every second: breathing, weight shifts, ear/whisker twitches, hands working a task. Nobody stands rigid.
- Characters look at each other or at scene objects — never into the lens. Only the declared speaker moves their mouth.

DIALOGUE CRAFT — the Instagram dialogue guide (required — dialogue is the engine of short-form video; every word must fight for its life):
- VOLUME: across the whole scene, roughly 50-70 spoken words total split into 5-8 short lines. Enough to feel snappy, few enough that every line gets a physical performance.
- LINE LENGTH: max 8-10 words per line; one idea per line. The scene's FINAL line is the shortest and hardest-hitting — it is the punch.
- THE DELETION TEST: if removing a line would not change the scene, the line does not exist. Ban greetings, filler, small talk, and any line that merely describes what the picture already shows.
- ONE JOB PER LINE: every line either ASKs, ANSWERs, DEFLECTs, WARNs, or REVEALs. Every exchange must shift the power or emotional balance between the characters.
- GROUNDED IN THE STORY BEAT: lines come only from the beat's actions, emotions, and talking points — never invent backstory, past events, or implications the beat does not state.
- SPEAK IN ACTION: pair every spoken line with a visible physical act (wringing a cape, freezing mid-gesture, turning away). While one character speaks, the other reacts physically — the listener's body is half the scene.
- SUBTEXT OVER EXPOSITION: convey feeling through what a character almost says, not through stating facts. No TV scolding tropes ("I told you...", "calm down"), no melodrama, no modern slang.
- ATTRIBUTE dialogue using the SPEAKERS & DIALOGUE ENCODING format above (identifying phrase + (S-ID) + physical action + `says: <d>[English] line</d>`).

TIME-CODED BEATS (required): open each chronological paragraph with a bracketed timecode, e.g. `[0:00-0:03]`. The timecodes must tile the full 10 seconds with no gaps or overlaps. Every distinct change of action, position, or expression gets its own beat.

OUTPUT FORMAT — return Markdown with EXACTLY these headers, in this order:
# <evocative scene title>
## Logline
(one or two sentences: protagonist, want, dramatic question)
## Characters in Scene
(one bullet per character in scene order: "- NAME <VOICE>voice description</VOICE>". Scene order fixes the speaker IDs: first-listed speaker = (S1), second = (S2).)
## Setting & Light
(the shared stage kept tight: environment, the ONE story object if any, the single dominant practical light source, depth planes — everything constant across parts)
{segment_headers}

SEGMENT RULES — each Segment section is a self-contained shooting plan written as the three labeled core fields the video model expects, EXACTLY in this form:

integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping sentence>. <timecoded beat paragraphs...>

overall_soundscape: <1-4 sentences>

non_diegetic_music: <1-3 sentences, or N/A>

Each Segment section must also:
- Use the exact headers shown above so tooling can parse the 10-second boundaries.
- Open [Shot 1] with the style token, then the spatial mapping sentence, then timecoded beat paragraphs separated ONLY by double line breaks (no ### headers or bullets inside segments).
- State the opening pose/composition that matches the previous Segment's final frame so clips concatenate seamlessly.
- Be FULLY SELF-CONTAINED: everything the video model needs lives inside this Segment. Never reference another Segment or a section that will not travel with it.
- MAXIMUM CONCISION: every sentence must earn its place; no padding, no repeats. HARD LIMIT: each Segment body MUST stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters.
"""


def build_treatment_system_instruction(part_count: int) -> str:
    """System instruction for the whole-scene Director's Treatment call."""
    movie_info = get_movie_info()
    roster = ", ".join(list_character_names())
    total_seconds = part_count * 10
    rules = "\n".join(f"- {rule}" for rule in movie_info.hard_direction_rules)
    return f"""You are a world-class short-form animation director planning a {total_seconds}-second scene as a single, complete short film for Instagram/YouTube viewers with 2-second attention spans. You are NOT writing video-model prompts yet — you are the director deciding what will make this scene unforgettable as a whole, before any shot is written.

Film style: {movie_info.style}
Hard direction rules (the treatment must respect them):
{rules}

Character roster (spell names exactly, ALL CAPS): {roster}

The scene is divided into {part_count} x 10-second segments. Plan ALL of them as one escalating arc.

OUTPUT FORMAT — return Markdown with EXACTLY these headers, nothing else:
## Hook
One sentence: what is on screen in the first two seconds that stops a scrolling thumb. It must already be in motion, in danger, or visually striking — never an establishing shot.
## Dramatic Question
One sentence naming the protagonist, their want, and the question the viewer is waiting to have answered.
## Escalation Ladder
Exactly one bullet per segment (Segment 0 ... Segment {part_count - 1}), each stating what THIS segment raises beyond the previous one — a new stake, a closer camera, a light or sound shift, an emotional turn. The ladder must end at the payoff.
## The Turn
One sentence: the exact moment the emotion pivots and what shifts in camera, light, and sound together.
## Unforgettable Image
One sentence describing the single held frame a viewer would remember, and in which segment it lands.
## Dialogue Spine
The scene's essential lines as a numbered list, 5-8 lines of at most 10 words each, each with its ALL CAPS speaker and its job (ASK / ANSWER / DEFLECT / WARN / REVEAL). Final line is the shortest and hardest — the punch.
## Final Held Frame
One sentence: the last image the scene lands on.

Keep the ENTIRE treatment at or under 600 characters total. Be decisive — one choice per slot, no alternatives, no hedging."""


def build_treatment_prompt(story: StorySceneSpec, scene: SceneSpec, part_count: int) -> str:
    """User prompt for the Director's Treatment call."""
    return (
        build_scene_context(story, scene)
        + "\n\nPlan this entire scene as one short film. Output ONLY the treatment "
        "structure (Hook, Dramatic Question, Escalation Ladder, The Turn, "
        f"Unforgettable Image, Dialogue Spine, Final Held Frame) for "
        f"{part_count} x 10-second segments."
    )


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


def build_part0_prompt(
    story: StorySceneSpec,
    scene: SceneSpec,
    part_count: int,
    treatment: str,
) -> str:
    """Prompt for segment 0, which also establishes the shared scene sections."""
    span = segment_span(0)
    return (
        build_scene_context(story, scene)
        + "\n\nDIRECTOR'S TREATMENT (the whole-scene plan you must execute — "
        "Segment 0 must land its Hook, and every beat must serve the ladder):\n"
        f"{treatment}\n\n"
        "Expand this abridged story beat into a production-ready scene design "
        "and output ONLY this structure, in this order:\n"
        "# <evocative scene title>\n"
        "## Logline\n"
        "## Characters in Scene\n"
        "## Setting & Light\n"
        f"## Segment 0 ({span})\n"
        "<segment 0 body: the three labeled core fields — "
        "integrated_multimodal_description / overall_soundscape / "
        "non_diegetic_music>\n\n"
        "Write Segment 0 ONLY. Later parts are generated separately and will "
        "reference this output, so keep the shared sections self-contained and "
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
    treatment: str,
) -> str:
    """Prompt for a later segment, chaining the previous segment and treatment."""
    span = segment_span(part_index)
    shared = (
        f"Logline: {logline}\n"
        f"Characters in scene: {', '.join(characters)}\n"
        f"Setting & Light: {setting}"
    )
    return (
        build_scene_context(story, scene)
        + "\n\nDIRECTOR'S TREATMENT (the whole-scene plan you must execute — "
        f"Segment {part_index} must raise its rung on the Escalation Ladder and "
        "serve the Unforgettable Image / Final Held Frame):\n"
        f"{treatment}\n\n"
        "ESTABLISHED SHARED CONTENT (already set for this scene; keep it "
        "consistent, do not restate it):\n"
        + shared
        + "\n\n<REFERENCE> (the previous segment's content you already wrote — "
        "continue seamlessly from its final frame; match pose, composition, "
        "blocking, and lighting):\n"
        f"{prev_body}\n</REFERENCE>\n\n"
        f"Produce ONLY this section, writing segment {part_index}'s shooting "
        "plan as the three labeled core fields:\n"
        f"## Segment {part_index} ({span})\n<segment body>\n\n"
        "Do NOT restate the title, Logline, Characters, or Setting & Light. "
        "Follow all direction rules and MAXIMUM CONCISION. HARD LIMIT: the "
        f"segment body must stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters."
    )


def build_critique_prompt(treatment: str, document: str) -> str:
    """Prompt for the quality-critique pass over one generated part."""
    return (
        "You are a brutally honest short-form video director reviewing a scene "
        "segment written for a LITERAL video-generation model. Score each axis "
        "1-10 and give ONE concrete fix per axis scoring below 8. Do NOT rewrite "
        "the segment.\n\n"
        "AXES:\n"
        "- HOOK (does the first second stop a scrolling thumb?)\n"
        "- ESCALATION (is this segment more than the last, per the treatment ladder?)\n"
        "- ATTENTION CONTROL (is there one clear focal point per beat?)\n"
        "- DIALOGUE ECONOMY (every line <=10 words, one job each, no deletable lines?)\n"
        "- LITERALNESS (only physical facts; no emotion labels, no invented numbers?)\n"
        "- FILMABILITY (one camera move, continuous locomotion, no teleporting?)\n"
        "- LENGTH (body at or under the stated character limit?)\n\n"
        f"DIRECTOR'S TREATMENT:\n{treatment}\n\n"
        f"SEGMENT UNDER REVIEW:\n{document}\n\n"
        "Return ONLY:\n"
        "SCORES: hook=N, escalation=N, attention=N, dialogue=N, literalness=N, filmability=N, length=N\n"
        "FIXES: numbered list, one line per fix."
    )


def build_polish_prompt(document: str, fixes: str) -> str:
    """Prompt to apply critique fixes while preserving structure and limits."""
    return (
        "Apply the following fixes to the scene segment. Keep the exact section "
        "structure, the spatial mapping first sentence, timecoded beats, and the "
        "HARD character limit. Return ONLY the rewritten document.\n\n"
        f"FIXES:\n{fixes}\n\n"
        f"DOCUMENT:\n{document}"
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
