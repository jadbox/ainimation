"""Unit tests for configurable script scene part counts."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_config import BackgroundSpec, SceneSpec, StorySceneSpec
from scriptgen.cli import _build_parser, _generate_part
from scriptgen.config import segment_span


class TestScriptgenParts(unittest.TestCase):
    def test_parser_accepts_part_count(self) -> None:
        args = _build_parser().parse_args(["--name", "example", "--parts", "5"])
        self.assertEqual(args.parts, 5)

    def test_segment_span_uses_ten_second_parts(self) -> None:
        self.assertEqual(segment_span(0), "0:00-0:10")
        self.assertEqual(segment_span(5), "0:50-1:00")

    @patch("scriptgen.cli.build_part0_prompt", return_value="part-zero prompt")
    @patch("scriptgen.cli._generate")
    def test_part_zero_receives_requested_part_count(self, generate, build_prompt) -> None:
        generate.return_value = (
            "# Title\n## Logline\nA logline.\n## Characters in Scene\nMOUSE\n"
            "## Setting & Light\nA setting.\n## Segment 0 (0:00-0:10)\nA beat."
        )
        story = StorySceneSpec(
            name="example",
            title="Example",
            scene="field",
            characters=("MOUSE",),
            emotions=(),
            actions=(),
            looks=(),
        )
        scene = SceneSpec(
            name="Field",
            slug="field",
            logline="A field.",
            backgrounds=(BackgroundSpec("main", "Field", "Day", "Calm"),),
        )

        _generate_part(
            0,
            story=story,
            scene=scene,
            scene_name="example",
            part_count=2,
            shared=None,
            prev_body=None,
            header="",
            system_instruction="",
            model="test",
            openrouter_key="test",
            verbose=False,
        )

        build_prompt.assert_called_once_with(story, scene, 2)


if __name__ == "__main__":
    unittest.main()
