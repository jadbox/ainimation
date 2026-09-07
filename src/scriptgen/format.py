"""Format generated scenes into per-segment base prompts in :mod:`scriptgen`.

Follows the official MiniMax H3 Video Prompt Writing Guides:
- base-en.txt (§2.2 Three Core Fields, §4.1 [Shot 1] Structure, §4.4 Dialogue Formatting)
- ref-en.txt (§2 Reference Labels, §5.4 Speaker IDs & Physical Delivery, §6 Sound Separation)

The saved part file is the video-generation prompt. Total prompt length (static template
+ segment body + animator reference tags) must stay strictly under 1,700 characters.
"""

from __future__ import annotations

from movie_config import get_character, standardize_name


def format_segment_base_prompt(
    scene_name: str = "",
    logline: str = "",
    setting: str = "",
    characters: list[str] | tuple[str, ...] = (),
    span: str = "",
    segment_body: str = "",
) -> str:
    """Build the base prompt document for a single scene segment.

    Follows MiniMax H3 Video Prompt Writing Guidelines:
    - base-en.txt (§2.2 Three Core Fields, §4.1 [Shot 1] Structure, §4.4 Dialogue Formatting)
    - ref-en.txt (§2 Reference Labels, §5.4 Speaker IDs & Physical Delivery, §6 Sound Separation)

    The saved part file is the video-generation prompt. Total prompt length (static template
    + segment body + animator reference tags) must stay strictly under 1,700 characters.
    """
    # ref-en.txt §5.4: Character voice descriptions attached to character roster headers
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

    # base-en.txt §4.1-4.4 & ref-en.txt §5.4: Compact preamble & strict mandates
    return f"""Characters appearing: {char_header_str}.
Match designs EXACTLY to reference images; never use references as opening frames.
MANDATES: One unbroken continuous shot — strictly NO cuts, jump cuts, or zoom jumps. Every character has an active role, emotional intention, and physical presence. Vivid theatrical animation in every frame with dynamic gestures, tactile object interaction, and continuously evolving facial expressions (expressions are never flat or static). Declared speaker moves mouth; non-speakers keep mouths closed.

{segment_body}"""
