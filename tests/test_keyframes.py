"""Unit tests for keyframes command-line script and prompt construction."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from animator.models import SceneSegment
import keyframes
from keyframes import (
    build_keyframe_prompt,
    main,
    proposal_path,
    proposal_prompt_path,
    resolve_ref_image,
    run,
)
from movie_config import set_film


class TestKeyframes(unittest.TestCase):
    def setUp(self) -> None:
        set_film("rats")

    def test_proposal_paths(self) -> None:
        scene_dir = Path("/tmp/test_scene")
        start_img = proposal_path(scene_dir, 0, "start")
        end_img = proposal_path(scene_dir, 0, "end")
        start_prompt = proposal_prompt_path(scene_dir, 1, "start")
        v1_img = proposal_path(scene_dir, 0, "start", version=1)
        v1_prompt = proposal_prompt_path(scene_dir, 0, "start", version=1)

        self.assertEqual(start_img, scene_dir / "part-0-start-proposal.jpg")
        self.assertEqual(end_img, scene_dir / "part-0-end-proposal.jpg")
        self.assertEqual(start_prompt, scene_dir / "part-1-start-proposal-prompt.txt")
        self.assertEqual(v1_img, scene_dir / "part-0-start-proposal-v1.jpg")
        self.assertEqual(v1_prompt, scene_dir / "part-0-start-proposal-v1-prompt.txt")

    def test_next_proposal_paths_versioning(self) -> None:
        from keyframes import next_proposal_paths

        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)

            # Initially, base paths are returned
            img0, prompt0 = next_proposal_paths(scene_dir, 0, "start")
            self.assertEqual(img0, scene_dir / "part-0-start-proposal.jpg")
            self.assertEqual(prompt0, scene_dir / "part-0-start-proposal-prompt.txt")

            # Create base image
            img0.write_bytes(b"base")
            img1, prompt1 = next_proposal_paths(scene_dir, 0, "start")
            self.assertEqual(img1, scene_dir / "part-0-start-proposal-v1.jpg")
            self.assertEqual(prompt1, scene_dir / "part-0-start-proposal-v1-prompt.txt")

            # Create v1 image
            img1.write_bytes(b"v1")
            img2, prompt2 = next_proposal_paths(scene_dir, 0, "start")
            self.assertEqual(img2, scene_dir / "part-0-start-proposal-v2.jpg")
            self.assertEqual(prompt2, scene_dir / "part-0-start-proposal-v2-prompt.txt")

    def test_build_keyframe_prompt_start(self) -> None:
        segment = SceneSegment(
            index=0,
            span="0:00-0:10",
            body="[0:00-0:03] MRS BRISBY enters from the dark right exterior; MR AGES sits at the spool desk.",
        )
        prompt = build_keyframe_prompt(
            scene_name="frisby_visits_mr_ages",
            segment=segment,
            keyframe_type="start",
            characters=["Mrs Brisby", "Mr Ages"],
            has_background=True,
            has_ref_prev=False,
            has_ref_after=False,
        )

        self.assertIn("KEYFRAME TARGET: START FRAME", prompt)
        self.assertIn("Time 0:00 / Opening Beat", prompt)
        self.assertIn("MRS BRISBY (<IMAGE_REF_0>)", prompt)
        self.assertIn("MR AGES (<IMAGE_REF_1>)", prompt)
        self.assertIn("<IMAGE_REF_BG>", prompt)
        self.assertNotIn("<IMAGE_REF_PREV>", prompt)
        self.assertNotIn("<IMAGE_REF_AFTER>", prompt)
        self.assertIn("MANDATES:", prompt)
        self.assertIn("1280x720", prompt)

    def test_build_keyframe_prompt_end_with_ref(self) -> None:
        segment = SceneSegment(
            index=1,
            span="0:10-0:20",
            body="[0:18-0:20] MRS BRISBY clutches her cape with trembling paws; MR AGES nods gravely.",
        )
        prompt = build_keyframe_prompt(
            scene_name="frisby_visits_mr_ages",
            segment=segment,
            keyframe_type="end",
            characters=["Mrs Brisby"],
            has_background=False,
            has_ref_prev=True,
            has_ref_after=True,
        )

        self.assertIn("KEYFRAME TARGET: END FRAME", prompt)
        self.assertIn("Final Held Pose", prompt)
        self.assertIn("<IMAGE_REF_PREV>", prompt)
        self.assertIn("<IMAGE_REF_AFTER>", prompt)
        self.assertIn("Chronological Bridge Context", prompt)
        self.assertIn("Previous Reference Frame", prompt)
        self.assertIn("After / Next Reference Frame", prompt)

    def test_resolve_ref_image_direct_and_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)
            ref_file = scene_dir / "part-0-end-proposal.jpg"
            ref_file.write_bytes(b"fake_jpeg")

            # Direct resolution
            resolved = resolve_ref_image(str(ref_file), scene_dir, "rats")
            self.assertEqual(resolved, ref_file.resolve())

            # Relative resolution in scene_dir
            resolved_rel = resolve_ref_image("part-0-end-proposal.jpg", scene_dir, "rats")
            self.assertEqual(resolved_rel, ref_file.resolve())

            # Missing file error
            with self.assertRaises(ValueError):
                resolve_ref_image("non_existent_ref.jpg", scene_dir, "rats")

    def test_run_without_ref_uses_none(self) -> None:
        with (
            patch("keyframes.generate_keyframe") as mock_gen,
            patch("keyframes.film_scripts_dir") as mock_scripts,
            patch("keyframes.film_animations_dir") as mock_anims,
            patch("keyframes.ensure_character_reference", return_value=Path("/tmp/char.jpg")),
            patch("keyframes.ensure_background_plate", return_value=None),
            patch("keyframes.find_scene_background_plate", return_value=None),
            patch("keyframes.genai.Client"),
            tempfile.TemporaryDirectory() as tmp_dir,
        ):
            scene_dir = Path(tmp_dir)
            mock_anims.return_value = scene_dir.parent
            mock_scripts.return_value = scene_dir.parent / "scripts"
            script_file = scene_dir.parent / "scripts" / "frisby_visits_mr_ages_part1.md"
            script_file.parent.mkdir(parents=True, exist_ok=True)
            script_file.write_text(
                "Characters: Mrs Brisby\n\nintegrated_multimodal_description: [Shot 1]\n[0:00-0:10] Mrs Brisby stands.",
                encoding="utf-8",
            )

            prior_end = scene_dir / "part-0-end-proposal.jpg"
            prior_end.parent.mkdir(parents=True, exist_ok=True)
            prior_end.write_bytes(b"test")

            from argparse import Namespace
            args = Namespace(
                film="rats",
                scene="frisby_visits_mr_ages",
                parts=1,
                type="start",
                ref=None,
                ref_prev=None,
                ref_after=None,
                image_model="gemini-3.1-flash-image-preview",
                output=str(scene_dir),
                scripts_dir=None,
                blueprint_dir=None,
            )
            ret = run(args)
            self.assertEqual(ret, 0)
            self.assertTrue(mock_gen.called)
            # Ensure ref_prev and ref_after passed to generate_keyframe are None
            self.assertIsNone(mock_gen.call_args.kwargs["ref_prev"])
            self.assertIsNone(mock_gen.call_args.kwargs["ref_after"])

    def test_cli_argument_parsing(self) -> None:
        with (
            patch(
                "sys.argv",
                [
                    "keyframes",
                    "--scene",
                    "frisby_visits_mr_ages",
                    "--parts",
                    "0",
                    "--both",
                    "--ref-prev",
                    "custom_prev_ref.jpg",
                    "--ref-after",
                    "custom_after_ref.jpg",
                ],
            ),
            patch("keyframes.run", return_value=0) as mock_run,
            self.assertRaises(SystemExit) as exit_ctx,
        ):
            main()

        self.assertEqual(exit_ctx.exception.code, 0)
        args = mock_run.call_args.args[0]
        self.assertEqual(args.scene, "frisby_visits_mr_ages")
        self.assertEqual(args.parts, 0)
        self.assertEqual(args.type, "both")
        self.assertEqual(args.ref_prev, "custom_prev_ref.jpg")
        self.assertEqual(args.ref_after, "custom_after_ref.jpg")
    def test_orientation_aspect_ratio(self) -> None:
        from blueprint_generator.utils.image import (
            aspect_ratio_to_dimensions,
            normalize_aspect_ratio,
        )

        self.assertEqual(normalize_aspect_ratio("16:9"), "16:9")
        self.assertEqual(normalize_aspect_ratio("landscape"), "16:9")
        self.assertEqual(normalize_aspect_ratio("portrait"), "9:16")
        self.assertEqual(normalize_aspect_ratio("9:16"), "9:16")
        self.assertEqual(normalize_aspect_ratio("1:1"), "1:1")

        self.assertEqual(aspect_ratio_to_dimensions("16:9"), (1280, 720))
        self.assertEqual(aspect_ratio_to_dimensions("9:16"), (720, 1280))
        self.assertEqual(aspect_ratio_to_dimensions("1:1"), (1024, 1024))
        self.assertEqual(aspect_ratio_to_dimensions("4:3"), (960, 720))
        self.assertEqual(aspect_ratio_to_dimensions("3:4"), (720, 960))


if __name__ == "__main__":
    unittest.main()
