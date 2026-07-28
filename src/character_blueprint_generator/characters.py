"""Character specifications for the Rats of NIMH Don Bluth style-guide generator.

Each character is derived from the design specifications in ``readme.md`` and
provides the data needed to build a generation prompt and a review system
instruction tuned to that character.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterSpec:
    """A single character blueprint used by the generator pipeline."""

    name: str
    species: str
    identity: str
    appearance: str
    garment: str
    staging: str
    pose_mood: str
    avoid: str

    def display_name(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Character registry
#
# Sources: readme.md Section 2 "Character Design & Specifications" and the
# "Signature Character Recipes" subsection. Characters without a full recipe in
# the README are described using the general anatomy/clothing rules so the
# generator can still produce a coherent style guide for them.
# ---------------------------------------------------------------------------

MRS_BRISBY = CharacterSpec(
    name="Mrs. Brisby",
    species="field mouse",
    identity=(
        "a widowed field mouse and the story's determined protagonist, seeking a "
        "way to save her sick son Timothy"
    ),
    appearance=(
        "dusty mauve-brown fur with a cream muzzle and chest, blue-violet eyes, "
        "pink ears and nose, oversized salmon-pink ear interiors with subtle inner "
        "rim shading, short cream muzzle, small wet pink nose with a bright "
        "highlight dot, long drooping whiskers, small four-fingered pale hands held "
        "near the chest, anxious upright posture"
    ),
    garment="a tattered red hooded cape with a frayed zigzag hem and a few large heavy folds",
    staging=(
        "mouse eye level inside a cozy cinderblock home burrow: one amber oil "
        "lantern is the sole dominant practical source, with deep teal and indigo "
        "shadows, a continuous cool-gold rim light, floating dust motes, and soft "
        "focus roots and household objects occluding roughly one quarter of the "
        "frame edges"
    ),
    pose_mood="anxious but determined, hands held near the chest, reading as a real animal first and a person second",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, a human "
        "body shape, flat lighting, extra limbs, duplicate garments, text, "
        "watermarks, and logos"
    ),
)

MR_AGES = CharacterSpec(
    name="Mr. Ages",
    species="mouse",
    identity=(
        "an elderly, reclusive mouse physician and herbalist who treats Timothy "
        "and directs Mrs. Frisby to the rats"
    ),
    appearance=(
        "white-gray, spiky tufted fur; a hunched, frail silhouette; oversized "
        "salmon-pink ears; heavy-lidded, glossy blue-gray eyes with two stacked "
        "white highlights; a short cream muzzle; a small wet pink nose; long "
        "drooping whiskers and a gray mustache; small, gnarled four-fingered "
        "pale-gray hands with visible knuckles; round, slightly crooked spectacles"
    ),
    garment="a weathered drab-gray shawl with a frayed zigzag hem and a few large, heavy folds",
    staging=(
        "mouse eye level inside a cluttered apothecary den: one amber oil lantern "
        "is the sole dominant practical source, with deep teal and indigo shadows, "
        "a continuous cool-gold rim light, floating dust motes, and soft focus "
        "roots and jars occluding roughly one quarter of the frame edges"
    ),
    pose_mood="observant, gentle, and capable rather than cute or comic",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, a human "
        "body shape, flat lighting, extra limbs, duplicate spectacles, text, "
        "watermarks, and logos"
    ),
)

NICODEMUS = CharacterSpec(
    name="Nicodemus",
    species="rat",
    identity=(
        "the wise, aged leader of the rats of NIMH and keeper of their history "
        "and plans"
    ),
    appearance=(
        "ghostly pale-gray fur, an enormous flowing white beard and brows, "
        "gnarled bony hands with long claw-nails and visible knuckles, one milky "
        "blind eye and one deep-set glossy eye with stacked white highlights, "
        "heavy lids, sagging cheek fur, drooping whiskers, a hunched monumental "
        "presence"
    ),
    garment="a deep teal robe with purple oval motifs and a frayed zigzag hem, drawn with few large heavy folds",
    staging=(
        "rat eye level inside an ancient alchemical study lit by bioluminescent "
        "teal and emerald glow plus a single amber candle: deep cobalt and indigo "
        "shadows, a continuous cool-gold rim light, floating dust motes, and soft "
        "focus hanging roots and glowing jars occluding roughly one quarter of the "
        "frame edges"
    ),
    pose_mood="reverent, ancient, and sacred, reading as a monumental elder rather than cute or comic",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, a human "
        "body shape, flat lighting, extra limbs, duplicate garments, text, "
        "watermarks, and logos"
    ),
)

TIMOTHY_FRISBY = CharacterSpec(
    name="Timothy Frisby",
    species="field mouse",
    identity=(
        "Mrs. Frisby's young son, whose pneumonia prevents the family from "
        "leaving their home before plowing season"
    ),
    appearance=(
        "small young field mouse with soft dusty mauve-brown fur, a cream muzzle "
        "and chest, oversized salmon-pink ears, large glossy blue-violet eyes with "
        "two stacked white highlights, a short cream muzzle, a small wet pink "
        "nose, drooping whiskers, small pale four-fingered hands, a frail sickly "
        "posture with heavy lids and dimmed eyes"
    ),
    garment="a small tattered blanket-wrap with a frayed zigzag hem, animal body still visible beneath it",
    staging=(
        "mouse eye level inside a warm cinderblock home burrow: one amber oil "
        "lantern is the sole dominant practical source, with deep teal and indigo "
        "shadows, a continuous cool-gold rim light, floating dust motes, and soft "
        "focus roots and bedding occluding roughly one quarter of the frame edges"
    ),
    pose_mood="frail, vulnerable, and tender, reading as a real sickly animal first",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, a human "
        "body shape, flat lighting, extra limbs, duplicate garments, text, "
        "watermarks, and logos"
    ),
)

JUSTIN = CharacterSpec(
    name="Justin",
    species="rat",
    identity=(
        "the capable, compassionate captain of the rats' guard who helps Mrs. "
        "Frisby"
    ),
    appearance=(
        "a lean athletic rat with sleek brown-gray fur, a cream muzzle and chest, "
        "oversized salmon-pink ears, large glossy amber eyes with two stacked "
        "white highlights, a short muzzle, a small wet pink nose, alert upright "
        "posture, small strong four-fingered pale hands"
    ),
    garment="a tattered dark-green hooded cape with a frayed zigzag hem and a few large heavy folds",
    staging=(
        "rat eye level inside a torchlit stone corridor: one amber torch is the "
        "sole dominant practical source, with deep teal and indigo shadows, a "
        "continuous cool-gold rim light, floating dust motes, and soft focus "
        "stone and roots occluding roughly one quarter of the frame edges"
    ),
    pose_mood="alert, capable, and compassionate, reading as a real animal first and a guardian second",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, a human "
        "body shape, flat lighting, extra limbs, duplicate garments, text, "
        "watermarks, and logos"
    ),
)

JENNER = CharacterSpec(
    name="Jenner",
    species="rat",
    identity=(
        "an ambitious rat who opposes Nicodemus's leadership and the plan to "
        "leave the farm"
    ),
    appearance=(
        "a large imposing rat with dark slate-gray fur, a cream muzzle, "
        "oversized salmon-pink ears, narrow glossy amber eyes with two stacked "
        "white highlights, a sharp muzzle, a small wet pink nose, bristling cheek "
        "ruffs and whiskers, small strong four-fingered pale hands with visible "
        "knuckles"
    ),
    garment="a tattered deep-crimson cape with a frayed zigzag hem and a few large heavy folds",
    staging=(
        "rat eye level inside a shadowy stone chamber lit by a single crimson "
        "ember source: deep magenta and indigo shadows, a continuous cool-gold "
        "rim light, floating dust motes, and soft focus stone and roots occluding "
        "roughly one quarter of the frame edges"
    ),
    pose_mood="ambitious, menacing, and calculating, reading as a real animal first and a threat second",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, a human "
        "body shape, flat lighting, extra limbs, duplicate garments, text, "
        "watermarks, and logos"
    ),
)

DRAGON = CharacterSpec(
    name="Dragon",
    species="cat",
    identity="the Fitzgibbons' formidable house cat, whose patrols make the rats' work dangerous",
    appearance=(
        "a massive tabby cat with mottled brown and gray fur, a broad flat face, "
        "glowing green eyes with stacked white highlights, a pink nose, long "
        "whiskers, powerful paws with extended claws, a low slinking predator "
        "silhouette"
    ),
    garment="no garment; the animal body is fully visible with tufted spiky fur breaking the silhouette",
    staging=(
        "rodent eye level in a dark farmyard at night: one cold moonlight shaft "
        "is the sole dominant practical source, with deep indigo and slate-purple "
        "shadows, a continuous icy-cyan rim light, floating dust motes, and soft "
        "focus grass and fence posts occluding roughly one quarter of the frame "
        "edges"
    ),
    pose_mood="predatory, looming, and dangerous, reading as a real animal first and a monster second",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, flat "
        "lighting, extra limbs, duplicate features, text, watermarks, and logos"
    ),
)

THE_GREAT_OWL = CharacterSpec(
    name="The Great Owl",
    species="owl",
    identity=(
        "a feared, ancient owl whose counsel sends Mrs. Frisby to the rats"
    ),
    appearance=(
        "a massive ancient owl with mottled brown and gray feathers, enormous "
        "glowing amber eyes with stacked white highlights, a hooked ivory beak, "
        "feathered ear tufts, taloned feet, a hunched monumental perched "
        "silhouette with sagging cheek feathers"
    ),
    garment="no garment; the animal body is fully visible with tufted spiky feathers breaking the silhouette",
    staging=(
        "rodent eye level inside a hollow tree at night: one cold moonlight shaft "
        "plus faint bioluminescent teal glow are the practical sources, with deep "
        "indigo and slate-purple shadows, a continuous icy-cyan rim light, "
        "floating dust motes, and soft focus bark and roots occluding roughly one "
        "quarter of the frame edges"
    ),
    pose_mood="ancient, feared, and wise, reading as a real animal first and a sage second",
    avoid=(
        "clean vector lines, smooth plastic rendering, modern clothing, flat "
        "lighting, extra limbs, duplicate features, text, watermarks, and logos"
    ),
)


CHARACTERS: dict[str, CharacterSpec] = {
    spec.name.lower(): spec
    for spec in (
        MRS_BRISBY,
        MR_AGES,
        NICODEMUS,
        TIMOTHY_FRISBY,
        JUSTIN,
        JENNER,
        DRAGON,
        THE_GREAT_OWL,
    )
}


def list_character_names() -> list[str]:
    """Return the display names of all available characters in registry order."""
    return [spec.display_name() for spec in (
        MRS_BRISBY,
        MR_AGES,
        NICODEMUS,
        TIMOTHY_FRISBY,
        JUSTIN,
        JENNER,
        DRAGON,
        THE_GREAT_OWL,
    )]


def get_character(name: str) -> CharacterSpec:
    """Look up a character by name (case-insensitive).

    Raises ``ValueError`` listing all available characters when no match exists.
    """
    key = name.strip().lower()
    if key in CHARACTERS:
        return CHARACTERS[key]
    available = ", ".join(list_character_names())
    raise ValueError(
        f"No character named {name!r}. Available characters: {available}."
    )
