"""Prompt builders that turn an abridged story beat into a scene design request.

Incorporates official MiniMax H3 Video Prompt Writing Guidelines:
- base-en.txt:
    * §2.2 Part Two Contains the Three Core Fields
    * §3.1-§3.2 Keyframe Development Paths (I2VA / FL2VA continuous motion path)
    * §4.1 Multimodal Description Timeline & [Shot 1] Opening Style/Framing
    * §4.2 Shots, Cuts & Continuous Camera Takes
    * §4.3 Camera Motion 3-Dimension Formula (Motion Type + Amplitude + Speed)
    * §4.4 Speakers, Audio Sources & Dialogue Formatting (<d>[Language] ...</d>, lip closure)
    * §4.5 On-Screen Text Formatting
    * §4.6 overall_soundscape (1-4 sentences ambient/physical/non-verbal audio)
    * §4.7 non_diegetic_music (1-3 sentences instrumentation/tempo/dynamics score)
- ref-en.txt:
    * §2 Reference Labels & Subject Definitions (<Subject N>, <Picture N>)
    * §5.4 Speakers, Audio Sources & Observable Physical/Facial Delivery
    * §6 Audio Layer Separation (Diegetic vs Soundscape vs Non-Diegetic Music)
"""

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
    """System instruction for the per-part shooting-plan generation calls.

    Embeds MiniMax H3 Video Prompt Writing techniques (base-en.txt & ref-en.txt)
    and enforces dense, theatrical scripting within the <1700 character budget.
    """
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

ATTENTION ENGINEERING & DYNAMIC ANIMATION (required — every frame must feel alive and gripping):
- HOOK (base-en.txt §4.1): open on action already in progress or visually arresting motion — never an empty room or a standing-still character. The first second is the scroll-stopper.
- THEATRICAL ACTING & CONTINUOUS VITALITY (ref-en.txt §5.4): characters must NEVER freeze, stand limp, or move like stiff plastic toys with static features. Characters act out their roles like master theatre actors giving a full stage performance. In EVERY beat, explicitly describe what EVERY visible character is doing physically AND what their face is expressing (eyes wide/narrowed, eyebrows furrowed/raised, mouth/jaw tense/softened, reactive smiles, breathing). Never leave any character blank or static.
- DYNAMIC STAGING & SILHOUETTES: stage characters with expressive silhouettes, contrasting heights, and tactile physical interaction (holding a hand, supporting a back, soothing, gripping a prop).
- ONE FOCAL POINT PER BEAT: direct the viewer's eye to the primary physical action, eyeline, or story object.
- ESCALATION ACROSS PARTS: each part must raise stakes, intimacy, or intensity beyond the previous one.
- THE UNFORGETTABLE IMAGE: land a held beat (1-2 seconds of still camera) around the scene's iconic moment.

LITERAL DIRECTION LANGUAGE (required — base-en.txt §4.1, ref-en.txt §5.4):
- Write only observable physical facts: who is where, what moves, where the camera is and where it goes.
- Express emotion ONLY through visible, specific physical and facial actions: trembling fingers, furrowed brows, flared nostrils, sharp inhalation, warm smiles, nodding. Never write bare emotion labels ("she feels sad").
- Never write invented numbers — no degrees, kelvin, inches, or percentages.
- ONE CONTINUOUS CAMERA MOTION PER SEGMENT (base-en.txt §3.2, §4.2): strictly ONE unbroken sequence shot. Strictly NO cuts, NO jump cuts, NO angle switches, and NO sudden zoom or focal length jumps. Declare a single continuous smooth camera motion (e.g. slow push in, static hold, slow tracking shot) across the 10 seconds.

CAMERA MOTION VOCABULARY (required — base-en.txt §4.3: Motion Type + Amplitude + Speed):
- Motion types: Zoom In / Zoom Out, Push In / Pull Out, Pan Left / Pan Right, Truck Left / Truck Right, Tilt Up / Tilt Down, Pedestal Up / Pedestal Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly / Shake Strongly, POV, Roll Clockwise / Roll Counterclockwise.
- Amplitude: "with small amplitude", "with large amplitude" (medium omitted).
- Speed: "at slow speed", "at fast speed" (normal omitted).
- STRICTLY NO CUTS OR ZOOM JUMPS: declare camera motion at the opening of [Shot 1] (e.g. "The camera pushes in with small amplitude at slow speed toward..."). Do NOT write separate, conflicting camera moves for sub-beats.

SPEAKERS & DIALOGUE ENCODING (required — base-en.txt §4.4, ref-en.txt §5.4):
- Assign stable speaker IDs in order of appearance: (S1), (S2).
- Place identifying phrase, ID, physical action, and delivery OUTSIDE dialogue tags: `{sample_speaker1}, a soft, breathless speaker (S1), leans forward with trembling hands and says: <d>[English] We must act now.</d>`
- Inside <d> put ONLY `<d>[Language] verbatim line</d>`. Non-speakers and finished speakers keep lips closed (e.g. `She closes her lips and...`).
- For voiceover: `says in an off-screen voiceover: <d>[English] ...</d> while lips remain completely closed.`

SOUND ARCHITECTURE (required — base-en.txt §4.6-§4.7, ref-en.txt §6):
- Synchronized diegetic sounds belong inline within the multimodal description beats.
- overall_soundscape (1-4 sentences): ambient sound, physical action sounds, and non-verbal human sounds (wind, rain, paper rustle, breathing). Do NOT repeat dialogue or music here.
- non_diegetic_music (1-3 sentences): audience-only score describing instrumentation, tempo, rhythm, and dynamics ONLY (no abstract mood words). Use N/A if no score.

SPATIAL & PHYSICAL LAWS (required — base-en.txt §4.1, ref-en.txt §2.1):
- First sentence of [Shot 1]: state style token, then a semicolon-separated list placing every character, key prop, and light source relative to camera.
- One continuous unbroken sequence shot — strictly NO cuts, jump cuts, or sudden zoom changes.
- In EVERY beat, specify the physical actions AND changing facial expressions of ALL visible characters.
- Characters look at each other or at scene objects — NEVER into the lens. Only the declared speaker moves their mouth.

DIALOGUE CRAFT (Instagram pacing):
- Max 8-10 words per line; one idea per line. Final line is the shortest punch.
- Pair every spoken line with a visible physical act. The listener reacts with facial/body language.

TIME-CODED BEATS (required): open each chronological paragraph with a bracketed timecode, e.g. `[0:00-0:03]`. The timecodes must tile the full 10 seconds with no gaps. In EVERY beat, describe what EVERY character on screen is doing physically AND what their face is expressing.

OUTPUT FORMAT (for the specific single Segment requested in the prompt) — return Markdown with EXACTLY these headers:
# <evocative scene title>
## Logline
(one short sentence under 60 chars: protagonist, action, dramatic question)
## Characters in Scene
(one bullet per character in scene order: "- NAME <VOICE>voice description</VOICE>". First-listed speaker = (S1), second = (S2).)
## Setting & Light
(one short sentence under 80 chars: environment, key prop, dominant practical light source)
## Segment <index> (<span: e.g. 0:00-0:10>)

SEGMENT RULES (base-en.txt §2.2):
Each Segment section is written as the three labeled core fields:

integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping sentence>. <timecoded beat paragraphs...>

overall_soundscape: <1-4 sentences>

non_diegetic_music: <1-3 sentences, or N/A>

Each Segment section must also:
- Write ONLY the single Segment requested in the prompt.
- Open [Shot 1] with style token, spatial mapping, and continuous camera motion.
- Be FULLY SELF-CONTAINED.
- MAXIMUM CONCISION: every sentence must be lean, dense, and punchy. HARD LIMIT: each Segment body MUST stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters so the total saved prompt stays strictly under 1,350 characters (leaving safety margin under the 1,700 character ceiling).
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

The scene is divided into {part_count} x 10-second segments. Plan ALL of them as one escalating arc. Every segment must feature active theatrical character acting with expressive facial shifts and continuous unbroken camera motion.

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
    """Prompt for segment 0, establishing shared scene sections and MiniMax core fields.

    References:
    - base-en.txt §2.2 (Three core fields), §3.1 (I2VA development), §4.1 (Opening framing)
    - ref-en.txt §5.4 (Theatrical acting & speaker encoding)
    """
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
        "maximally concise. Obey every direction rule. In every timecoded beat, "
        "spell out what EVERY character on screen is doing physically AND what their "
        "face is expressing (theatrical acting; no plastic/static features). Keep camera "
        "motion continuous and unbroken with strictly NO cuts or sudden zoom jumps. "
        f"HARD LIMIT: the Segment 0 body must stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters "
        "so the total prompt remains under 1,350 characters."
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
    """Prompt for a later segment, chaining the previous segment and treatment.

    References:
    - base-en.txt §3.2 (FL2VA single-shot continuity path between keyframes)
    - ref-en.txt §5.4 & §6 (Observable character acting and audio separation)
    """
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
        "Follow all direction rules and MAXIMUM CONCISION. In every timecoded beat, "
        "spell out what EVERY character on screen is doing physically AND what their "
        "face is expressing (theatrical acting; no plastic/static features). Keep camera "
        "motion continuous and unbroken with strictly NO cuts or sudden zoom jumps. "
        f"HARD LIMIT: the segment body must stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters "
        "so the total prompt remains under 1,350 characters."
    )


def build_critique_prompt(treatment: str, document: str) -> str:
    """Prompt for the quality-critique pass over one generated part.

    Evaluates compliance with MiniMax H3 rules (base-en.txt & ref-en.txt).
    """
    return (
        "You are a brutally honest short-form video director reviewing a scene "
        "segment written for a LITERAL video-generation model. Score each axis "
        "1-10 and give ONE concrete fix per axis scoring below 8. Do NOT rewrite "
        "the segment.\n\n"
        "AXES:\n"
        "- HOOK (does the first second stop a scrolling thumb? base-en.txt §4.1)\n"
        "- ESCALATION (is this segment more than the last, per the treatment ladder?)\n"
        "- ATTENTION CONTROL (is there one clear focal point per beat?)\n"
        "- DYNAMISM & THEATRICAL ACTING (are all characters on screen continuously alive with expressive physical acting and changing facial expressions in EVERY beat, acting like great theatre actors with zero plastic/stiff doll-like stillness? ref-en.txt §5.4)\n"
        "- CAMERA CONTINUITY & NO CUTS (is it strictly one continuous unbroken shot with zero cuts, zero jump cuts, and zero sudden zoom jumps across beats? base-en.txt §3.2, §4.2-§4.3)\n"
        "- DIALOGUE ECONOMY (every line <=10 words, one job each, no deletable lines? base-en.txt §4.4)\n"
        "- LITERALNESS (only physical facts; no emotion labels, no invented numbers? ref-en.txt §5.4)\n"
        "- FILMABILITY (one camera move, continuous locomotion, no teleporting? base-en.txt §4.3)\n"
        "- LENGTH (body at or under the stated character limit so total is under 1,350 characters?)\n\n"
        f"DIRECTOR'S TREATMENT:\n{treatment}\n\n"
        f"SEGMENT UNDER REVIEW:\n{document}\n\n"
        "Return ONLY:\n"
        "SCORES: hook=N, escalation=N, attention=N, dynamism=N, camera=N, dialogue=N, literalness=N, filmability=N, length=N\n"
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
        f"Your previous rendered script is {current_chars} characters; the hard cap is "
        f"1350 characters (total prompt must stay under 1700 characters). Rewrite the document, cutting at least "
        f"{reduce_by} characters. Keep the Logline (1 sentence <60 chars) and Setting & Light (1 sentence <80 chars) "
        f"extremely compact. Make the multimodal description dense and punchy (target {target_chars} characters for the segment body), "
        "retaining timecoded beats, theatrical character acting, and the three core fields. "
        f"Return ONLY the rewritten document.\n\n{previous_doc}"
    )
