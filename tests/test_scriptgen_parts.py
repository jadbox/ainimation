"""Unit tests for configurable script scene part counts and generation flow."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_config import BackgroundSpec, SceneSpec, StorySceneSpec
from scriptgen.cli import _build_parser, _generate_part, run
from scriptgen.config import MAX_SCRIPT_CHARS, MAX_SCRIPT_PROMPT_CHARS, segment_span


def _story() -> StorySceneSpec:
    return StorySceneSpec(
        name="example",
        title="Example",
        scene="field",
        characters=("MOUSE",),
        emotions=(),
        actions=(),
        looks=(),
    )


def _scene() -> SceneSpec:
    return SceneSpec(
        name="Field",
        slug="field",
        logline="A field.",
        backgrounds=(BackgroundSpec("main", "Field", "Day", "Calm"),),
    )


PART_ZERO_DOC = (
    "# Title\n## Logline\nA logline.\n## Characters in Scene\nMOUSE\n"
    "## Setting & Light\nA setting.\n## Segment 0 (0:00-0:10)\nA beat."
)


class TestScriptgenParts(unittest.TestCase):
    def test_parser_accepts_part_count(self) -> None:
        args = _build_parser().parse_args(["--name", "example", "--parts", "5"])
        self.assertEqual(args.parts, 5)

    def test_segment_span_uses_ten_second_parts(self) -> None:
        self.assertEqual(segment_span(0), "0:00-0:10")
        self.assertEqual(segment_span(5), "0:50-1:00")

    def test_budget_constants_reserve_video_model_headroom(self) -> None:
        self.assertEqual(MAX_SCRIPT_CHARS, 1350)
        self.assertEqual(MAX_SCRIPT_PROMPT_CHARS, 650)

    @patch("scriptgen.cli.build_part0_prompt", return_value="part-zero prompt")
    @patch("scriptgen.cli._generate")
    def test_part_zero_receives_requested_part_count_and_treatment(
        self, generate, build_prompt
    ) -> None:
        generate.return_value = PART_ZERO_DOC

        _generate_part(
            0,
            story=_story(),
            scene=_scene(),
            scene_name="example",
            part_count=2,
            treatment="## Hook\nA hook.",
            shared=None,
            prev_body=None,
            header="",
            system_instruction="",
            model="test",
            openrouter_key="test",
            verbose=False,
        )

        build_prompt.assert_called_once_with(_story(), _scene(), 2, "## Hook\nA hook.")

    @patch("scriptgen.cli._critique", return_value="")
    @patch("scriptgen.cli.build_part0_prompt", return_value="part-zero prompt")
    @patch("scriptgen.cli._generate")
    def test_oversized_part_raises_instead_of_writing(
        self, generate, build_prompt, critique
    ) -> None:
        huge_body = "x" * (MAX_SCRIPT_CHARS + 100)
        generate.return_value = (
            "# Title\n## Logline\nA logline.\n## Characters in Scene\nMOUSE\n"
            f"## Setting & Light\nA setting.\n## Segment 0 (0:00-0:10)\n{huge_body}"
        )

        with self.assertRaises(RuntimeError):
            _generate_part(
                0,
                story=_story(),
                scene=_scene(),
                scene_name="example",
                part_count=1,
                treatment="## Hook\nA hook.",
                shared=None,
                prev_body=None,
                header="",
                system_instruction="",
                model="test",
                openrouter_key="test",
                verbose=False,
            )

    @patch("scriptgen.cli.build_polish_prompt", return_value="polish prompt")
    @patch("scriptgen.cli._critique", return_value="1. Tighten the hook.")
    @patch("scriptgen.cli.build_part0_prompt", return_value="part-zero prompt")
    @patch("scriptgen.cli._generate")
    def test_critique_fixes_trigger_one_polish_rewrite(
        self, generate, build_prompt, critique, polish_prompt
    ) -> None:
        generate.return_value = PART_ZERO_DOC

        _generate_part(
            0,
            story=_story(),
            scene=_scene(),
            scene_name="example",
            part_count=1,
            treatment="## Hook\nA hook.",
            shared=None,
            prev_body=None,
            header="",
            system_instruction="",
            model="test",
            openrouter_key="test",
            verbose=False,
        )

        polish_prompt.assert_called_once()
        # First generate: part 0 prompt; second generate: polish prompt.
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(generate.call_args.args[1], "polish prompt")

    @patch("scriptgen.cli.build_polish_prompt", return_value="polish prompt")
    @patch("scriptgen.cli._critique")
    @patch("scriptgen.cli.build_part0_prompt", return_value="part-zero prompt")
    @patch("scriptgen.cli._generate")
    def test_passing_critique_skips_polish(
        self, generate, build_prompt, critique, polish_prompt
    ) -> None:
        critique.return_value = ""
        generate.return_value = PART_ZERO_DOC

        _generate_part(
            0,
            story=_story(),
            scene=_scene(),
            scene_name="example",
            part_count=1,
            treatment="## Hook\nA hook.",
            shared=None,
            prev_body=None,
            header="",
            system_instruction="",
            model="test",
            openrouter_key="test",
            verbose=False,
        )

        polish_prompt.assert_not_called()
        self.assertEqual(generate.call_count, 1)


PART_FILE_TEMPLATE = (
    'Scene: "Example" — A logline.\n'
    "Characters appearing: MOUSE.\n"
    "=== SHARED SETTING & LIGHT ===\n"
    "A setting.\n"
    "integrated_multimodal_description: part {idx} body\n"
)


class TestResumeBehavior(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.part0 = self.out / "example_part0.md"
        self.part0.write_text(PART_FILE_TEMPLATE.format(idx=0), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _args(self, parts: int) -> argparse.Namespace:
        return argparse.Namespace(
            name="example",
            output=str(self.out),
            parts=parts,
            force=False,
            model="test",
            verbose=False,
        )

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_resume_generates_only_missing_parts(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        generate_part.return_value = ("content", "body", ("l", "s", ["MOUSE"]))

        result = run(self._args(parts=2))

        self.assertEqual(result, 0)
        generate_part.assert_called_once()
        self.assertEqual(generate_part.call_args.args[0], 1)
        self.assertEqual(
            generate_part.call_args.kwargs["prev_body"],
            "integrated_multimodal_description: part 0 body",
        )
        self.assertEqual(
            generate_part.call_args.kwargs["shared"], ("A logline.", "A setting.", ["MOUSE"])
        )
        self.assertTrue((self.out / "example_part1.md").exists())

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_all_parts_present_does_nothing(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        (self.out / "example_part1.md").write_text(
            PART_FILE_TEMPLATE.format(idx=1), encoding="utf-8"
        )

        result = run(self._args(parts=2))

        self.assertEqual(result, 0)
        generate_part.assert_not_called()

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_force_regenerates_from_part_zero(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        generate_part.return_value = ("content", "body", ("l", "s", ["MOUSE"]))
        args = self._args(parts=2)
        args.force = True

        run(args)

        self.assertEqual(generate_part.call_count, 2)
        self.assertEqual(generate_part.call_args_list[0].args[0], 0)
        self.assertEqual(generate_part.call_args_list[1].args[0], 1)

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_non_contiguous_parts_raise(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        self.part0.unlink()
        (self.out / "example_part1.md").write_text(
            PART_FILE_TEMPLATE.format(idx=1), encoding="utf-8"
        )

        with self.assertRaises(RuntimeError):
            run(self._args(parts=2))

    @patch("sys.argv", ["scriptgen", "--name", "example", "--parts", "1", "--force"])
    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_metadata_file_written_for_generated_parts(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        generate_part.return_value = ("script content", "body", ("l", "s", ["MOUSE"]))
        args = self._args(parts=1)
        args.force = True

        result = run(args)

        self.assertEqual(result, 0)
        md_file = self.out / "example_part0.md"
        txt_file = self.out / "example_part0.txt"
        self.assertTrue(md_file.exists())
        self.assertTrue(txt_file.exists())
        txt_content = txt_file.read_text(encoding="utf-8")
        self.assertIn("uv run scriptgen", txt_content)
        self.assertIn("<OUTPUT>", txt_content)
        self.assertIn("</OUTPUT>", txt_content)

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_backup_created_when_overwriting_existing_parts(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        old_content = self.part0.read_text(encoding="utf-8")
        generate_part.return_value = ("new content", "body", ("l", "s", ["MOUSE"]))
        args = self._args(parts=1)
        args.force = True

        run(args)

        backup_dir = self.out / "part0_backup"
        self.assertTrue(backup_dir.exists())
        backup_file = backup_dir / "example_part0.md"
        self.assertTrue(backup_file.exists())
        self.assertEqual(backup_file.read_text(encoding="utf-8"), old_content)

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    @patch("scriptgen.cli.resolve_openrouter_model", return_value="test")
    @patch("scriptgen.cli._generate_part")
    @patch("scriptgen.cli._generate_treatment", return_value="treatment")
    @patch("scriptgen.cli.get_scene", return_value=_scene())
    @patch("scriptgen.cli.get_story_scene", return_value=_story())
    def test_existing_backup_deleted_and_recreated(
        self, story, scene, treatment, generate_part, resolve
    ) -> None:
        backup_dir = self.out / "part0_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stale_file = backup_dir / "stale.txt"
        stale_file.write_text("stale backup data", encoding="utf-8")

        generate_part.return_value = ("new content", "body", ("l", "s", ["MOUSE"]))
        args = self._args(parts=1)
        args.force = True

        run(args)

        self.assertFalse(stale_file.exists())
        self.assertTrue((backup_dir / "example_part0.md").exists())


class TestCritiqueScoring(unittest.TestCase):
    @patch("scriptgen.cli._generate")
    def test_low_scores_yield_fixes(self, generate) -> None:
        from scriptgen.cli import _critique

        generate.return_value = (
            "SCORES: hook=5, escalation=8, attention=9, dialogue=8, "
            "literalness=9, filmability=8, length=9\n"
            "FIXES:\n1. Open on the vial glow."
        )
        fixes = _critique("treatment", "doc", "m", "sys", "key", False)
        self.assertIn("Open on the vial glow", fixes)

    @patch("scriptgen.cli._generate")
    def test_all_passing_scores_yield_no_fixes(self, generate) -> None:
        from scriptgen.cli import _critique

        generate.return_value = (
            "SCORES: hook=9, escalation=8, attention=9, dialogue=9, "
            "literalness=8, filmability=9, length=9\nFIXES:\nn/a"
        )
        fixes = _critique("treatment", "doc", "m", "sys", "key", False)
        self.assertEqual(fixes, "")


if __name__ == "__main__":
    unittest.main()
