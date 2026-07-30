"""Prompt building utilities for characters and scene backgrounds."""

from __future__ import annotations

import argparse
from pathlib import Path

from blueprint_generator import slug
from blueprint_generator.utils.characters import CharacterSpec, get_character
from blueprint_generator.utils.scenes import BackgroundSpec, SceneSpec, get_scene
from blueprint_generator.utils.models import Attempt, Subject
from movie_config import get_movie_info


def build_initial_prompt(character: CharacterSpec) -> str:
    """Build the initial image generation prompt for a character style guide."""
    movie_info = get_movie_info()
    display_name = character.display_name()
    return f"""Create a polished {display_name} character style guide for a hand-painted
{movie_info.style}. Deliver one cohesive 16:9 reference
image with a large three-quarter hero pose plus smaller front, profile, and back
turnaround views, detail callouts for key features, and a clear silhouette read.

{display_name} is {character.identity}: {character.appearance}. Keep true animal anatomy visible beneath garments.
Feature oversized glossy eyes with stacked white catchlight highlights and tufted
spiky fur/feather silhouettes breaking outer contours.

Rendering style: hand-inked tapered dark-brown linework (no black vector lines),
two-tone cel shading, dense gouache and watercolor paper texture. Lighting: strong
warm amber/gold key light against deep teal/indigo shadow with continuous 360-degree
cool-gold rim lighting. Frame from a low rodent eye-level (2-12 inches high) with
soft-focus dark foreground elements framing 20-30% of the borders.

Avoid {character.avoid}."""


def build_review_system_instruction(character: CharacterSpec) -> str:
    """Build the reviewer LLM system instruction for a character style guide."""
    movie_info = get_movie_info()
    display_name = character.display_name()
    return f"""You are a world-class visual development director and production designer specializing in {movie_info.style}.

Your job is to critically review the supplied {display_name} character reference sheet image against the requested prompt, analyze any previous review iterations you gave on earlier images, and decide whether the current image meets feature-film production standards.

When past review iterations are provided:
- Treat them as clearly labeled historical feedback from previous rounds in this review process.
- Critique the results of your past instructions: evaluate whether the image generator successfully implemented your prior feedback/revised prompt, or if it introduced new flaws.
- Refine and improve your review process based on how effectively previous prompt changes moved the artwork toward the target aesthetic.

Apply strict aesthetic & technical visual criteria for {display_name}:
1. Character Identity & Anatomy: {character.identity}. Must read as a real {character.species} first and a person second. Required visual features, garment, and posture: {character.appearance}. Must retain true animal anatomy under garments, oversized glossy eyes with stacked white highlights, and tufted spiky fur/feather silhouettes breaking contours.
2. Linework & Rendering: Expressive hand-inked tapered lines (dark brown, not black/vector), rich 2-tone cel shading, dense gouache/watercolor textured paint effect. Reject clean vector art, 3D CGI, smooth plastic gradients, or digital glow filters.
3. Staging & Lighting: Low rodent eye-level perspective (2-12 inches high). Strong single practical light source producing rich amber/gold highlights contrasted with deep teal/indigo shadows and continuous 360-degree cool-gold rim lighting. Dark, soft-focus foreground elements framing 20-30% of edges.
4. Sheet Organization & Quality: Clear 16:9 reference sheet with a prominent three-quarter hero pose plus turnaround views (front, profile, back) and detail callouts. Zero anatomy glitches, zero extra limbs, zero text/logos/watermarks/labels.
5. Character Style Befitting the Narrative (HARD GATE): The design itself must make the viewer FEEL this character's role in the story at first glance. Apply character-design DNA: grotesque-yet-appealing shapes, asymmetry and age/wear etched into the silhouette, tufted spiky fur or feathers breaking every contour, and oversized glossy eyes that carry the entire emotional performance. Ask yourself: "Could this exact design only exist in {movie_info.title}, and does it trigger the precise emotional reaction the narrative demands (awe, fear, tenderness, menace)?" A competent, cute, symmetrical, or generic rendering that could be dropped into any modern cartoon or children's book FAILS this criterion even when every technical box above is checked.

Be exacting and demanding. Do NOT accept merely because an image is visually pleasing or artistic if it misses key style mandates or reference sheet layout needs. NEVER accept an image that fails criterion 5, no matter how polished or technically correct it is: "generic but well-executed" is always a rejection. When rejecting, provide a complete, self-contained revised image prompt that precisely remedies all identified defects — especially any missing narrative emotional register or character-style DNA — while preserving all correct details.

Return JSON only with this schema:
{{"accepted": boolean, "score": integer from 0 to 100, "learning": "one concise lesson for the next iteration", "feedback": "specific visual findings", "revised_prompt": "a complete replacement image prompt when rejected; empty string when accepted"}}."""


def build_scene_initial_prompt(scene: SceneSpec, background: BackgroundSpec) -> str:
    """Build the initial image generation prompt for a scene background plate."""
    movie_info = get_movie_info()
    return f"""Create a polished production background plate for a hand-painted
{movie_info.style}.
Deliver one cohesive 16:9 background with NO characters or creatures in frame —
a clean plate ready for cel compositing.

Scene: {scene.name} — {scene.logline}.
This plate depicts {background.description}.

Paint in dense opaque gouache with transparent watercolor washes on heavy-tooth
textured paper, using sponge-dabbing, dry-brush work on bark and stone, and fine
splatter for dirt and damp mist. Gothic organic forms only — gnarled tangled
roots, arched burrows, sagging beams — with zero straight edges or digital
symmetry. Human-scale objects, if any, loom gargantuan from this rodent
macro perspective.

Lighting: {background.lighting}. Keep 60-70% of the frame in deep shadow, warm
amber/gold light at the epicenter shifting to cool teal/indigo ambient shadow,
a soft airbrushed glow radiating from the light source, and volumetric dust
motes in the light path. Mood: {background.mood}.

Frame from a low rodent macro camera (2-12 inches above ground) with the
environment dominating the frame, a heavy vignette, and soft-focus dark
foreground silhouettes (roots, vines, cracked edges) occluding 20-30% of the
frame borders. No characters, no text, no watermarks."""


def build_scene_review_system_instruction(scene: SceneSpec, background: BackgroundSpec) -> str:
    """Build the reviewer LLM system instruction for a scene background plate."""
    movie_info = get_movie_info()
    return f"""You are a world-class background art director and production designer specializing in {movie_info.style}.

Your job is to critically review the supplied background plate for the scene "{scene.name}" ({scene.logline}) against the requested prompt, analyze any previous review iterations you gave on earlier images, and decide whether the current image meets feature-film production standards.

When past review iterations are provided:
- Treat them as clearly labeled historical feedback from previous rounds in this review process.
- Critique the results of your past instructions: evaluate whether the image generator successfully implemented your prior feedback/revised prompt, or if it introduced new flaws.
- Refine and improve your review process based on how effectively previous prompt changes moved the artwork toward the target aesthetic.

Apply strict aesthetic & technical visual criteria for this background plate:
1. Environment Content: The plate must depict {background.description}. Gothic organic forms only (gnarled roots, arched burrows, sagging beams); zero straight edges, zero modern props, zero digital symmetry. Rodent macro scale: human objects must loom gargantuan.
2. Medium & Texture: Dense opaque gouache and transparent watercolor on heavy-tooth paper with sponge-dabbing, dry-brush, and fine splatter texture. Reject clean vector art, 3D CGI, smooth plastic gradients, photographic realism, or digital glow filters.
3. Lighting & Palette: {background.lighting}. A single clearly identifiable practical light source; 60-70% of frame in deep shadow; warm amber/gold key against cool teal/indigo ambient shadow; soft airbrushed bloom around the source; volumetric dust motes in the light path.
4. Staging & Depth: Low rodent macro camera (2-12 inches above ground); environment dominating the frame; soft-focus dark foreground silhouettes occluding 20-30% of frame borders; heavy vignette. The plate must feel {background.mood}.
5. Clean Plate & Narrative Register (HARD GATE): NO characters or creatures anywhere in frame, no text, logos, or watermarks — this is a production background for cel compositing. And the environment itself must make the viewer FEEL the scene's role in the story at first glance ({scene.logline}). Ask yourself: "Could this exact background only exist in {movie_info.title}, and does it trigger the precise emotional reaction the narrative demands?" A competent, pretty, generic fantasy backdrop that could be dropped into any modern cartoon FAILS this criterion even when every technical box above is checked.

Be exacting and demanding. Do NOT accept merely because an image is visually pleasing or artistic if it misses key style mandates or background plate needs. NEVER accept an image that fails criterion 5, no matter how polished or technically correct it is: "generic but well-executed" is always a rejection. When rejecting, provide a complete, self-contained revised image prompt that precisely remedies all identified defects — especially any missing narrative emotional register or environment DNA — while preserving all correct details.

Return JSON only with this schema:
{{"accepted": boolean, "score": integer from 0 to 100, "learning": "one concise lesson for the next iteration", "feedback": "specific visual findings", "revised_prompt": "a complete replacement image prompt when rejected; empty string when accepted"}}."""


def build_history_context(history: list[tuple[Attempt, bytes]]) -> str:
    """Format past iteration records as context for the reviewer."""
    if not history:
        return ""
    lines = ["=== PREVIOUS REVIEW ITERATIONS HISTORY ==="]
    for attempt, _ in history:
        verdict = "accepted" if attempt.accepted else "rejected"
        lines.append(f"--- Iteration {attempt.number} ({verdict}) ---")
        lines.append(f"Prompt provided to image generator:\n{attempt.prompt_used}")
        lines.append(f"Your score: {attempt.score if attempt.score is not None else 'N/A'}/100")
        lines.append(f"Your feedback: {attempt.feedback}")
        lines.append(f"Your lesson learned: {attempt.learning}")
        lines.append(f"Prompt change applied: {attempt.prompt_change}\n")
    return "\n".join(lines)


def fallback_revision(prompt: str, feedback: str) -> str:
    """Fallback revised prompt construction when reviewer provides feedback without replacement prompt."""
    return f"{prompt}\n\nCorrection focus from visual review: {feedback.strip()}"


def build_subjects(args: argparse.Namespace) -> list[Subject]:
    """Resolve the CLI target into the list of blueprint subjects to generate."""
    if args.character:
        character = get_character(args.character)
        output = (
            Path(args.output)
            if args.output
            else Path("out") / "blueprint" / slug(character.name)
        )
        return [
            Subject(
                label=f"character {character.name!r}",
                display_name=character.name,
                output_dir=output,
                style_slug=slug(character.name),
                initial_prompt=build_initial_prompt(character),
                review_instruction=build_review_system_instruction(character),
            )
        ]

    scene = get_scene(args.scene)
    base = Path(args.output) if args.output else Path("out") / "blueprint" / scene.slug
    return [
        Subject(
            label=f"scene {scene.name!r} background {background.key!r}",
            display_name=f"{scene.name} — {background.key} background",
            output_dir=base / background.key,
            style_slug=f"{scene.slug}-{background.key}",
            initial_prompt=build_scene_initial_prompt(scene, background),
            review_instruction=build_scene_review_system_instruction(scene, background),
        )
        for background in scene.backgrounds
    ]
