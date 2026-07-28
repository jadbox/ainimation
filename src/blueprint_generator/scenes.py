"""Scene background specifications for the Rats of NIMH Don Bluth blueprint generator.

Each scene is derived from the environment, lighting, and color-script
specifications in ``readme.md`` (Sections 4 and 5) and describes 1-2 background
plates. Every background plate runs through its own generate/review loop in
:mod:`blueprint_generator.generate`, producing a clean, character-free
production background ready for cel compositing.
"""

from __future__ import annotations

from dataclasses import dataclass

from blueprint_generator import slug


@dataclass(frozen=True)
class BackgroundSpec:
    """A single background plate within a scene."""

    key: str
    """Short filesystem-safe identifier, e.g. ``hollow-interior``."""

    description: str
    """What the background plate depicts (environment content only)."""

    lighting: str
    """The single dominant practical light source and the palette around it."""

    mood: str
    """The emotional register the plate must evoke."""


@dataclass(frozen=True)
class SceneSpec:
    """A scene blueprint: 1-2 background plates sharing one location/story beat."""

    name: str
    slug: str
    logline: str
    backgrounds: tuple[BackgroundSpec, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.backgrounds) <= 2:
            raise ValueError(
                f"Scene {self.name!r} must describe 1-2 background plates, "
                f"got {len(self.backgrounds)}."
            )


# ---------------------------------------------------------------------------
# Scene registry
#
# Sources: readme.md Section 4 "Background, Foreground & Environments" and
# Section 5 "Scene Directing & Lighting Manual" (including the Section 5C
# color-script palette mapping).
# ---------------------------------------------------------------------------

GREAT_OWL_HOLLOW = SceneSpec(
    name="The Great Owl's Hollow",
    slug="great-owl-hollow",
    logline=(
        "Mrs. Brisby's terrifying pilgrimage to the ancient owl's hollow tree, "
        "where counsel is given amid bones and moonlight"
    ),
    backgrounds=(
        BackgroundSpec(
            key="hollow-interior",
            description=(
                "the cavernous interior of an ancient hollow oak at night: "
                "gnarled curved bark walls ribbed like a gothic nave, a floor "
                "littered with tiny rodent bones, dried husks, and owl pellets, "
                "cobweb veils hanging from above, deep knotholes receding into "
                "pitch black"
            ),
            lighting=(
                "one cold shaft of moonlight spearing down through a crack in "
                "the trunk as the single dominant practical source, with deep "
                "indigo and slate-purple shadows carrying blood-crimson and "
                "magenta accents (the Immediate Danger palette), faint icy-cyan "
                "edge light on bark ridges"
            ),
            mood="immediate danger and mortality; reverent dread before an ancient predator",
        ),
        BackgroundSpec(
            key="forest-approach",
            description=(
                "the night forest floor approaching the hollow oak: the tree "
                "looms as a towering twisted monolith seen from mouse height, "
                "overgrown thorn bushes and tangled roots framing the view, "
                "giant mushrooms and dew-covered grass blades, drifting ground "
                "mist"
            ),
            lighting=(
                "cold moonlight backlighting the oak's silhouette as the single "
                "dominant practical source, deep indigo and slate-purple shadows "
                "with faint crimson accents, thin fog catching the light in "
                "volumetric layers"
            ),
            mood="vulnerability at small scale; a tiny pilgrim before a looming sacred terror",
        ),
    ),
)

MR_AGES_APOTHECARY = SceneSpec(
    name="Mr. Ages' Apothecary",
    slug="mr-ages-apothecary",
    logline=(
        "the cluttered hermit den where Mr. Ages brews remedies among towering "
        "glass jars and dried herbs"
    ),
    backgrounds=(
        BackgroundSpec(
            key="apothecary-interior",
            description=(
                "a cluttered apothecary den burrowed under roots: giant found "
                "objects repurposed as furniture (a glass canning jar as a "
                "cupboard, a rusted thimble as a pot, a spool as a table), "
                "hanging bundles of dried herbs, shelves of corked bottles, "
                "scattered parchment scraps, arched root ceiling"
            ),
            lighting=(
                "one amber oil lantern on the workbench as the single dominant "
                "practical source, warm gold highlights against deep teal and "
                "indigo shadows in the background jars, soft airbrushed glow "
                "around the flame, floating dust motes"
            ),
            mood="ancient alchemy and intellectual mystery; cozy but reclusive",
        ),
    ),
)

BRISBY_CINDERBLOCK_HOME = SceneSpec(
    name="Brisby Cinderblock Home",
    slug="brisby-cinderblock-home",
    logline=(
        "the warm, cramped cinderblock burrow where the Frisby family shelters "
        "from the coming plow"
    ),
    backgrounds=(
        BackgroundSpec(
            key="burrow-interior",
            description=(
                "a cozy cinderblock home interior at mouse scale: rough concrete "
                "block walls with arched nooks, a scrap of red fabric as a "
                "curtain, a spool bed with patchwork bedding, a bottle-cap "
                "table, stored seeds and a cracked teacup, roots poking through "
                "the ceiling"
            ),
            lighting=(
                "one amber oil lantern as the single dominant practical source, "
                "rich ochres, terracotta, and candlelight golds against deep "
                "umber and teal shadows (the Sanctuary palette), gentle bloom "
                "around the flame, floating dust motes"
            ),
            mood="sanctuary and safety; a small pocket of warmth inside overwhelming darkness",
        ),
    ),
)


SCENES: dict[str, SceneSpec] = {
    spec.slug: spec
    for spec in (
        GREAT_OWL_HOLLOW,
        MR_AGES_APOTHECARY,
        BRISBY_CINDERBLOCK_HOME,
    )
}


def list_scene_names() -> list[str]:
    """Return the display names of all available scenes in registry order."""
    return [spec.name for spec in (
        GREAT_OWL_HOLLOW,
        MR_AGES_APOTHECARY,
        BRISBY_CINDERBLOCK_HOME,
    )]


def get_scene(name: str) -> SceneSpec:
    """Look up a scene by name or slug (case-insensitive).

    Accepts the registered slug (``great-owl-hollow``), the display name
    (``The Great Owl's Hollow``), or any reasonable slugged variation.

    Raises ``ValueError`` listing all available scenes when no match exists.
    """
    key = slug(name.strip())
    if key in SCENES:
        return SCENES[key]
    normalized = "".join(ch for ch in name.lower() if ch.isalnum())
    for spec in SCENES.values():
        if normalized == "".join(ch for ch in spec.name.lower() if ch.isalnum()):
            return spec
    available = ", ".join(f"{spec.name} ({spec.slug})" for spec in SCENES.values())
    raise ValueError(
        f"No scene named {name!r}. Available scenes: {available}."
    )
