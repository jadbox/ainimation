"""Format generated scenes into per-segment base prompts in :mod:`scriptgen`."""

from __future__ import annotations

from movie_config import get_character, get_movie_info, standardize_name


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
        f"=== SHARED SETTING & LIGHT (constant across scene) ===\n{setting}\n\n"
        if setting
        else ""
    )

    return f"""One unbroken continuous shot — NO cuts, jump cuts, or angle changes; smooth camera motion only. Style: {movie_info.style_summary}

Scene: "{scene_name}" — {logline or 'see script below.'}

Characters appearing: {char_header_str}.
Match designs EXACTLY to reference images; never use references as opening frames.
{movie_info.camera_rules}

MANDATES:
- Feet on floor; no standing on furniture/props unless climbing.
- Midground pieces occlude characters behind them; interacting characters share one depth plane in 3/4 or profile view.
- Characters look at each other/scripted objects — NEVER into lens; keep 3/4 or profile eyelines.
- Only the declared speaker moves mouth/lips; all others keep mouths CLOSED, react with body language.
- Every character stays alive with continuous secondary motion (breathing, weight shifts, twitches); never freeze or stand rigid.
- No teleporting, position pops, fades, or duplicate/ghost characters.
- All location/facing changes use continuous physical locomotion (step, walk, turn, pivot, climb).

{setting_block}=== SCENE SCRIPT{span_note} ===
{segment_body}"""
