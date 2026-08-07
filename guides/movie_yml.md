# `movie.yml` Style Guide

Every film lives in its own folder under `films/<film>/` and is configured by a
single machine-readable file: **`films/<film>/movie.yml`**. This guide documents
the schema — required fields, optional fields, and conventions. The pipeline tools
(`scriptgen`, `generate-blueprint`, `animator`, and the web console) read **only**
this file; no other per-film document is required.

> Reference implementation: [`films/rats/movie.yml`](../films/rats/movie.yml).
> The file must be valid YAML. Strings may use folded scalars (`>-`) for
> multi-line prose; the loader (`src/movie_config.py`) parses it with `yaml.safe_load`.

---

## 1. Top-Level Layout

```yaml
movie:          # movie metadata, style bible, and direction rules  -> REQUIRED
characters:     # list of character specs                            -> REQUIRED
scenes:         # list of scene locations & background plates        -> REQUIRED
story:          # abridged story beats scriptgen expands             -> REQUIRED
```

All four sections are required. Every tool assumes they exist; list entries may be
empty only if the film genuinely has no characters/scenes/story.

---

## 2. `movie:` — Movie Metadata & Style Bible

> **Used by** = which generative process(es) read the field: `scriptgen` (scene
> scripts), `animator` (video clips), `blueprint` (character & scene plates);
> `—` = not consumed by any generator. "via scripts" marks fields the animator
> only inherits through the generated segment scripts, not by reading `movie.yml`
> directly. See §7 for the full field-by-process matrix.

### Required fields

| Field | Type | Used by | Description |
| :--- | :--- | :--- | :--- |
| `title` | string | scriptgen, animator, blueprint | The film's title (used in the web console header, blueprint descriptions, and logs). |
| `headline` | string | scriptgen | One-line description of the source/material, e.g. `"a short film adaptation of The Rats of NIMH"`. |
| `style` | string | scriptgen, animator, blueprint | The film's complete, prompt-ready look. Combines the named reference (artist/era/technique, e.g. `"Don Bluth's iconic 1980s dark fantasy feature animation style (The Secret of NIMH, 1982)"`) with the dense rendering summary (linework, shading, palette, light, vignette, grain). Used as the director/designer identity in prompts, prepended to every video segment prompt header, and used as the render style for blueprint scene plates. |
| `camera_rules` | string | scriptgen, animator | A one-sentence camera mandate injected into every segment prompt. |
| `hard_direction_rules` | list of strings | scriptgen (animator via scripts) | Strict visual/lighting/animation mandates. Injected verbatim into the `scriptgen` system instruction as non-negotiable direction; each entry is a complete imperative sentence. |

### Optional fields

| Field | Type | Used by | Description |
| :--- | :--- | :--- | :--- |
| `orientation` | string | animator | Output aspect ratio, e.g. `"16:9"`. Defaults to `16:9`. All video providers render at this ratio. Consumed by the animator for the video request aspect ratio. |
| `style_checklist` | list of items | scriptgen, blueprint (animator via scripts) | Do / Don't checklist. Each item has `category`, `do`, and `don_t`. Consumed by `scriptgen` (system instruction) and by blueprint generation (character sheet prompts and both reviewers' hard style gate). |
| `prompt_template` | string | — | A canonical generative prompt template for the film's style — reference material for agents and prompt authors. Not consumed by tooling. |

> **Keep it lean.** The core generation inputs are `style`, `camera_rules`, and
> `hard_direction_rules`. `style` should fuse the film's look: the named
> reference, linework, shading, background medium, lighting/color contrast, rim
> light, vignette, occlusion, and film grain. Longer artistic prose (tone,
> character design, color scripting, cinematography, etc.) does **not** need to
> live in the yml — the pipeline never reads it. Archive such detail in the
> optional `movie.depricated.md` file if you want to keep it around.


### `style_checklist` item shape

```yaml
style_checklist:
  - category: "Line Art"                        # REQUIRED
    do: "Tapered ink lines, soft colored outlines"   # REQUIRED
    don_t: "Vector-clean outlines"                    # REQUIRED (key is don_t)
```

### Example

```yaml
movie:
  title: "The Rats of NIMH"
  headline: "a short film adaptation of The Rats of NIMH"
  style: >-
    Don Bluth's iconic 1980s dark fantasy feature animation style (The Secret of NIMH, 1982):
    hand-painted 2D cel animation with hand-inked tapered lines, 2-tone cel shading,
    painterly gouache backgrounds, warm amber key light against deep teal/indigo
    shadow, 360-degree rim lighting, heavy vignette, film grain.
  camera_rules: "Keep the camera at rodent eye-level (2-12 inches high) around a single dominant practical light source."
  orientation: "16:9"
  hard_direction_rules:
    - "Camera height stays at rodent eye-level unless a shot is deliberately a predator POV."
    - "Every shot orbits a single identifiable practical light source; 60-70% of the frame sits in deep shadow."
```

---

## 3. `characters:` — Character Roster

A list of character specs. All fields are strings.

| Field | Type | Used by | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `name` | string | scriptgen, animator, blueprint | **Yes** | Display name, e.g. `"Mrs Brisby"`. Must be unique. Names are standardized to ALL CAPS (`MRS BRISBY`) for dialogue tags and blueprint lookups. |
| `species` | string | blueprint | Yes | e.g. `"field mouse"`, `"rat"`, `"owl"`. |
| `identity` | string | scriptgen, blueprint | Yes | Who the character is and their role in the story, e.g. `"a widowed field mouse and the story's determined protagonist..."`. |
| `appearance` | string | scriptgen, blueprint | Yes | Full visual recipe: fur/feather colors, eyes, ears, nose, whiskers, garments, posture. Injected into blueprints and character prompts. |
| `voice` | string | scriptgen (animator via scripts) | No | Voice direction (pitch, delivery, accent). Wrapped in `<VOICE>` tags in scripts. Omit for non-speaking characters. |
| `avoid` | string | blueprint | No | Negative prompt guidance, e.g. `"clean vector lines, modern clothing, extra limbs, text, watermarks, and logos"`. |

> **Naming conventions**: `name` must be unique; story entries and CLI arguments
> reference characters by this exact name. Slug forms (`mr-ages`) are derived
> automatically for output folders — avoid punctuation-only variants.

---

## 4. `scenes:` — Scene Locations & Background Plates

A list of scene locations, each carrying one or more background plates used for
cel-composited background generation.

| Field | Type | Used by | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `name` | string | scriptgen, blueprint | **Yes** | Human-readable scene name, e.g. `"Old Barn Field"`. |
| `slug` | string | scriptgen, animator, blueprint | **Yes** | Unique URL-safe identifier, e.g. `"old-barn-field"`. Referenced by story `scene` entries and output folders. |
| `logline` | string | scriptgen, blueprint | Yes | One-sentence description of the location's look and dramatic role. |
| `backgrounds` | list of items | scriptgen, animator, blueprint | No | Background plates. Each item has `key`, `description`, `lighting`, `mood`. |

### Background item shape

```yaml
backgrounds:
  - key: "field-approach"        # REQUIRED, unique within the scene (drives output folder)
    description: "..."           # REQUIRED: the plate content at mouse scale
    lighting: "..."              # REQUIRED: single dominant light source, palette, atmosphere
    mood: "..."                  # REQUIRED: emotional register of the plate
```

---

## 5. `story:` — Abridged Story Beats

A list of story beats that `scriptgen` expands into full scene design documents.
`scene` references a scene `slug`; `characters` reference roster `name`s.

| Field | Type | Used by | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `name` | string | scriptgen, animator | **Yes** | Unique production slug for the beat, e.g. `"frisby_visits_mr_ages"`. Drives output file names (`<name>_part<N>.md`) and the `--name` CLI argument. |
| `title` | string | scriptgen | Yes | Evocative scene title, e.g. `"A Cure for Timothy"`. |
| `scene` | string | scriptgen, animator | Yes | `slug` of the scene location this beat takes place in. |
| `characters` | list of strings | scriptgen | Yes | Roster names appearing in the scene. |
| `emotions` | list of strings | scriptgen | Yes | Key emotions/feelings driving the scene. |
| `actions` | list of strings | scriptgen | Yes | Important actions & talking points. |
| `looks` | list of strings | scriptgen | Yes | Where characters look and their facial expressions. |

> `scriptgen` treats these beats as the **complete** story of the scene: the
> pipeline is instructed to invent no events, history, or implications beyond them.

---

## 6. Film Slugs & Selection

* A folder counts as a film only if it contains a `movie.yml`
  (`films.py` / `web/src/lib/movie.ts`).
* Tools select a film with `--film <slug>` or the `FILM` environment variable;
  the default is the first film folder (alphabetical) under `films/`.
* Folders prefixed with `_` (e.g. `films/_clinicalclarity/`) are git-ignored
  scratch films but still work with the pipeline.
* Each film's rendered assets live in `films/<film>/out/` (`scripts/`,
  `blueprint/`, `animations/`) — never edit those by hand; they are written by
  the tools.

---

## 7. Field Usage by Pipeline Process

Which `movie.yml` fields each generative process actually consumes. This matters
when editing a film: a field's edits only affect the processes marked with a
direct use.

Legend: **Direct** = read from `movie.yml` at runtime; **Indirect** = baked into
artifacts produced earlier (e.g. `style`/`camera_rules` are already in
the generated segment scripts); `—` = not used.

| Field | `scriptgen` (scene scripts) | `animator` (video clips) | `blueprint` (character / scene plates) |
| :--- | :--- | :--- | :--- |
| `movie.title` | display (CLI header) | logging | reviewer narrative hard-gate |
| `movie.headline` | Direct (system instruction) | — | — |
| `movie.style` | Direct (director identity + video-prompt header) | Direct (video-prompt header, via `format.py`) | Direct (image prompts + reviewer identity + scene plate style) |
| `movie.camera_rules` | Direct (video-prompt header) | Direct (video-prompt header, via `format.py`) | — |
| `movie.orientation` | — | Direct (video request aspect ratio) | — |
| `movie.hard_direction_rules` | Direct (system instruction) | Indirect (baked into scripts) | — |
| `movie.style_checklist` | Direct (system instruction style bible) | Indirect (baked into scripts) | Direct (character sheet prompt + both reviewers' style gate) |
| `movie.prompt_template` | — | — | — (reference only) |
| `characters[*]` | Direct (`name`/`species`/`identity`/`appearance`/`voice` → roster & voices) | Direct (`name` → roster match, blueprint lookup, voice tags) | Direct (`name`/`species`/`identity`/`appearance`/`avoid`) |
| `scenes[*]` | Direct (`name`/`slug`/`logline`/`backgrounds` → scene context) | Direct (`slug`/`backgrounds[].key` → background plate lookup) | Direct (`name`/`slug`/`logline` + `backgrounds[].description/lighting/mood`) |
| `story[*]` | Direct (the beat to expand) | Direct (`scene` → scene-slug mapping) | — |

### Notes & rationale

* **Keep the style inputs aligned.** The image/video generation quality depends on
  `style` and `style_checklist` staying consistent with `hard_direction_rules`
  and `camera_rules` — they all flow into different parts of the same look.
* **`scriptgen`** is the heaviest consumer: it turns `story[*]` beats into
  segment scripts whose header carries `style` + `camera_rules`, and
  whose generation is steered by `style`, `headline`, `hard_direction_rules`,
  and `style_checklist`.
* **`animator`** mostly inherits the look from the generated scripts; it adds
  `orientation` (aspect ratio) and uses `story`/`scenes`/`characters` only for
  continuity references and background-plate lookup.
* **`blueprint`** generates *images* (character sheets + background plates), so it
  is the other place `style` lives. It consumes `style` (director identity, scene
  plate style) and `style_checklist` (character sheets and both reviewers). Do not
  rely on the verbose prose fields that were removed — the yml is intentionally
  lean, and the full artistic bible is archived in `movie.depricated.md`.

---

## 8. Adding a New Film

1. `mkdir films/<slug>/`
2. Create `films/<slug>/movie.yml` following this guide (start by copying
   `films/rats/movie.yml`).
3. Verify it loads: `uv run scriptgen` (lists story scenes) or
   `uv run python -c "from movie_config import get_movie_info; print(get_movie_info().title)"`.
