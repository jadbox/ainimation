"""Prompt building utilities for characters and scene backgrounds."""

from __future__ import annotations

import argparse
from pathlib import Path

from blueprint_generator import slug
from blueprint_generator.utils.characters import CharacterSpec, get_character
from blueprint_generator.utils.scenes import BackgroundSpec, SceneSpec, get_scene
from blueprint_generator.utils.models import Subject
from films import film_blueprint_dir
from movie_config import get_film, get_movie_info


def render_style_checklist(movie_info, categories: list[str] | None = None) -> str:
    """Render the film's do/don't style checklist, optionally filtered by category.

    Returns an empty string when the film defines no ``style_checklist``.
    """
    items = movie_info.style_checklist
    if categories is not None:
        items = [item for item in items if item.category in categories]
    return "\n".join(
        f"- {item.category}: DO {item.do} — DON'T {item.don_t}"
        for item in items
    )


def build_initial_prompt(character: CharacterSpec) -> str:
    """Build the image generation prompt for a character model sheet, baking in all visual review standards."""
    movie_info = get_movie_info()
    display_name = character.display_name()
    checklist = render_style_checklist(movie_info, categories=["Line Art", "Characters"])
    checklist_block = (
        f"\nFollow the film's style checklist (mandatory do's and don'ts):\n{checklist}\n"
        if checklist
        else ""
    )
    return f"""Create a formal 1980s animation production model sheet for {display_name} in
the hand-painted {movie_info.style}. Deliver one cohesive, true 16:9 reference
image containing four full-body, head-to-toe views of the same character: front,
strict profile, back, and three-quarter. Arrange the views in a clean horizontal
turnaround lineup on one shared baseline, with generous, even spacing and a clear
silhouette read. Every ear, hand, foot, tail, garment edge, and other extremity
must remain fully inside the frame.

The entire canvas behind and between the figures is strictly one flat, uniform solid medium
slate-blue color (#4A5D6E), filling every pixel edge-to-edge. Absolutely NO white, cream, parchment,
paper texture, gradient, vignette, scenic setting, floor plane, border, margin,
frame, prop, or foreground occlusion. Use neutral, even studio lighting with at
most a subtle contact shadow directly below each figure's feet.

CHARACTER IDENTITY & ANATOMICAL INTEGRITY:
{display_name} is a {character.species} — {character.identity}: {character.appearance}.
Must read as a real {character.species} first and a person second: keep true animal anatomy and skeletal
structure visible beneath garments. Oversized glossy eyes with 2-3 stacked white highlights carry the entire
emotional performance. Tufted spiky fur or feather silhouettes break contours.

LINEWORK & RENDERING STANDARDS:
Expressive hand-inked tapered lines (soft dark brown or colored ink outlines, never harsh pure-black vector strokes),
rich 2-tone cel shading, and dense gouache and transparent watercolor textured paint effect with fine tooth.
Reject clean vector art, 3D CGI, smooth plastic gradients, or digital glow filters.

NARRATIVE CHARACTER STYLE:
The design itself must make the viewer immediately FEEL this character's role in {movie_info.title} at first glance
(conveying {character.identity} with rich emotional register: awe, fear, tenderness, or menace). Apply expressive,
organic character shapes with subtle asymmetry and personality etched into the silhouette.
{checklist_block}
This is a formal character turnaround sheet, not a cinematic scene, illustration,
collage, or pose montage. The film's rendering medium and linework apply to the
character art only. No text, labels, arrows, callouts, logos, or watermarks anywhere in the image.

Avoid {character.avoid}."""


def build_scene_initial_prompt(scene: SceneSpec, background: BackgroundSpec) -> str:
    """Build the image generation prompt for a scene background plate, baking in all visual review standards."""
    movie_info = get_movie_info()
    extras = []
    if background.lighting:
        extras.append(f"Lighting: {background.lighting}.")
    if background.mood:
        extras.append(f"Mood: {background.mood}.")
    extra_clause = f"\n{' '.join(extras)}" if extras else ""
    checklist = render_style_checklist(movie_info, categories=["Backgrounds"])
    checklist_block = (
        f"\nFollow the film's style checklist for backgrounds:\n{checklist}\n"
        if checklist
        else ""
    )
    return f"""Create a polished production background plate for a hand-painted
{movie_info.style}.
Deliver one cohesive 16:9 background with NO characters or creatures in frame —
a clean plate ready for cel compositing.

Scene: {scene.name} — {scene.logline}.
This plate depicts {background.description}.{extra_clause}

PRODUCTION BACKGROUND PLATE MANDATE (HARD GATE):
ABSOLUTELY NO characters, animals, creatures, people, figures, or silhouettes anywhere in the frame.
Every pixel is pure environment set for 2D cel compositing. No text, titles, watermarks, signatures, or logos.

ENVIRONMENT DNA & MACRO STAGING:
Paint this plate in the film's style: {movie_info.style} Gothic organic
forms only — gnarled tangled roots, arched burrows, sagging beams — with zero
straight edges or digital symmetry. Human-scale objects, if any, loom gargantuan
from this rodent macro perspective.
Frame from a low rodent macro camera (2-12 inches above ground) with the
environment dominating the frame, a heavy vignette, and soft-focus dark
foreground silhouettes (roots, vines, cracked edges) occluding 20-30% of the
frame borders, framing a richly layered midground and deep shadowed background.

MEDIUM & TEXTURE:
Dense opaque gouache and transparent watercolor on heavy-tooth paper with visible sponge-dabbing,
dry-brush scumbling, and fine paint splatter texture. Reject clean vector lines, 3D CGI rendering,
smooth plastic gradients, photographic realism, or digital glow filters.

LIGHTING, ATMOSPHERE & NARRATIVE REGISTER:
Lighting and atmosphere must faithfully reflect the plate description ({background.description}).
Keep 60-70% of the frame in deep shadow, with warm amber/gold key light blooming softly from
identifiable practical light sources against cool teal/indigo ambient shadow, and volumetric dust
motes drifting in the light beam. The environment itself must make the viewer immediately FEEL the
scene's emotional stakes and role in the story ({scene.logline}) at first glance.
{checklist_block}"""


def build_subjects(args: argparse.Namespace) -> list[Subject]:
    """Resolve the CLI target into the list of blueprint subjects to generate."""
    if args.character:
        character = get_character(args.character)
        output = (
            Path(args.output)
            if args.output
            else film_blueprint_dir(get_film()) / slug(character.name)
        )
        return [
            Subject(
                label=f"character {character.name!r}",
                display_name=character.name,
                output_dir=output,
                style_slug=slug(character.name),
                initial_prompt=build_initial_prompt(character),
            )
        ]

    scene = get_scene(args.scene)
    base = (
        Path(args.output)
        if args.output
        else film_blueprint_dir(get_film()) / scene.slug
    )
    return [
        Subject(
            label=f"scene {scene.name!r} background {background.key!r}",
            display_name=f"{scene.name} — {background.key} background",
            output_dir=base / background.key,
            style_slug=f"{scene.slug}-{background.key}",
            initial_prompt=build_scene_initial_prompt(scene, background),
        )
        for background in scene.backgrounds
    ]
