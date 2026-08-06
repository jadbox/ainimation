#!/usr/bin/env python3
"""Expand an abridged story scene from ``movie.yml`` into detailed segment design files.

Uses an OpenRouter text model (default ``qwen/qwen3.8-max``; ``--model gemini``
is a shortcut for ``google/gemini-3.6-flash``) to turn the ``story:`` section's
abridged scene beats (scene reference, characters, key emotions, important
actions/talking points, and character eyelines/expressions) into production-ready
segment prompts covering character locations, camera location, camera movement,
scene animations, sounds, and music — all held to the direction and lighting
rules in ``movie.yml``.

The scene is exported as one prompt file per segment:
``out/scripts/<name>_part0.md``, ``out/scripts/<name>_part1.md``, etc.

Usage:
    python src/scriptgen.py                         # list available story scenes
    python src/scriptgen.py --name frisby_visits_mr_ages
    python src/scriptgen.py --name ... --part 0     # write only segment 0
"""

from __future__ import annotations

from scriptgen.cli import main

if __name__ == "__main__":
    main()