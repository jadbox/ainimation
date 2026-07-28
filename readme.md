# AI Animation Art Pipeline & Production Environment

An automated AI-driven art pipeline and production suite for creating 2D animated feature film content. The codebase is story-agnostic and dynamically driven by configuration settings in `movie.yml` and narrative specifications in `movie.md`.

---

## 1. Project Overview & Capabilities

This project automates the multi-stage visual development and animation generation workflow:

1. **Character Blueprint Sheets**: Generates cohesive 16:9 character style guides (hero poses, turnarounds, detail callouts) with automated multi-turn vision LLM review loops.
2. **Scene Background Plates**: Generates clean, character-free 16:9 production background plates for cel compositing.
3. **30-Second Scene Scripts**: Expands abridged story beats from the `story:` section of `movie.yml` into structured 30-second scene design documents divided into three 10-second segments.
4. **Animated Clips (Gemini Omni Flash)**: Generates 720p 24fps video clips per segment with last-frame continuity locking, then concatenates them into full scene videos with seamless crossfade transitions.

---

## 2. Configuring Movie & Style Specifications

All movie-specific information, character rosters, scene definitions, and hard direction rules are defined externally:

* **`movie.yml`**: Machine-readable configuration located at the project root. Contains:
  * **Movie metadata**: Title, adaptation description, style description, style summary, and camera rules.
  * **Hard direction rules**: List of strict visual/lighting/animation mandates passed into system instructions.
  * **Characters**: List of characters (`name`, `species`, `identity`, `appearance`, `garment`, `staging`, `pose_mood`, `avoid`).
  * **Scenes**: List of scene locations (`name`, `slug`, `logline`, `backgrounds`).
  * **Story**: Abridged story beats (`name`, `title`, `scene`, `characters`, `emotions`, `actions`, `looks`) that `scene-script` expands into full scene design documents. `scene` references a scene location slug; `characters` reference roster names; `looks` records where the characters are looking and their facial expressions.
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
   * OpenRouter API Key (optional, for OpenRouter review models like Kimi K3):
     ```bash
     export OPENROUTER_API_KEY="your-openrouter-api-key"
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

### B. Scene Script Generator (`scene-script`)

Expands an abridged story scene from the `story:` section of `movie.yml` into a detailed 30-second scene design document split into three self-contained 10-second segments.

* **CLI Commands**:
  ```bash
  # List the story scenes available for --name
  uv run scene-script

  # Expand a story scene into a full scene design document
  uv run scene-script --name frisby_visits_mr_ages
  ```

* **Key Options**:
  * `--name NAME`: Story scene name from the `story:` section of `movie.yml` (written to `out/scripts/<name>.md`). Omit to list all available story scenes.
  * `--model MODEL`: Gemini text model ID (default: `gemini-3.6-flash`).
  * `--output PATH`: Custom output file path.
  * `--force`: Overwrite existing script if it already exists.

* **Output Document Structure** (`out/scripts/<name>.md`):
  * `## Logline`: Protagonist, want, and dramatic question.
  * `## Characters in Scene`: Character roster list matching `movie.yml`.
  * `## Setting & Light`: Shared environment, story object, primary light source, and color palette.
  * `## Segment 0 (0:00-0:10)`, `## Segment 1 (0:10-0:20)`, `## Segment 2 (0:20-0:30)`: Fully self-contained shooting plans with blocking, camera, animation, dialogue, sound/music, and step-by-step shot timing.

---

### C. Animator (`animator` / `src/animator.py`)

Generates animated 720p 24fps video clips for each segment in a scene script using Google Gemini Omni Flash (`gemini-omni-flash-preview`), maintaining frame-0 visual continuity between segments, and combining them into a full video with crossfade transitions.

* **CLI Commands**:
  ```bash
  # Generate all missing segment clips and combine into full.mp4
  uv run animator --scene frisby_meets_greatowl

  # Generate only segment 2 (0:20-0:30)
  uv run animator --scene frisby_meets_greatowl --parts 2

  # Force regeneration of segment 1
  uv run animator --scene frisby_meets_greatowl --parts 1 --force

  # Re-combine existing part clips without making API calls
  uv run animator --scene frisby_meets_greatowl --compose-only
  ```

* **Key Options**:
  * `--scene NAME`: Scene script name (reads `out/scripts/<scene>.md`).
  * `--parts N`: Generate only segment index `N` (0-indexed). Default: generate all missing segments.
  * `--force`: Regenerate parts even if clip already exists.
  * `--compose-only`: Skip API calls and combine existing `part-*.mp4` clips into `full.mp4`.
  * `--video-model MODEL`: Video generation model ID (default: `gemini-omni-flash-preview`).
  * `--duration SECONDS`: Duration per segment (default: 10).
  * `--timeout SECONDS`: Polling timeout per video request (default: 600).
  * `--scripts-dir DIR`: Directory containing scene scripts (default: `out/scripts`).
  * `--blueprint-dir DIR`: Directory containing blueprint character reference images (default: `out/blueprint`).
  * `--output DIR`: Custom output folder (default: `out/animations/<scene>/`).

* **Workflow & Continuity Mechanics**:
  1. Reads `out/scripts/<scene>.md` and extracts characters from `## Characters in Scene`.
  2. Loads latest blueprint images (`attempt-*.jpg`) from `out/blueprint/<character-slug>/` as character reference inputs. Missing blueprints are generated automatically via `generate-blueprint` (the exact command is echoed as `CREATING BLUEPRINT: ...`).
  3. For the first segment (index 0), attaches the scene location's background plate (`out/blueprint/<scene-slug>/attempt-*.jpg`, auto-generated if missing) as an environment reference so the set layout and depth layering stay anchored. The script name is mapped to a scene location via the `story:` section of `movie.yml`.
  4. For segment `N > 0`, extracts the last frame of segment `N-1` (`part-<N-1>.jpg`) via `ffmpeg` and sends it as a mandatory opening frame reference for exact visual/background continuity (no background plate is attached to these segments).
  5. Generates `part-<N>.mp4` for each segment.
  6. Combines all parts into `out/animations/<scene>/full.mp4` with a 0.2s crossfade transition using `ffmpeg`.

* **Module Layout**:
  * `src/animator.py`: Executable CLI launcher script.
  * `src/animator/`: Package containing submodules for config (`config.py`), models (`models.py`), script parsing (`script.py`), prompt building (`prompt.py`), Gemini API client (`api.py`), video media & ffmpeg processing (`media.py`), and CLI orchestration (`cli.py`).

---

## 5. Automated AI Pipeline Architecture

```
[ movie.yml / movie.md ]
          │
          ▼
[ scene-script ] ──► Generates 30s Scene Document (out/scripts/<scene>.md)
          │
          ▼
[ generate-blueprint ] ──► Generates Character & Background Blueprints (out/blueprint/...)
          │
          ▼
[ animator ] ──► Segment Video Generation (Gemini Omni Flash)
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
