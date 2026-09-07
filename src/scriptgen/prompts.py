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
    and enforces dense, theatrical scripting with vivid action, emotional storytelling,
    and active character roles within the character budget.
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

EMOTIONAL STORYTELLING IN EVERY 10-SECOND PART (CRITICAL MANDATE):
- Each 10-second scene part must tell its own gripping micro-story with genuine emotional stakes, kinetic momentum, and an emotional shift.
- A part is never just arbitrary choreography: it must have a beginning desire/tension, a vivid action or sensory complication, and an emotional landing or pivot that sets up the next part.

DISTINCT ROLES FOR EVERY CHARACTER (NO IDLE OR PASSIVE CHARACTERS):
- When characters are present in a scene, EVERY character has an active, defined dramatic role, an urgent personal objective, and a continuous physical presence in THAT part.
- NO IDLE CHARACTERS: Never leave any character standing limp, frozen, or passively observing. Concurrently describe what ALL visible characters are doing physically AND what their facial expressions and eyes are doing.
- In multi-character interactions, treat the scene like a theatrical stage performance: Character A's action/dialogue triggers an immediate visible physical and facial reaction from Character B (e.g. recoiling, leaning in, eyes widening, jaw tightening, hands reaching). Characters maintain active eyelines looking at each other or at focal story props — NEVER into the camera lens.

WONDERFUL VIVID ACTION & PHYSICAL ACTING:
- Direct animation with golden-age theatrical vitality: dynamic locomotion, deep anticipation crouches, follow-through drag on ears, whiskers, tails, and capes, and weight transfer.
- TACTILE INTERACTION: Characters touch, grasp, manipulate, clutch, climb, scramble, or lean against props and the set. Action is tactile, kinetic, and visually arresting.
- OBSERVABLE PHYSICALIZED EMOTION: Convey feelings purely through concrete physical acting and facial animation (trembling paws, clutching garments, wide glossy eyes with stacked highlights, flared nostrils, sudden recoil, softening brow, clenched fists, rapid chest breathing). Never write bare abstract emotion labels ("she feels sad").

SHOW, DON'T TELL & CINEMATIC DIALOGUE RULES:
- ZERO SELF-NARRATION OR LITERAL EXPOSITION: Characters must NEVER speak to themselves out loud to describe what is happening in the environment, declare what sounds they hear, explain their internal feelings, or announce their next action (STRICTLY FORBIDDEN lines like "A rustle!", "Almost there.", "Run!", "Inside!", "I hear something!", "I am scared.").
- SOLITARY / SUSPENSE SCENES: When a character is alone (especially in suspense, danger, or travel), there is NO spoken dialogue. Tension is created purely through visual performance, physical reaction, and diegetic sound effects. Silence and breathing are cinematic; self-talk destroys tension and realism.
- SENSORY EVENTS & THREATS: If something happens in the environment (e.g. a scary rustle in bushes, a twig snap, a shadow shifting, an approaching predator), describe the physical sound event directly in the beat / soundscape, and describe the character's IMMEDIATE, VISCERAL physical/facial reaction (instant freeze mid-stride, ears flattening tightly, pupils dilating in terror, sharp intake of breath, trembling paws, sinking low into cover, head whipping toward the sound).
- MULTI-CHARACTER DIALOGUE: When 2+ characters are present, spoken dialogue is strictly conversational, subtextual, and conflict-driven. Characters speak to each other, never to themselves or the audience. Every line must have subtext, desire, or friction. Max 8-10 words per line.


10-SECOND SEGMENT FLOW & CHRONOLOGICAL BEATS (required):
Structure each 10-second continuous shot as ONE single narrative paragraph describing the beats in the chronological order they occur:
- Beat 1 (Setup & Hook): Opens in medias res with clear motion vector and depth staging. Hooks the viewer instantly with scroll-stopping motion. (Budget: 1-2 punchy sentences, ~25-35 words).
- Beat 2 (Complication & Action): An unexpected sensory event, emotional friction, obstacle, or vivid kinetic action where characters actively interact with props and each other. (Budget: 1-2 punchy sentences, ~30-40 words).
- Beat 3 (Reaction & Turn): Characters react physically and emotionally, landing on a decisive pose or emotional shift that propels into the closing frame. (Budget: 1-2 punchy sentences, ~25-35 words).
Do NOT include bracketed timestamps (such as [0:00-0:03]). Weave all beats into ONE continuous narrative paragraph in the order they occur.

CAMERA CONTINUITY & VOCABULARY (required — base-en.txt §3.2, §4.2, §4.3):
- Strictly ONE unbroken sequence shot per 10-second part. Strictly NO cuts, NO jump cuts, NO angle switches, and NO sudden zoom or focal length jumps.
- Declare a single continuous smooth camera motion at the opening of [Shot 1] using Motion Type + Amplitude + Speed:
  * Motion types: Zoom In / Zoom Out, Push In / Pull Out, Pan Left / Pan Right, Truck Left / Truck Right, Tilt Up / Tilt Down, Pedestal Up / Pedestal Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly / Shake Strongly, POV.
  * Amplitude: "with small amplitude", "with large amplitude" (medium omitted).
  * Speed: "at slow speed", "at fast speed" (normal omitted).
  * Example: "The camera pushes in with small amplitude at slow speed toward..."

SPEAKERS & DIALOGUE ENCODING (required — base-en.txt §4.4, ref-en.txt §5.4):
- Assign stable speaker IDs in order of appearance: (S1), (S2).
- Place identifying phrase, ID, physical action, and delivery OUTSIDE dialogue tags: `{sample_speaker1}, a soft, breathless speaker (S1), leans forward with trembling hands and says: <d>[English] We must act now.</d>`
- Inside <d> put ONLY `<d>[Language] verbatim line</d>`. Non-speakers and finished speakers keep lips closed (e.g. `She closes her lips and...`).
- For voiceover: `says in an off-screen voiceover: <d>[English] ...</d> while lips remain completely closed.`
- Pair every spoken line with a visible physical act. The listener reacts with physical/facial acting.

SOUND ARCHITECTURE (required — base-en.txt §4.6-§4.7, ref-en.txt §6):
- Synchronized diegetic sounds belong inline within the multimodal description beats.
- overall_soundscape: exactly 1-2 sentences of ambient sound, physical action sounds, and non-verbal human sounds (wind, rain, paper rustle, breathing, gasps). Do NOT repeat dialogue or music here.
- non_diegetic_music: exactly 1 sentence of audience-only score describing instrumentation, tempo, rhythm, and dynamics ONLY (no abstract mood words). Use N/A if no score.

SPATIAL & PHYSICAL LAWS (required — base-en.txt §4.1, ref-en.txt §2.1):
- First sentence of [Shot 1]: state style token, then a semicolon-separated list placing every character, key prop, and light source relative to camera, followed by continuous camera motion.
- In every beat, specify the physical actions AND changing facial expressions of ALL visible characters.

SINGLE CONTINUOUS PARAGRAPH (required): Write integrated_multimodal_description as ONE continuous paragraph in chronological order without timecode brackets or timestamps.

OUTPUT FORMAT (when generating scene parts) — return each 10-second segment enclosed in <PART0>, <PART1>, <PART2>, ... tags:
<PART0>
integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping and camera motion sentence>. <Beat 1 action and dialogue>. <Beat 2 complication and reaction>. <Beat 3 landing pose and transition>.

overall_soundscape: <1-2 sentences>

non_diegetic_music: <1 sentence, or N/A>
</PART0>

<PART1>
integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping and camera motion continuing from Part 0>. <Beat 1 action and dialogue>. <Beat 2 complication and reaction>. <Beat 3 landing pose and transition>.

overall_soundscape: <1-2 sentences>

non_diegetic_music: <1 sentence, or N/A>
</PART1>

SEGMENT RULES (base-en.txt §2.2):
Each <PARTn> section is written as the three labeled core fields:
- integrated_multimodal_description: [Shot 1] 2D-animated, <style token>, <opening spatial mapping and camera motion sentence>. Followed by the three beats in sequential order within ONE continuous paragraph (~100-150 words total).
- overall_soundscape: 1-2 sentences.
- non_diegetic_music: 1 sentence, or N/A.

Each <PARTn> section must also:
- Open [Shot 1] with style token, spatial mapping, and continuous camera motion.
- Progress seamlessly through Beat 1 (Setup/Hook) -> Beat 2 (Complication/Action) -> Beat 3 (Reaction/Bridge) in order without bracketed timestamps.
- Be FULLY SELF-CONTAINED per segment.
- ECONOMY OF LANGUAGE: every sentence must be lean, dense, and punchy. HARD LIMIT: each Segment body MUST stay at or under {MAX_SCRIPT_PROMPT_CHARS} characters.
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

SCENE STORY & LOGLINE AS THE FOUNDATIONAL ARC:
- The scene's story & logline (`Scene story & logline: <name> — <logline>`) defines the primary narrative arc, emotional stakes, and dramatic progression for this scene.
- You MUST read and analyze this scene logline as the foundational story to break down across the {part_count} x 10-second segments in the Escalation Ladder, ensuring the whole arc advances and resolves within this runtime.

The scene is divided into {part_count} x 10-second segments. Plan ALL of them as one escalating arc. Every segment must tell an emotional micro-story, assign clear active roles to every character present, feature active theatrical acting with expressive facial shifts, structured chronological progression (Hook/Setup -> Complication/Action -> Reaction/Bridge), and continuous unbroken camera motion.

SHOW, DON'T TELL MANDATE: Never plan dialogue for exposition or self-narration. Solo characters do not speak out loud to narrate what they see, hear, or do. Convey tension, threats, and discoveries through diegetic sound and visceral physical reactions.

OUTPUT FORMAT — return Markdown with EXACTLY these headers, nothing else:
## Hook
One sentence: what is on screen in the first two seconds that stops a scrolling thumb. It must already be in motion, in danger, or visually striking — never an establishing shot.
## Dramatic Question
One sentence naming the protagonist, their want, and the question the viewer is waiting to have answered.
## Character Roles & Dynamics
One sentence per character in this scene defining their urgent objective, emotional stance, and how they physically interact with each other or the environment.
## Escalation Ladder
Exactly one bullet per segment (Segment 0 ... Segment {part_count - 1}). Each bullet must define:
- Segment N (0:00-0:10): [Micro-Story Arc & Emotional Shift: Beginning emotion -> Complication -> Emotional Landing] | [Character Roles: for each character, their physical action and emotional reaction] | [Vivid Action: key kinetic physical/prop interaction].
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

Keep the ENTIRE treatment at or under 1400 characters total. Be decisive — one choice per slot, no alternatives, no hedging."""


def build_treatment_prompt(story: StorySceneSpec, scene: SceneSpec, part_count: int) -> str:
    """User prompt for the Director's Treatment call."""
    is_solo = len(story.characters) <= 1
    scene_type_note = (
        "This is a SOLO CHARACTER scene (no conversation partners). Enforce SHOW, DON'T TELL: "
        "NO self-narration or speaking out loud. Build suspense through diegetic sound cues "
        "and physical character reactions."
        if is_solo
        else "This is a MULTI-CHARACTER scene. Every character present must have an active dramatic role, "
        "distinct objective, and physical/emotional presence in every part. Use lean, subtextual dialogue."
    )
    return (
        build_scene_context(story, scene)
        + f"\n\nScene character setup: {scene_type_note}\n\n"
        "Plan this entire scene as one short film. Read the Scene story & logline above as the primary "
        f"narrative to tell, and break that overarching story arc cleanly into {part_count} x 10-second parts. "
        "Output ONLY the treatment "
        "structure (Hook, Dramatic Question, Character Roles & Dynamics, Escalation Ladder, The Turn, "
        f"Unforgettable Image, Dialogue Spine, Final Held Frame) for "
        f"{part_count} x 10-second segments."
    )


def build_scene_context(story: StorySceneSpec, scene: SceneSpec) -> str:
    """Render the canonical story-beat context block used in every part prompt."""
    characters = ", ".join(story.characters)
    emotions = "\n".join(f"  - {item}" for item in story.emotions)
    actions = "\n".join(f"  - {item}" for item in story.actions)
    looks = "\n".join(f"  - {item}" for item in story.looks)
    background_lines = []
    for bg in scene.backgrounds:
        line = f"  - ({bg.key}) {bg.description}"
        extras = []
        if bg.lighting:
            extras.append(f"Lighting: {bg.lighting}")
        if bg.mood:
            extras.append(f"Mood: {bg.mood}")
        if extras:
            line += "\n    " + "\n    ".join(extras)
        background_lines.append(line)
    backgrounds = "\n".join(background_lines)
    return (
        f"Scene name (production slug): {story.name}\n"
        f"Story beat: {story.title}\n"
        f"Scene story & logline: {scene.name} — {scene.logline}\n"
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
        f"integrated_multimodal_description: [Shot 1] 2D-animated, storybook style; <spatial layout and camera motion>. <Beat 1 action and dialogue>. <Beat 2 complication and reaction>. <Beat 3 landing pose and transition>.\n\n"
        "overall_soundscape: <1-2 sentences>\n\n"
        "non_diegetic_music: <1 sentence, or N/A>\n"
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
        "- STORY ARC FROM LOGLINE: Execute the dramatic narrative arc established in the scene logline and treatment. Each part must tangibly advance that story toward its resolution, with clear stakes and emotional momentum.\n"
        "- EMOTIONAL STORYTELLING: Each part must tell a compelling micro-story with genuine emotion, kinetic momentum, and an emotional shift.\n"
        "- CHARACTER ROLES: Every character listed in 'Characters in scene' MUST have an active dramatic role and physical presence in EVERY beat. No idle, stiff, or passive characters. Describe both their physical actions and continuous facial acting.\n"
        "- WONDERFUL VIVID ACTION: Dynamic, tactile, kinetic physical actions and prop interactions. Use expressive secondary motion (ears, whiskers, fur, capes) and weight shifts.\n"
        "- CONTINUITY: Each subsequent part continues seamlessly from the closing frame, character poses, positions, and lighting of the previous part.\n"
        "- SHOW, DON'T TELL: Strictly NO self-narration or literal exposition ('A rustle!'). Convey suspense through diegetic sound cues and immediate physical reactions.\n"
        "- CHRONOLOGICAL BEAT PROGRESSION: In every 10-second part, weave Beat 1 (Setup/Hook) -> Beat 2 (Complication/Action) -> Beat 3 (Reaction/Bridge) in chronological order within ONE continuous paragraph without timestamps (~25-40 words per beat).\n"
        "- THEATRICAL ACTING: Explicitly describe what EVERY character on screen is doing physically AND how their facial expressions are continuously animating (lively animation in every frame; expressions are never flat, dull, or static).\n"
        "- CAMERA CONTINUITY: Strictly ONE unbroken sequence shot per part with zero cuts, zero jump cuts, and zero zoom jumps.\n"
        "- LEAN AUDIO: Exactly 1-2 sentences for overall_soundscape and 1 sentence for non_diegetic_music.\n"
        f"- HARD LIMIT: Each part body must stay strictly at or under {MAX_SCRIPT_PROMPT_CHARS} characters."
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


def build_condense_system_instruction() -> str:
    """Lightweight, dedicated system instruction for condensation passes."""
    return (
        "You are an expert film script editor. Your only task is to tighten and trim the provided "
        "animation scene segment prompt so that it fits strictly within the given character budget. "
        "Preserve the three core fields (integrated_multimodal_description, overall_soundscape, "
        "non_diegetic_music), all key story actions, camera movements, and dialogue. "
        "Strip redundant adjectives, consolidate sentences, and enforce concision. "
        "Never add commentary, explanation, or preamble."
    )


def build_condense_prompt(
    previous_doc: str,
    current_chars: int,
    target_chars: int,
    part_index: int = 0,
    span: str = "",
) -> str:
    """Prompt to rewrite a single part body shorter while keeping its structure and vivid acting."""
    doc_len = len(previous_doc.strip())
    return (
        f"CRITICAL: Part {part_index} ({doc_len} characters) exceeds the budget. "
        f"Rewrite it concisely so the segment body is strictly under {target_chars} characters total.\n\n"
        "CONDENSATION RULES:\n"
        f"1. Output ONLY the condensed segment body for Part {part_index} ({span or segment_span(part_index)}). "
        "Do NOT include title, logline, characters, setting, or <PARTn> tags.\n"
        "2. Keep the three core fields: integrated_multimodal_description, overall_soundscape, non_diegetic_music.\n"
        "3. In integrated_multimodal_description: Keep as ONE continuous paragraph in chronological order. "
        "Keep the [Shot 1] spatial mapping and continuous camera motion first sentence (~20-25 words). "
        "Follow with the chronological beats: Setup/Hook (~25-30 words), Complication/Action (~25-35 words), and Reaction/Landing (~20-30 words). "
        "Preserve vivid kinetic action, emotional expressions, and dialogue while trimming excess adjectives and filler words. "
        "Do NOT use timestamps or bracketed timecodes.\n"
        "4. In overall_soundscape: Exactly ONE concise sentence.\n"
        "5. In non_diegetic_music: Exactly ONE concise sentence (or N/A).\n"
        "6. Obey SHOW, DON'T TELL (strictly zero self-narration).\n\n"
        f"PREVIOUS PART BODY TO CONDENSE:\n{previous_doc}\n\n"
        "Return ONLY the rewritten condensed segment body."
    )



