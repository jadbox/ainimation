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
    sample_speaker1 = roster_names[0] if roster_names else "CHARACTER ONE"
    return f"""You are a world-class animation director designing {total_seconds}-second short films for vertical-scroll audiences (Instagram/YouTube). You write for a LITERAL video-generation model: it executes exactly what is physically described and cannot interpret poetry, metaphors, or abstract emotion. Your job is to engineer what a viewer with a 2-second attention span sees, moment by moment.

HARD DIRECTION RULES (every choice must obey them):
{rules}
{style_bible}

CHARACTER ROSTER (use only these characters, spelled exactly in ALL CAPS):
{roster}

CHARACTER VOICES:
{char_voices}

SHOW, DON'T TELL & CINEMATIC DIALOGUE RULES (CRITICAL MANDATE):
- ZERO SELF-NARRATION OR LITERAL EXPOSITION: Characters must NEVER speak to themselves out loud to describe what is happening in the environment, declare what sounds they hear, explain their internal feelings, or announce their next action (STRICTLY FORBIDDEN lines like "A rustle!", "Almost there.", "Run!", "Inside!", "I hear something!", "I am scared.").
- SOLITARY / SUSPENSE SCENES: When a character is alone (especially in suspense, danger, or travel), there is NO spoken dialogue. Tension is created purely through visual performance, physical reaction, and diegetic sound effects. Silence and breathing are cinematic; self-talk destroys tension and realism.
- SENSORY EVENTS & THREATS: If something happens in the environment (e.g. a scary rustle in bushes, a twig snap, a shadow shifting, an approaching predator), describe the physical sound event directly in the beat / soundscape, and describe the character's IMMEDIATE, VISCERAL physical/facial reaction (instant freeze mid-stride, ears flattening tightly, pupils dilating in terror, sharp intake of breath, trembling paws, sinking low into cover, head whipping toward the sound).
- MULTI-CHARACTER DIALOGUE: When 2+ characters are present, spoken dialogue is strictly conversational, subtextual, and conflict-driven. Characters speak to each other, never to themselves or the audience. Every line must have subtext, desire, or friction.

10-SECOND SEGMENT FLOW & 3-BEAT STORYBOARDING RHYTHM (required):
Structure each 10-second continuous shot into a dynamic 3-beat dramatic arc:
- [0:00-0:03] Hook & Kinetic Setup: Open in medias res with clear motion vector and depth staging (foreground framing elements, midground subject, background lighting/target). Hook the audience instantly.
- [0:03-0:07] Complication / Sensory Event / Shift: An unexpected visual or sonic event, obstacle, or emotional pivot that challenges the character or creates suspense.
- [0:07-0:10] Kinetic Reaction / Propulsion / Bridge: Character commits to action, reacts physically, and propels toward the closing frame, creating seamless continuity for the next segment.

ATTENTION ENGINEERING & THEATRICAL ACTING (required — base-en.txt §4.1, ref-en.txt §5.4):
- HOOK: open on action already in progress or visually arresting motion — never an empty room or a standing-still character. The first second is the scroll-stopper.
- THEATRICAL ACTING & CONTINUOUS VITALITY: characters must NEVER freeze, stand limp, or move like stiff plastic toys with flat, dull, or static features. Characters act out their roles like master theatre actors giving a full, lively stage performance. In EVERY beat, explicitly describe what EVERY visible character is doing physically AND how their facial expressions are continuously animating and lively (eyes wide/narrowed, eyebrows furrowed/raised, mouth/jaw tense/softened, reactive smiles, breathing; expressions must NEVER be flat, dull, or static). Never leave any character blank or static.
- DEPTH STAGING & SILHOUETTES: stage characters with expressive silhouettes, depth planes (dark soft-focus foreground framing, active midground performance, deep background light/destination), and tactile physical interaction.
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
- Max 8-10 words per line; one idea per line. Final line is the shortest punch.
- Pair every spoken line with a visible physical act. The listener reacts with facial/body language.

SOUND ARCHITECTURE (required — base-en.txt §4.6-§4.7, ref-en.txt §6):
- Synchronized diegetic sounds belong inline within the multimodal description beats.
- overall_soundscape (1-4 sentences): ambient sound, physical action sounds, and non-verbal human sounds (wind, rain, paper rustle, breathing). Do NOT repeat dialogue or music here.
- non_diegetic_music (1-3 sentences): audience-only score describing instrumentation, tempo, rhythm, and dynamics ONLY (no abstract mood words). Use N/A if no score.

SPATIAL & PHYSICAL LAWS (required — base-en.txt §4.1, ref-en.txt §2.1):
- First sentence of [Shot 1]: state style token, then a semicolon-separated list placing every character, key prop, and light source relative to camera.
- One continuous unbroken sequence shot — strictly NO cuts, jump cuts, or sudden zoom changes.
- In EVERY beat, specify the physical actions AND changing facial expressions of ALL visible characters.
- Characters look at each other or at scene objects — NEVER into the lens. Only the declared speaker moves their mouth.

TIME-CODED BEATS (required): open each chronological paragraph with a bracketed timecode, e.g. `[0:00-0:03]`. The timecodes must tile the full 10 seconds with no gaps. In EVERY beat, describe what EVERY character on screen is doing physically AND what their face is expressing.

OUTPUT FORMAT (when generating scene parts) — return each 10-second segment enclosed in <PART0>, <PART1>, <PART2>, ... tags:
<PART0>
integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping sentence>. <timecoded beat paragraphs...>

overall_soundscape: <1-4 sentences>

non_diegetic_music: <1-3 sentences, or N/A>
</PART0>

<PART1>
integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping sentence continuing from Part 0>. <timecoded beat paragraphs...>

overall_soundscape: <1-4 sentences>

non_diegetic_music: <1-3 sentences, or N/A>
</PART1>

SEGMENT RULES (base-en.txt §2.2):
Each <PARTn> section is written as the three labeled core fields:

integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping sentence>. <timecoded beat paragraphs...>

overall_soundscape: <1-4 sentences>

non_diegetic_music: <1-3 sentences, or N/A>

Each <PARTn> section must also:
- Open [Shot 1] with style token, spatial mapping, and continuous camera motion.
- Follow 3-beat rhythm: [0:00-0:03], [0:03-0:07], [0:07-0:10].
- Be FULLY SELF-CONTAINED per segment.
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

The scene is divided into {part_count} x 10-second segments. Plan ALL of them as one escalating arc. Every segment must feature active theatrical character acting with expressive facial shifts, structured 3-beat rhythm ([0:00-0:03] Hook/Setup -> [0:03-0:07] Complication/Sensory Event -> [0:07-0:10] Reaction/Bridge), and continuous unbroken camera motion.

SHOW, DON'T TELL MANDATE: Never plan dialogue for exposition or self-narration. Solo characters do not speak out loud to narrate what they see, hear, or do. Convey tension, threats, and discoveries through diegetic sound and visceral physical reactions.

OUTPUT FORMAT — return Markdown with EXACTLY these headers, nothing else:
## Hook
One sentence: what is on screen in the first two seconds that stops a scrolling thumb. It must already be in motion, in danger, or visually striking — never an establishing shot.
## Dramatic Question
One sentence naming the protagonist, their want, and the question the viewer is waiting to have answered.
## Escalation Ladder
Exactly one bullet per segment (Segment 0 ... Segment {part_count - 1}), each stating what THIS segment raises beyond the previous one — a new stake, a sensory or physical obstacle, a closer camera, a light or sound shift, an emotional turn. The ladder must end at the payoff.
## The Turn
One sentence: the exact moment the emotion pivots and what shifts in camera, light, and sound together.
## Unforgettable Image
One sentence describing the single held frame a viewer would remember, and in which segment it lands.
## Dialogue Spine
Context-aware dialogue plan:
- If this is a SOLO character scene (1 character): write `[SOLO SCENE: NO spoken dialogue / self-narration. 100% visual storytelling, physical acting, and diegetic sound design.]` (at most 1 single whispered gasp if strictly motivated).
- If MULTI-CHARACTER scene (2+ characters): 2-5 essential subtextual lines (numbered list), max 10 words each, with ALL CAPS speaker and job (ASK / CHALLENGE / DEFLECT / WARN / REVEAL). Final line is the shortest punch.
## Final Held Frame
One sentence: the last image the scene lands on.

Keep the ENTIRE treatment at or under 600 characters total. Be decisive — one choice per slot, no alternatives, no hedging."""


def build_treatment_prompt(story: StorySceneSpec, scene: SceneSpec, part_count: int) -> str:
    """User prompt for the Director's Treatment call."""
    is_solo = len(story.characters) <= 1
    scene_type_note = (
        "This is a SOLO CHARACTER scene (no conversation partners). Enforce SHOW, DON'T TELL: "
        "NO self-narration or speaking out loud. Build suspense through diegetic sound cues "
        "and physical character reactions."
        if is_solo
        else "This is a MULTI-CHARACTER scene. Use lean, subtextual dialogue between characters."
    )
    return (
        build_scene_context(story, scene)
        + f"\n\nScene character setup: {scene_type_note}\n\n"
        "Plan this entire scene as one short film. Output ONLY the treatment "
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


def build_all_parts_prompt(
    story: StorySceneSpec,
    scene: SceneSpec,
    part_count: int,
    treatment: str,
    existing_parts: dict[int, str] | None = None,
    start_part: int = 0,
) -> str:
    """Prompt to generate scene parts simultaneously separated by <PART0>, <PART1>, ... tags.

    References:
    - base-en.txt §2.2 (Three core fields), §3.1-§3.2 (I2VA / FL2VA continuous motion path)
    - ref-en.txt §5.4 (Theatrical acting & speaker encoding)
    """
    parts_to_gen = list(range(start_part, part_count))
    tags_example = "\n\n".join(
        f"<PART{i}>\n"
        f"integrated_multimodal_description: [Shot 1] 2D-animated, storybook style; ... [{segment_span(i)}] ...\n\n"
        "overall_soundscape: ...\n\n"
        "non_diegetic_music: ...\n"
        f"</PART{i}>"
        for i in parts_to_gen
    )

    ref_block = ""
    if existing_parts and start_part > 0:
        prev_items = []
        for idx in range(start_part):
            if idx in existing_parts:
                prev_items.append(f"<EXISTING_PART{idx}>\n{existing_parts[idx]}\n</EXISTING_PART{idx}>")
        if prev_items:
            ref_block = (
                "\n\nALREADY GENERATED PARTS (Reference — maintain exact continuity from the final frame of Part "
                f"{start_part - 1}):\n" + "\n\n".join(prev_items) + "\n"
            )

    parts_desc = (
        f"parts {start_part} through {part_count - 1}"
        if start_part > 0
        else f"all {part_count} parts (Part 0 to Part {part_count - 1})"
    )

    return (
        build_scene_context(story, scene)
        + "\n\nDIRECTOR'S TREATMENT (the whole-scene plan you must execute across all parts):\n"
        f"{treatment}"
        f"{ref_block}\n\n"
        f"Generate {parts_desc} simultaneously. Separate EACH part into its own explicit <PART0>, <PART1>, <PART2>, ... section.\n\n"
        "OUTPUT FORMAT (generate each requested part tag and its 3 core fields):\n"
        f"{tags_example}\n\n"
        "DIRECTION & CONTINUITY MANDATES (Strictly enforce for every part):\n"
        "- CONTINUITY: Each subsequent part continues seamlessly from the closing frame, character poses, positions, and lighting of the previous part.\n"
        "- SHOW, DON'T TELL: Strictly NO self-narration or literal exposition ('A rustle!'). Convey suspense through diegetic sound cues and immediate physical reactions.\n"
        "- 3-BEAT RHYTHM: In every 10-second part, structure into [0:00-0:03] Setup/Hook -> [0:03-0:07] Complication/Sensory Event -> [0:07-0:10] Reaction/Bridge.\n"
        "- THEATRICAL ACTING: In every timecoded beat, explicitly describe what EVERY character on screen is doing physically AND how their facial expressions are continuously animating (lively animation in every frame; expressions are never flat, dull, or static).\n"
        "- CAMERA CONTINUITY: strictly ONE unbroken sequence shot per part with zero cuts, zero jump cuts, and zero zoom jumps.\n"
        f"- HARD LIMIT: each part body must stay strictly at or under {MAX_SCRIPT_PROMPT_CHARS} characters."
    )


def build_part0_prompt(
    story: StorySceneSpec,
    scene: SceneSpec,
    part_count: int,
    treatment: str,
) -> str:
    """Prompt for segment 0 (compatibility wrapper around build_all_parts_prompt)."""
    return build_all_parts_prompt(story, scene, 1, treatment, start_part=0)


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
    """Prompt for a later segment (compatibility wrapper around build_all_parts_prompt)."""
    return build_all_parts_prompt(
        story,
        scene,
        part_index + 1,
        treatment,
        existing_parts={part_index - 1: prev_body},
        start_part=part_index,
    )


def build_critique_prompt(treatment: str, document: str, part_count: int = 1) -> str:
    """Prompt for the quality-critique pass over all generated scene parts together.

    Evaluates compliance with MiniMax H3 rules (base-en.txt & ref-en.txt) and whole-scene flow.
    """
    return (
        "You are a brutally honest short-form animation director reviewing a multi-part scene "
        "written for a LITERAL video-generation model. Review ALL scene parts (<PART0>, <PART1>, ...) "
        "together for holistic flow and individual execution. Score each axis 1-10 and give concrete fixes "
        "per axis scoring below 8. Do NOT rewrite the document.\n\n"
        "AXES:\n"
        "- HOOK (does Part 0 open in medias res with scroll-stopping motion/staging? base-en.txt §4.1)\n"
        "- ESCALATION (does each subsequent part raise stakes, tension, or intimacy per the treatment ladder?)\n"
        "- CONTINUITY (does each part continue seamlessly from the exact closing frame, blocking, and pose of the previous part?)\n"
        "- SHOW_DONT_TELL (is dialogue completely free of self-narration, environmental description like 'A rustle!', or talking out loud when alone? Are sensory events delivered via diegetic sound and physical reactions? ref-en.txt §5.4)\n"
        "- PACING_RHYTHM (does each 10-second segment follow a dynamic 3-beat rhythm: Setup -> Complication/Sensory Event -> Reaction/Bridge?)\n"
        "- DYNAMISM_ACTING (are all visible characters continuously alive with lively physical animation and constantly animating facial expressions in EVERY beat, never flat or dull? ref-en.txt §5.4)\n"
        "- ATMOSPHERE_AUDIO (are diegetic sound cues and soundscape used effectively to build tension and tactile texture rather than relying on speech? base-en.txt §4.6, ref-en.txt §6)\n"
        "- CAMERA_CONTINUITY (is each part strictly one continuous unbroken shot with zero cuts, zero jump cuts, and zero zoom jumps across beats? base-en.txt §3.2, §4.2-§4.3)\n"
        "- LITERALNESS (only observable physical facts; no bare emotion labels, no invented numbers? ref-en.txt §5.4)\n"
        f"- LENGTH (each part body at or under {MAX_SCRIPT_PROMPT_CHARS} chars so total prompt is under 1,350 characters?)\n\n"
        f"DIRECTOR'S TREATMENT:\n{treatment}\n\n"
        f"PARTS UNDER REVIEW:\n{document}\n\n"
        "Return ONLY:\n"
        "SCORES: hook=N, escalation=N, continuity=N, show_dont_tell=N, pacing_rhythm=N, dynamism_acting=N, atmosphere_audio=N, camera_continuity=N, literalness=N, length=N\n"
        "FIXES: numbered list of concrete fixes specifying which part (<PART0>, <PART1>, etc.) each fix applies to."
    )


def build_polish_prompt(document: str, fixes: str) -> str:
    """Prompt to apply critique fixes across all parts while preserving <PARTn> tags and limits."""
    return (
        "Apply the following fixes across the scene parts. Keep all <PART0>, <PART1>, ... section tags, "
        "the three core fields per part (integrated_multimodal_description, overall_soundscape, non_diegetic_music), "
        "spatial mapping first sentences, 3-beat timecoded rhythm, Show Don't Tell mandates, "
        "and the HARD character limit per part. Return ONLY the rewritten document containing all parts.\n\n"
        f"FIXES:\n{fixes}\n\n"
        f"DOCUMENT:\n{document}"
    )


def build_condense_prompt(
    previous_doc: str,
    current_chars: int,
    target_chars: int,
    part_index: int = 0,
    span: str = "",
) -> str:
    """Prompt to rewrite a single part body shorter while keeping its structure."""
    doc_len = len(previous_doc.strip())
    return (
        f"CRITICAL: Part {part_index} ({doc_len} characters) exceeds the budget. "
        f"Rewrite it concisely so the segment body is strictly under {target_chars} characters total.\n\n"
        "CONDENSATION RULES:\n"
        f"1. Output ONLY the condensed segment body for Part {part_index} ({span or segment_span(part_index)}). "
        "Do NOT include title, logline, characters, setting, or <PARTn> tags.\n"
        "2. Keep the three core fields: integrated_multimodal_description, overall_soundscape, non_diegetic_music.\n"
        "3. In integrated_multimodal_description: Keep the [Shot 1] spatial mapping first sentence. "
        "Tighten each timecoded beat ([0:00-0:03], [0:03-0:07], [0:07-0:10]) to exactly ONE lean, dense sentence "
        "focusing strictly on key physical actions, facial expressions, and diegetic sound cues.\n"
        "4. In overall_soundscape: Exactly ONE concise sentence.\n"
        "5. In non_diegetic_music: Exactly ONE concise sentence (or N/A).\n"
        "6. Obey SHOW, DON'T TELL (strictly zero self-narration).\n"
        "7. Cut all filler words, wordy descriptions, and redundant adjectives.\n\n"
        f"PREVIOUS PART BODY TO CONDENSE:\n{previous_doc}\n\n"
        "Return ONLY the rewritten condensed segment body."
    )


