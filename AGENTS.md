# Agent Instructions for Animation Project

**CRITICAL REQUIREMENT**: Before generating, editing, or directing any artwork, storyboards, animation frames, prompt templates, compositing graphs, or pipeline scripts in this project, you **MUST** read `readme.md` in this directory.

## Core Mandates for AI Agents

1. **Read `readme.md` First**: Always consult `readme.md` for the complete pipeline overview, tooling usage, and project layout.
2. **The Tools Are Film-Agnostic**: The pipeline tools (`scriptgen`, `generate-blueprint`, `animator`, and the web console) work for any film. Never hard-code a specific film, art style, or aesthetic into tool code, prompts, UI, or documentation.
3. **All Film-Specific Direction Lives in the Film Folder**: Every style, character, lighting, camera, and narrative mandate for a given film is defined in that film's `films/<film>/movie.md` (style bible) and `films/<film>/movie.yml` (machine-readable config). When working on a specific film, read both files and strictly adhere to them. For example, the `films/rats/` folder carries the Don Bluth / *The Rats of NIMH* specifications in its `movie.md` and `movie.yml`.
4. **Execute the Selected Film's Directing Rules**: Apply the `hard_direction_rules`, camera rules, lighting mandates, and character recipes from the selected film's `movie.yml`/`movie.md` rather than any global style assumptions.
5. **Use the Standard Prompt Template & Pipeline**: Refer to `readme.md` for generation prompt structure and pipeline architecture; per-film prompt templates belong in that film's `movie.md`.
6. NEVER run animator.py or generate movies. Instead request the user to run commands to test any video generation action or test.
7. NEVER update out/scripts contents directly. This should always be written to only by scriptgen.py.
8. Assume the dev server is already loaded and running on http://127.0.0.1:4321.
