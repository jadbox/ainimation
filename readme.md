# AI Animation Art Pipeline & Production Environment

An automated AI-driven art pipeline and production suite for creating 2D animated feature film content. The codebase is story-agnostic and dynamically driven by configuration in `movie.yml` — the single per-film source of truth for story, characters, scenes, and the full style bible. Multiple films are supported: each film lives in its own folder under `films/<film>/` containing its `movie.yml` and rendered `out/` assets, and every tool selects the film via `--film <slug>` (or the `FILM` environment variable; default: the first film folder found under `films/`). See [`guides/movie_yml.md`](./guides/movie_yml.md) for the `movie.yml` schema reference.

---

## 1. Project Overview & Capabilities

This project automates the multi-stage visual development and animation generation workflow:

1. **Character Blueprint Sheets**: Generates cohesive 16:9 character style guides (hero poses, turnarounds, detail callouts) with production-grade visual standards baked directly into prompts.
2. **Scene Background Plates**: Generates clean, character-free 16:9 production background plates for cel compositing.
3. **30-Second Scene Scripts**: Expands abridged story beats from the `story:` section of `movie.yml` into structured 30-second scene design documents divided into three 10-second segments.
4. **Keyframe Proposals**: Generates start and closing keyframe proposal images (`part-<N>-start-proposal.jpg` / `part-<N>-end-proposal.jpg`) ahead of video generation, referencing character blueprints, background plates, and prior keyframes to lock framing and character poses.
5. **Animated Clips (Pluggable Video Provider)**: Generates 720p 24fps video clips per segment with first/last-frame continuity locking (MiniMax H3 via the MiniMax API directly at 768P by default, Google Gemini Omni 1.1, or OpenRouter Alibaba Wan 3.0 at 480p), exports each clip's first and last frames as `part-<N>-start.jpg` / `part-<N>-end.jpg`, then concatenates the clips into full scene videos with seamless crossfade transitions.
6. **Film Assembly**: The web console can merge available scene `full.mp4` files in story order into `films/<film>/out/animations/film.mp4` and export a midpoint `film-thumb.jpg`.
7. **Web Console**: A local browser UI over the pipeline (scene tables, script generation, blueprint viewing, animator command copy) — see section 4.E.

---

## 2. Configuring Movie & Style Specifications

All movie-specific information — art style, character rosters, scene definitions, story beats, and the full style bible — is defined externally, per film, under `films/<film>/`. The tools themselves carry no film-specific style or aesthetic. The schema is documented in [`guides/movie_yml.md`](./guides/movie_yml.md).

* **`films/<film>/movie.yml`**: The single machine-readable configuration file for one film, loaded by `src/movie_config.py`. Contains:
  * **Movie metadata & style direction**: Title, headline, a prompt-ready `style` (the named reference fused with the look: linework, shading, light/palette, vignette, grain), camera rules, orientation, an optional do/don't `style_checklist`, and an optional `prompt_template`. Keep it lean — the full prose style bible is not read by the pipeline; archive it in `movie.depricated.md` if desired.
  * **Hard direction rules**: List of strict visual/lighting/animation mandates passed into system instructions.
  * **Characters**: List of characters (`name`, `species`, `identity`, `appearance`, `voice`, `avoid`).
  * **Scenes**: List of scene locations (`name`, `slug`, `logline`, `backgrounds`).
  * **Story**: Abridged story beats (`name`, `title`, `scene`, `characters`, `emotions`, `actions`, `looks`) that `scriptgen` expands into full scene design documents. `scene` references a scene location slug; `characters` reference roster names; `looks` records where the characters are looking and their facial expressions.
* **`films/<film>/movie.depricated.md`**: Optional archived copy of a legacy human-readable style bible, kept for reference only. It is **not** read by any tool — all direction must live in `movie.yml`.
* **`films/<film>/out/`**: Rendered assets for the film (`scripts/`, `blueprint/`, `animations/`).

All CLI tools take `--film <slug>` (or honor the `FILM` environment variable) to pick which film folder to read and write; the default is the first film folder found under `films/`. To add a new movie, create `films/<slug>/` with its own `movie.yml`. To adapt an existing film's style, edit its `movie.yml`. The Python code dynamically loads the selected film's `movie.yml` via `src/movie_config.py` without requiring code changes.

---

## 3. Installation & Environment Setup

1. **Install dependencies with `uv`**:
   ```bash
   uv sync
   ```

2. **Set API keys**:
   * Gemini API Key (required):
     ```bash
     export GEMINI_API_KEY="your-gemini-api-key"
     # or export GOOGLE_API_KEY="..."
     ```
   * OpenRouter API Key (required when using `--model openrouter` for video):
     ```bash
     export OPENROUTER_API_KEY="your-openrouter-api-key"
     ```
   * MiniMax API Key (required when using `--model minimax` for video):
     ```bash
     export MINIMAX_API_KEY="your-minimax-api-key"
     ```

3. **External Dependencies**:
   * `ffmpeg` and `ffprobe` on `PATH` for video clip extraction, continuity frame locking, and crossfade combination.
   * `bun` (or `node`/`npm`) for the web console runtime (section 4.E).

---

## 4. CLI Python Scripts & Tooling Usage

### Example End-to-End Pipeline

```bash
# 1. Edit films/<film>/movie.yml to set up the story, characters, scenes, and style bible

# 2. Generate a character style guide or a scene's background plates
uv run generate-blueprint --film <film> --character "<Character Name>"   # character blueprint
uv run generate-blueprint --film <film> --scene <scene-slug>             # scene background plates

# 3. Generate the scene script for a story scene name from movie.yml
uv run scene-script --film <film> --name <story_scene_name> -v

# 4. (Optional) Generate keyframe proposals for scene parts
uv run keyframes --film <film> --scene <story_scene_name> --parts 0 --start

# 5. Generate video for just part 0 of the scene; full.mp4 is composed
#    automatically as additional parts are made
uv run python src/animator.py --film <film> --scene <story_scene_name> --parts 0 --model minimax
```

### A. Blueprint Generator (`generate-blueprint` / `generate.sh`)

Generates character style guide sheets (`--character`) or scene background plates (`--scene`) in a direct high-fidelity generation pass using Google's Nano Banana 2 image model (`gemini-3.1-flash-image-preview`), baking all production review standards directly into the prompts.

* **CLI Commands**:
  ```bash
  # Generate character style guide
  uv run generate-blueprint --character "<Character Name>"

  # Force regenerate a character blueprint
  uv run generate-blueprint --character "<Character Name>" --force

  # Generate scene background plates
  uv run generate-blueprint --scene <scene-slug>
  ```

* **Key Options**:
  * `--film SLUG`: Film folder under `films/<slug>/` to use (default: first film found, or `$FILM`).
  * `--character NAME`: Character display name from the film's `movie.yml`.
  * `--scene NAME`: Scene name or slug from the film's `movie.yml`.
  * `--output DIR`: Custom output path (default: `films/<film>/out/blueprint/<slug>/`).
  * `--image-model MODEL`: Gemini image model ID (default: `gemini-3.1-flash-image-preview`).
  * `--force`: Regenerate the blueprint even if an existing style image already exists.
  * `--new`: Ignore previous run's `prompt.txt` and start from a fresh spec prompt.

* **Output Artifacts** (written to `films/<film>/out/blueprint/<subject-slug>/`):
  * `<subject-slug>-style.jpg`: Primary 720p style reference image.
  * `attempt-01.jpg`: Reference plate for the animator pipeline.
  * `prompt.txt`: Production prompt used for the image generation.
  * `iterations.md`: Summary documentation with model, prompt, and image details.

* **Module Layout**:
  * `src/blueprint.py`: Executable CLI launcher script.
  * `src/blueprint_generator/`: Package containing the generator execution loop and modular helpers under `utils/` for models, prompts, image processing, and dynamic YAML character/scene lookups.

---

### B. Scene Script Generator (`scriptgen` / `scene-script`)

Expands an abridged story scene from the `story:` section of the film's `movie.yml` into detailed segment design files written per scene segment (e.g `films/<film>/out/scripts/<story_scene_name>_part0.md`). Generation runs through OpenRouter's chat completions API.

* **CLI Commands**:
  ```bash
  # List the story scenes available for --name
  uv run scriptgen

   # Expand a story scene into three 10-second prompt documents (the default)
   uv run scriptgen --name <story_scene_name>

   # Expand a story scene into five 10-second prompt documents
   uv run scriptgen --name <story_scene_name> --parts 5
  ```

* **Key Options**:
  * `--film SLUG`: Film folder under `films/<slug>/` to use (default: first film found, or `$FILM`).
   * `--name NAME`: Story scene name from the `story:` section of the film's `movie.yml` (written to `films/<film>/out/scripts/<name>_part0.md`, etc.). Omit to list all available story scenes.
   * `--parts N`: Number of 10-second scene parts to generate (1-10, default: 3).
   * `--model MODEL`: Model slug used to expand the scene (default: `google/gemini-3.8-flash`). The shortcuts `gemini` and `gemini-3.8-flash` map to `google/gemini-3.8-flash` on OpenRouter. Requires `OPENROUTER_API_KEY` or `GEMINI_API_KEY` (`GOOGLE_API_KEY`).
   * `-v` / `--verbose`: Stream the LLM output (reasoning/thinking plus final content) as it is generated.
   * `--output PATH`: Custom output file or directory base path.
   * `--force`: Overwrite existing scripts if they already exist.

* **Director's Treatment + Simultaneous Multi-Part Generation**: generation is two-phase. First, a **Director's Treatment** pass plans the *entire* scene as one short film (scroll-stopping hook, dramatic question, character roles/dynamics, per-part escalation ladder with micro-story arcs and emotional shifts, the turn, the unforgettable image, a 5–8 line dialogue spine, and the final held frame). Then all requested 10-second segments are generated simultaneously in a single prompt separated by explicit `<PART0>`, `<PART1>`, `<PART2>`, ... sections. Thinking level is set to `high` for deep scene planning.

* **Embedded Quality & Character Directing**: All directorial quality standards are front-loaded directly into the generation prompt — emotional storytelling in every 10-second part, defined active roles for every character present (no idle/passive characters), vivid kinetic action with tactile prop/environment interaction, unbroken continuous camera motion, and strict show-don't-tell mandates.

* **Length Validation & Export Splitting**: each saved segment prompt file (static preamble/mandates + segment body) must stay strictly under the character budget (`MAX_SCRIPT_CHARS`, default: 5,800 chars, ensuring safe headroom under the 7,000 video model API ceiling; customizable via `--max-chars`). If any individual part is oversized, `scriptgen` runs a targeted condensation pass using a dedicated editor system instruction up to 3 times, followed by deterministic fallback trimming. The generated document is then split into individual part export files (`films/<film>/out/scripts/<name>_part<N>.md`) with common static instructions prepended as a prefix.

* **Dialogue Guide (Instagram pacing)**: the system prompt governs dialogue volume and economy — roughly 50–70 spoken words across a scene split into 5–8 lines, max 8–10 words per line, one job per line (ASK/ANSWER/DEFLECT/WARN/REVEAL), the deletion test, and the final line as the shortest punch.

* **Output Document Structure** (`films/<film>/out/scripts/<name>_part<N>.md`):
  * Pre-formatted segment video prompts following the MiniMax prompt-writing guide: a fixed preamble (characters appearing with voice tags, reference alignment instructions, mandates), followed by the three labeled core fields — `integrated_multimodal_description:` (a single continuous paragraph describing `[Shot 1]` spatial mapping and continuous camera motion followed by sequential beats in chronological order without bracketed timestamps, with `(S1)`/`(S2)` speaker IDs and `<d>[English] …</d>` dialogue tags), `overall_soundscape:` (1–2 sentences), and `non_diegetic_music:` (1 sentence or `N/A`).

---

### C. Animator (`animator` / `src/animator.py`)

Generates animated 720p 24fps video clips for each segment prompt in `films/<film>/out/scripts/<scene>_part<N>.md` using a pluggable video provider — MiniMax H3 via the MiniMax API directly (`MiniMax-H3`) at 768P by default, Google Gemini Omni 1.1 (`gemini-omni-1.1-flash`, 720p) via the Gemini API, or OpenRouter's async videos API with Alibaba Wan 3.0 (`alibaba/wan-3.0`) at 480p — maintaining frame-0 visual continuity between segments, and combining them into a full video with crossfade transitions.

* **CLI Commands**:
  ```bash
  # Generate all missing segment clips and combine into full.mp4 (MiniMax H3)
  uv run animator --scene <story_scene_name>

  # Generate using the OpenRouter provider (Alibaba Wan 3.0 at 480p)
  uv run animator --scene <story_scene_name> --model openrouter

  # Generate using the MiniMax API directly (MiniMax H3 at 768P)
  uv run animator --scene <story_scene_name> --model minimax

  # Generate only segment 2 (0:20-0:30)
  uv run animator --scene <story_scene_name> --parts 2

  # Generate a new version of segment 1 (e.g. part-1-v1.mp4)
  uv run animator --scene <story_scene_name> --parts 1

  # Generate a part with explicitly supplied opening and closing frames
  uv run animator --scene <story_scene_name> --parts 1 --frame_start path/to/start.jpg --frame_end path/to/end.jpg

  # Re-combine existing part clips without making API calls
  uv run animator --scene <story_scene_name> --compose-only
  ```

* **Key Options**:
  * `--film SLUG`: Film folder under `films/<slug>/` to use (default: first film found, or `$FILM`).
  * `--scene NAME`: Scene script name (reads `films/<film>/out/scripts/<scene>_part<N>.md`).
  * `--parts N`: Generate only segment index `N` (0-indexed). Automatically creates a new version (`-v1`, `-v2`, ...) if the base clip already exists. Default: generate all missing segments.
  * `--compose-only`: Skip API calls and combine the highest version of each existing `part-*.mp4` clip into `full.mp4`.
   * `--frame_start PATH` / `--frame-start PATH`: Use an image as the mandatory opening frame for every generated part, overriding automatically discovered prior-part continuity frames.
   * `--frame_end PATH` / `--frame-end PATH`: Use an image as the mandatory closing frame for every generated part.
  * `--model MODEL`: Video model spec — a `provider:model-id` pair (e.g. `google:gemini-omni-1.1-flash`, `minimax:MiniMax-H3`, `openrouter:alibaba/wan-3.0`) or a provider shortcut (`google`, `minimax`, `openrouter`; `gemini` aliases `google`). Default: `minimax` (MiniMax H3 via the MiniMax API). The `google` provider uses `GEMINI_API_KEY`/`GOOGLE_API_KEY` and defaults to Gemini Omni 1.1 (`gemini-omni-1.1-flash`) at 720p (supported Omni resolutions: 360p, 720p, 1080p, 4k). The `openrouter` provider uses `OPENROUTER_API_KEY` and defaults to `alibaba/wan-3.0` at `480p`. The `minimax` provider uses `MINIMAX_API_KEY` and defaults to `MiniMax-H3` at `768P`. (The older `--provider` / `--video-model` flags are still accepted as deprecated aliases.)
  * `--duration SECONDS`: Duration per segment (default: 10).
  * `--timeout SECONDS`: Polling timeout per video request (default: 600).
  * `--scripts-dir DIR`: Directory containing scene scripts (default: `films/<film>/out/scripts`).
  * `--blueprint-dir DIR`: Directory containing blueprint character reference images (default: `films/<film>/out/blueprint`).
  * `--output DIR`: Custom output folder (default: `films/<film>/out/animations/<scene>/`).

* **Workflow & Continuity Mechanics**:
  1. Reads `films/<film>/out/scripts/<scene>_part<N>.md` for each segment and extracts characters from the prompt.
  2. Loads latest blueprint images (`attempt-*.jpg`) from `films/<film>/out/blueprint/<character-slug>/` as character reference inputs. Missing blueprints are generated automatically via `generate-blueprint` (the exact command is echoed as `CREATING BLUEPRINT: ...`).
  3. For the first segment (index 0), attaches the scene location's background plate (`films/<film>/out/blueprint/<scene-slug>/attempt-*.jpg`, auto-generated if missing) as an environment reference so the set layout and depth layering stay anchored. The script name is mapped to a scene location via the `story:` section of the film's `movie.yml`.
   4. For segment `N > 0`, locates the latest last frame of segment `N-1` (`part-<N-1>-end.jpg` or `part-<N-1>-v<V>-end.jpg`, falling back to extracting it from the latest clip via `ffmpeg`) and sends it as a mandatory opening frame reference for exact visual/background continuity (no background plate is attached to these segments).
   5. If `--frame-end` is supplied, attaches it as a mandatory closing frame reference so the clip's final frame lines up with that image.
   6. Tacks reference image tags (<IMAGE_REF_N>) and continuity/opening/closing frame instructions onto the segment prompt, saving the final tagged prompt to `films/<film>/out/animations/<scene>/part-<N>-prompt.md` (or `-v<V>-prompt.md`).
   7. Generates `part-<N>.mp4` (or `-v1.mp4`, `-v2.mp4`) for each segment and exports its first and last frames as `part-<N>-start.jpg` and `part-<N>-end.jpg`.
   8. Combines all parts (using the highest available version for each part) into `films/<film>/out/animations/<scene>/full.mp4` with a 0.2s crossfade transition using `ffmpeg`.

* **Module Layout**:
  * `src/animator.py`: Executable CLI launcher script.
  * `src/animator/`: Package containing submodules for config (`config.py`), modular video providers (`providers/` — `base.py`, `minimax.py`, `openrouter.py`, `gemini.py`, `factory.py`), script parsing (`script.py`), prompt building (`prompt.py`), video media & ffmpeg processing (`media.py`), and CLI orchestration (`cli.py`).

---

### D. Keyframe Generator (`keyframes` / `generate-keyframes` / `src/keyframes.py`)

Generates 16:9 start and/or end keyframe proposal images for scene script parts ahead of animation (`part-<N>-start-proposal.jpg` / `part-<N>-end-proposal.jpg`). If a proposal file already exists, new generations automatically create versioned files (`-v1.jpg`, `-v2.jpg`, etc.) so multiple alternatives can be generated and compared in the web UI. Reuses character blueprints and scene background plates as visual references, and supports explicit `--ref-prev` and `--ref-after` image parameters for scene continuity or generating midway keyframes situated between prior and after frames. Outputs a direct file link in the terminal for human review.

* **CLI Commands**:
  ```bash
  # Generate start keyframe proposal for segment 0
  uv run keyframes --scene <story_scene_name> --parts 0 --start

  # Generate both start and end keyframe proposals for segment 0
  uv run keyframes --scene <story_scene_name> --parts 0 --both

  # Generate start keyframe for segment 1 using segment 0's proposal as previous reference
  uv run keyframes --scene <story_scene_name> --parts 1 --start --ref-prev part-0-end-proposal.jpg

  # Generate a keyframe proposal bridging between a previous frame and an after/next frame
  uv run keyframes --scene <story_scene_name> --parts 1 --start --ref-prev part-0-end-proposal.jpg --ref-after part-1-end-proposal.jpg
  ```

* **Key Options**:
  * `--film SLUG`: Film folder under `films/<slug>/` to use (default: first film found, or `$FILM`).
  * `--scene NAME`: Story scene name from `movie.yml` (reads `films/<film>/out/scripts/<name>_part<N>.md`).
  * `--parts N` / `--part N`: Segment index (0-indexed). Default: all segments in the scene.
  * `--type {start,end,both}` / `--frame {start,end,both}`: Type of keyframe to generate (default: `start`).
  * `--start` / `--end` / `--both`: Shortcut flags for keyframe type.
  * `--ref-prev PATH` / `--ref PATH`: Image file to use as previous / earlier keyframe reference (absolute, relative, or in the scene animations folder).
  * `--ref-after PATH`: Image file to use as after / subsequent keyframe reference (absolute, relative, or in the scene animations folder).
  * `--image-model MODEL`: Gemini image generation model ID (default: `gemini-3.1-flash-image-preview`).
  * `--output DIR`: Custom output directory (default: `films/<film>/out/animations/<scene>/`).

* **Output Artifacts** (written to `films/<film>/out/animations/<scene>/`):
  * `part-<N>-start-proposal.jpg` (or `-v1.jpg`, `-v2.jpg`): 1280x720 16:9 opening keyframe proposal image.
  * `part-<N>-end-proposal.jpg` (or `-v1.jpg`, `-v2.jpg`): 1280x720 16:9 closing keyframe proposal image.
  * `part-<N>-<start|end>-proposal-prompt.txt` (or `-v1-prompt.txt`): Final prompt used for generation.

---

### E. Web Console (`./start_web.sh`)

A local Astro + Tailwind web UI over the pipeline tools — no authentication, intended to run on your machine alongside the Python pipeline.

* **Running**:
  ```bash
  ./start_web.sh   # installs web dependencies if needed, then serves http://127.0.0.1:8080 (pass --port to change)
  ```

* **Features**:
  * Multi-film support: routes by film (`/<film>`, `/<film>/scene/...`); `/` redirects to the default film (first folder under `films/`, or `$FILM`). A film switcher appears in the header when more than one film exists, and the header title always reflects the selected film's `movie.yml` title.
  * Scene table driven by the `story:` section of the film's `movie.yml`, with live script/blueprint/video status from `films/<film>/out/`.
  * **View scripts** page renders all segment scripts with a sticky index, and hosts script generation: a **Generate scripts** button (when no scripts exist) or **Regenerate scripts** button (when they do), each with a number-of-parts selector, that runs `uv run scriptgen -v --film <film> --name <scene>` on the server and streams output into a terminal panel.
  * **Blueprint pages** view character and background design sheets and can trigger `generate-blueprint`.
  * **Animate page** presents one command per part with a GENERATE dropdown (model selection: Google Omni 1.1, MiniMax H3, or OpenRouter Wan 3.0; plus video length and keyframe frame overrides) and opens the CLI terminal modal to run it (streaming output) or copy it to your terminal; the scene page's **copy animator cmd** copies `uv run animator --film <film> --scene <scene>` to the clipboard.

* See [`web/README.md`](./web/README.md) for details (production build, environment overrides).

---

## 5. Automated AI Pipeline Architecture

```
[ films/<film>/movie.yml ]
          │
          ▼
[ scriptgen ] ──► Generates Segment Prompts (films/<film>/out/scripts/<scene>_part<N>.md)
          │
          ▼
[ generate-blueprint ] ──► Generates Character & Background Blueprints (films/<film>/out/blueprint/...)
          │
          ├──► (Optional) [ keyframes ] ──► Start/End Keyframe Proposals (part-<N>-<start|end>-proposal.jpg)
          │                                  │ (Used as --frame-start / --frame-end in animator)
          ▼                                  ▼
[ animator ] ──► Segment Video Generation (Pluggable Provider: MiniMax / Gemini / OpenRouter)
          │
          ├──► Segment 0 (0:00-0:10) ──► films/<film>/out/animations/<scene>/part-0.mp4
          │                                     │ (Exports part-0-start.jpg and part-0-end.jpg)
          ├──► Segment 1 (0:10-0:20) ◄──────────┘ (part-0-end.jpg as opening-frame reference)
          │            │
          │            ▼ ──► films/<film>/out/animations/<scene>/part-1.mp4
          │                     │ (Exports part-1-start.jpg and part-1-end.jpg)
          ├──► Segment 2 (0:20-0:30) ◄──────────┘ (part-1-end.jpg as opening-frame reference)
          │            │
          │            ▼ ──► films/<film>/out/animations/<scene>/part-2.mp4
          │
          ▼
[ ffmpeg Crossfade Pass ] ──► Combined Final Scene Video (films/<film>/out/animations/<scene>/full.mp4)
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Author attribution is required if this project is forked or used:
**Jonathan Dunlap (Github @jadbox)**
