"""Format generated scenes into per-segment base prompts in :mod:`scriptgen`.

The saved part file IS the video-generation prompt, so every character of the
fixed template competes with the actual shooting plan for the ~6,000 character
budget (the animator tacks ~1,000 more characters of reference instructions on
top before sending, under a 7,000 absolute ceiling). The template keeps only
the anchors other tools parse ("Characters appearing:", the SHARED SETTING
marker) plus the three labeled core fields the MiniMax prompt guide requires:

    integrated_multimodal_description: [Shot 1] ...
    overall_soundscape: ...
    non_diegetic_music: ...
"""

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
    """Build the base prompt document for a single scene segment.

    ``segment_body`` must already contain the three MiniMax core fields
    (``integrated_multimodal_description:`` / ``overall_soundscape:`` /
    ``non_diegetic_music:``). ``span`` is accepted for interface stability but
    is no longer rendered — the animator controls clip duration.
    """
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

    setting_block = (
        f"=== SHARED SETTING & LIGHT (constant across scene) ===\n{setting}\n\n"
        if setting
        else ""
    )

    return f"""Style: {movie_info.style}
Camera: {movie_info.camera_rules}

Scene: "{scene_name}" — {logline or 'see script below.'}
Characters appearing: {char_header_str}.
Match designs EXACTLY to reference images; never use references as opening frames.

MANDATES: One unbroken continuous shot — no cuts, only smooth camera motion. No teleporting, position pops, fades, or duplicate characters — all position/facing changes are continuous physical locomotion. Only the declared speaker moves mouth/lips; all others keep mouths CLOSED and react with body language. Every character stays alive with continuous secondary motion (breathing, weight shifts, posture shifts, tactile interactions); never freeze, idle, or stand rigid.

{setting_block}{segment_body}"""
