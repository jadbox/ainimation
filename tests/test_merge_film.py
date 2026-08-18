"""Unit tests for merge_film CLI script."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import merge_film
from movie_config import StorySceneSpec


class TestMergeFilm(unittest.TestCase):
    def test_run_combines_parts_and_merges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            film_dir = temp_path / "films" / "testfilm"
            anim_dir = film_dir / "out" / "animations"
            scripts_dir = film_dir / "out" / "scripts"
            scene_dir = anim_dir / "scene1"
            scene_dir.mkdir(parents=True, exist_ok=True)
            scripts_dir.mkdir(parents=True, exist_ok=True)

            # Create mock script parts
            (scripts_dir / "scene1_part0.md").write_text("<!-- comment -->\nSegment 0 text", encoding="utf-8")
            (scripts_dir / "scene1_part1.md").write_text("<!-- comment -->\nSegment 1 text", encoding="utf-8")

            # Create fake full.mp4
            (scene_dir / "full.mp4").write_bytes(b"dummy video")

            mock_story = StorySceneSpec(
                name="scene1",
                title="Scene 1",
                scene="A test scene",
                characters=(),
                emotions=(),
                actions=(),
                looks=(),
            )

            args = MagicMock()
            args.film = "testfilm"

            with (
                patch("merge_film.get_film", return_value="testfilm"),
                patch("merge_film.film_animations_dir", return_value=anim_dir),
                patch("merge_film.film_scripts_dir", return_value=scripts_dir),
                patch("merge_film.list_story_scenes", return_value=[mock_story]),
                patch("merge_film.combine_parts") as mock_combine,
                patch("shutil.which", return_value="/usr/bin/ffmpeg"),
                patch("subprocess.run") as mock_subproc,
            ):
                mock_subproc.return_value = MagicMock(stdout="10.0\n")

                ret = merge_film.run(args)
                self.assertEqual(ret, 0)
                mock_combine.assert_called_once()
                segments = mock_combine.call_args[0][1]
                self.assertEqual(len(segments), 2)
                self.assertEqual(segments[0].index, 0)
                self.assertEqual(segments[0].body, "Segment 0 text")
                self.assertEqual(segments[1].index, 1)
                self.assertEqual(segments[1].body, "Segment 1 text")


if __name__ == "__main__":
    unittest.main()
