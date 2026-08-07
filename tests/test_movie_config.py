"""Unit tests for movie.yml style-bible fields and movie_config loading."""

from __future__ import annotations

import unittest
from pathlib import Path

from films import PROJECT_ROOT
from movie_config import load_movie_config

RATS_MOVIE_YML = Path(PROJECT_ROOT) / "films" / "rats" / "movie.yml"


class TestMovieConfigStyleBible(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.movie_info, _, _, _ = load_movie_config(RATS_MOVIE_YML)

    def test_core_fields_load(self) -> None:
        self.assertEqual(self.movie_info.title, "The Rats of NIMH")
        self.assertEqual(self.movie_info.orientation, "16:9")
        self.assertTrue(self.movie_info.style)
        self.assertTrue(self.movie_info.hard_direction_rules)

    def test_style_bible_fields_load(self) -> None:
        for field in ("style", "camera_rules", "prompt_template"):
            self.assertTrue(getattr(self.movie_info, field), f"{field} should not be empty")

    def test_style_checklist_loads(self) -> None:
        checklist = self.movie_info.style_checklist
        self.assertEqual(len(checklist), 6)
        for item in checklist:
            self.assertTrue(item.category)
            self.assertTrue(item.do)
            self.assertTrue(item.don_t)

    def test_removed_verbose_fields_are_absent(self) -> None:
        for field in (
            "tone",
            "style_summary",
            "character_design",
            "animation_mechanics",
            "environments",
            "staging_and_lighting",
            "color_scripting",
            "pacing_and_cuts",
            "optical_effects",
            "cinematography",
        ):
            self.assertFalse(
                hasattr(self.movie_info, field), f"{field} should no longer exist"
            )

    def test_style_checklist_is_tuple(self) -> None:
        self.assertIsInstance(self.movie_info.style_checklist, tuple)


if __name__ == "__main__":
    unittest.main()
