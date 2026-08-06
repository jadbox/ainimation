# AI Animation Art Pipeline & Production Environment

An automated AI-driven art pipeline and production suite for creating 2D animated feature film content. The codebase is story-agnostic and dynamically driven by configuration settings in `movie.yml` and narrative specifications in `movie.md`.

---

## 1. Project Overview & Capabilities

This project automates the multi-stage visual development and animation generation workflow:

1. **Character Blueprint Sheets**: Generates cohesive 16:9 character style guides (hero poses, turnarounds, detail callouts) with automated multi-turn vision LLM review loops.
2. **Scene Background Plates**: Generates clean, character-free 16:9 production background plates for cel compositing.
3. **30-Second Scene Scripts**: Expands abridged story beats from the `story:` section of `movie.yml` into structured 30-second scene design documents divided into three 10-second segments.
4. **Animated Clips (Pluggable Video Provider)**: Generates 720p 24fps video clips per segment with last-frame continuity locking (Google Gemini Omni Flash by default, OpenRouter MiniMax H3 at 768p, or the MiniMax API directly with MiniMax H3 at 768P), then concatenates them into full scene videos with seamless crossfade transitions.

---

## 2. Configuring Movie & Style Specifications

All movie-specific information, character rosters, scene definitions, and hard direction rules are defined externally:

* **`movie.yml`**: Machine-readable configuration located at the project root. Contains:
  * **Movie metadata**: Title, adaptation description, style description, style summary, and camera rules.
  * **Hard direction rules**: List of strict visual/lighting/animation mandates passed into system instructions.
  * **Characters**: List of characters (`name`, `species`, `identity`, `appearance`, `voice`, `avoid`).
  * **Scenes**: List of scene locations (`name`, `slug`, `logline`, `backgrounds`).
  * **Story**: Abridged story beats (`name`, `title`, `scene`, `characters`, `emotions`, `actions`, `looks`) that `scriptgen` expands into full scene design documents. `scene` references a scene location slug; `characters` reference roster names; `looks` records where the characters are looking and their facial expressions.
* **`movie.md`**: Human-readable style bible containing comprehensive artistic guidelines, color scripting, animation mechanics, optical FX passes, and camera director checklists. Refer to [`movie.md`](./movie.md) for full style documentation.

To adapt this pipeline for a new movie or art style, edit `movie.yml` (and `movie.md`). The Python code dynamically loads `movie.yml` via `src/movie_config.py` without requiring code changes.

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
   * OpenRouter API Key (required when using `--provider openrouter` for video, or for OpenRouter review models like Kimi K3):
     ```bash
     export OPENROUTER_API_KEY="your-openrouter-api-key"
     ```
   * MiniMax API Key (required when using `--provider minimax` for video):
     ```bash
     export MINIMAX_API_KEY="your-minimax-api-key"
     ```

3. **External Dependencies**:
   * `ffmpeg` and `ffprobe` on `PATH` for video clip extraction, continuity frame locking, and crossfade combination.

---

## 4. CLI Python Scripts & Tooling Usage

### A. Blueprint Generator (`generate-blueprint` / `generate.sh`)

Generates character style guide sheets (`--character`) or scene background plates (`--scene`) using an image generation model and an automated reviewer LLM loop.

* **CLI Commands**:
  ```bash
  # Generate character style guide
  uv run generate-blueprint --character "Mrs Brisby"

  # Using helper shell script (positional character name)
  ./generate.sh "Mr Ages" --max-iterations 3

  # Generate scene background plates
  uv run generate-blueprint --scene great-owl-hollow
  ```

* **Key Options**:
  * `--character NAME`: Character display name from `movie.yml`.
  * `--scene NAME`: Scene name or slug from `movie.yml`.
  * `--output DIR`: Custom output path (default: `./out/blueprint/<slug>/`).
  * `--image-model MODEL`: Gemini image model ID (default: `gemini-3.1-flash-image-preview`).
  * `--review-model MODEL`: Reviewer model ID (`gemini-3.6-flash` or OpenRouter e.g. `moonshotai/kimi-k3`). Default: `moonshotai/kimi-k3`.
  * `--max-iterations N`: Maximum generation/review attempts per subject (1-4, default: 4).

* **Output Artifacts** (written to `./out/blueprint/<subject-slug>/`):
  * `<subject-slug>-style.jpg`: Accepted or latest 720p style reference image.
  * `prompt.txt`: Final prompt used for the image (reloaded automatically on subsequent runs).
  * `iterations.md`: Full review history, scores, feedback, and prompt adjustments per iteration.
  * `attempt-01.jpg` ... `attempt-04.jpg`: Retained attempt candidates.

* **Module Layout**:
  * `src/blueprint_generator/blueprint.py`: CLI entrypoint & generator execution loop.
  * `src/blueprint_generator/utils/`: Modular helpers for models, prompts, image processing, reviewer API routing, and dynamic YAML character/scene lookups.

---

### B. Scene Script Generator (`scriptgen` / `scene-script`)

Expands an abridged story scene from the `story:` section of `movie.yml` into detailed segment design files written per scene segment (e.g., `out/scripts/frisby_visits_mr_ages_part0.md`). Generation runs through OpenRouter's chat completions API.

* **CLI Commands**:
  ```bash
  # List the story scenes available for --name
  uv run scriptgen

  # Expand a story scene into segment prompt documents (writes part 0, 1, and 2)
  uv run scriptgen --name frisby_visits_mr_ages
  ```

* **Key Options**:
  * `--name NAME`: Story scene name from the `story:` section of `movie.yml` (written to `out/scripts/<name>_part0.md`, etc.). Omit to list all available story scenes.
  * `--model MODEL`: OpenRouter model slug used to expand the scene (default: `qwen/qwen3.8-max`). The shortcut `gemini` maps to `google/gemini-3.6-flash` on OpenRouter. Requires `OPENROUTER_API_KEY`.
  * `-v` / `--verbose`: Stream the LLM output from OpenRouter (reasoning/thinking plus final content) as it is generated.
  * `--output PATH`: Custom output file or directory base path.
  * `--force`: Overwrite existing scripts if they already exist.

* **Sequential Per-Part Generation**: the three 10-second segments are generated one at a time in order. Part 0 also establishes the shared sections (title, logline, characters, setting & light). Each later part is prompted with the previous segment's saved content embedded as a `<REFERENCE>` block so blocking, composition, and lighting continue seamlessly. Reasoning effort for the default model is set to `medium` to limit excessive "thinking" time.

* **Length Validation & Retry**: each saved segment file (static template + segment body) must stay at or below 6000 characters. If any part is over the limit, `scriptgen` re-runs that part's prompt with a reduction instruction (embedding the previous generation and the exact number of characters to cut) up to 3 times before writing.

* **Output Document Structure** (`out/scripts/<name>_part<N>.md`):
  * Pre-formatted segment video prompts containing style summary, camera rules, depth & staging mandates, characters, logline, shared setting & light, and the segment's moment-by-moment shooting plan.

---

### C. Animator (`animator` / `src/animator.py`)

Generates animated 720p 24fps video clips for each segment prompt in `out/scripts/<scene>_part<N>.md` using a pluggable video provider — Google Gemini Omni Flash (`gemini-omni-flash-preview`) by default, or OpenRouter's async videos API with MiniMax H3 (`minimax/hailuo-3`) at 768p — maintaining frame-0 visual continuity between segments, and combining them into a full video with crossfade transitions.

* **CLI Commands**:
  ```bash
  # Generate all missing segment clips and combine into full.mp4 (Gemini)
  uv run animator --scene frisby_meets_greatowl

  # Generate using the OpenRouter provider (MiniMax H3 at 768p)
  uv run animator --scene frisby_meets_greatowl --provider openrouter

  # Generate using the MiniMax API directly (MiniMax H3 at 768P)
  uv run animator --scene frisby_meets_greatowl --provider minimax

  # Generate only segment 2 (0:20-0:30)
  uv run animator --scene frisby_meets_greatowl --parts 2

  # Force regeneration of segment 1
  uv run animator --scene frisby_meets_greatowl --parts 1 --force

  # Re-combine existing part clips without making API calls
  uv run animator --scene frisby_meets_greatowl --compose-only
  ```

* **Key Options**:
  * `--scene NAME`: Scene script name (reads `out/scripts/<scene>_part<N>.md`).
  * `--parts N`: Generate only segment index `N` (0-indexed). Default: generate all missing segments.
  * `--force`: Regenerate parts even if clip already exists.
  * `--compose-only`: Skip API calls and combine existing `part-*.mp4` clips into `full.mp4`.
  * `--provider NAME`: Video generation provider (`google`, `openrouter` or `minimax`; `gemini` is an alias for `google`). Default: `google` (Gemini Omni Flash). The `openrouter` provider uses `OPENROUTER_API_KEY` and defaults to `minimax/hailuo-3` at `768p`. The `minimax` provider uses `MINIMAX_API_KEY` and defaults to `MiniMax-H3` at `768P`.
  * `--video-model MODEL`: Video generation model ID (default: `gemini-omni-flash-preview` for `google`; OpenRouter e.g. `minimax/hailuo-3`; MiniMax e.g. `MiniMax-H3`).
  * `--duration SECONDS`: Duration per segment (default: 10).
  * `--timeout SECONDS`: Polling timeout per video request (default: 600).
  * `--scripts-dir DIR`: Directory containing scene scripts (default: `out/scripts`).
  * `--blueprint-dir DIR`: Directory containing blueprint character reference images (default: `out/blueprint`).
  * `--output DIR`: Custom output folder (default: `out/animations/<scene>/`).

* **Workflow & Continuity Mechanics**:
  1. Reads `out/scripts/<scene>_part<N>.md` for each segment and extracts characters from the prompt.
  2. Loads latest blueprint images (`attempt-*.jpg`) from `out/blueprint/<character-slug>/` as character reference inputs. Missing blueprints are generated automatically via `generate-blueprint` (the exact command is echoed as `CREATING BLUEPRINT: ...`).
  3. For the first segment (index 0), attaches the scene location's background plate (`out/blueprint/<scene-slug>/attempt-*.jpg`, auto-generated if missing) as an environment reference so the set layout and depth layering stay anchored. The script name is mapped to a scene location via the `story:` section of `movie.yml`.
  4. For segment `N > 0`, extracts the last frame of segment `N-1` (`part-<N-1>.jpg`) via `ffmpeg` and sends it as a mandatory opening frame reference for exact visual/background continuity (no background plate is attached to these segments).
  5. Tacks reference image tags (<IMAGE_REF_N>) and continuity/opening frame instructions onto the segment prompt, saving the final tagged prompt to `out/animations/<scene>/part-<N>-prompt.md`.
  6. Generates `part-<N>.mp4` for each segment.
  7. Combines all parts into `out/animations/<scene>/full.mp4` with a 0.2s crossfade transition using `ffmpeg`.

* **Module Layout**:
  * `src/animator.py`: Executable CLI launcher script.
  * `src/animator/`: Package containing submodules for config (`config.py`), provider abstraction (`provider.py`), Gemini API client (`api.py`), script parsing (`script.py`), prompt building (`prompt.py`), video media & ffmpeg processing (`media.py`), and CLI orchestration (`cli.py`).

---

## 5. Automated AI Pipeline Architecture

```
[ movie.yml / movie.md ]
          │
          ▼
[ scriptgen ] ──► Generates Segment Prompts (out/scripts/<scene>_part<N>.md)
          │
          ▼
[ generate-blueprint ] ──► Generates Character & Background Blueprints (out/blueprint/...)
          │
          ▼
[ animator ] ──► Segment Video Generation (Pluggable Provider: Gemini / OpenRouter)
          │
          ├──► Segment 0 (0:00-0:10) ──► out/animations/<scene>/part-0.mp4
          │                                     │ (Extracts last frame part-0.jpg)
          ├──► Segment 1 (0:10-0:20) ◄──────────┘ (Frame-0 Continuity Reference)
          │            │
          │            ▼ ──► out/animations/<scene>/part-1.mp4
          │                     │ (Extracts last frame part-1.jpg)
          ├──► Segment 2 (0:20-0:30) ◄──────────┘ (Frame-0 Continuity Reference)
          │            │
          │            ▼ ──► out/animations/<scene>/part-2.mp4
          │
          ▼
[ ffmpeg Crossfade Pass ] ──► Combined Final Scene Video (out/animations/<scene>/full.mp4)
```
