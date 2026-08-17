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
    discover_continuity_ref,
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

        self.assertEqual(start_img, scene_dir / "part-0-start-proposal.jpg")
        self.assertEqual(end_img, scene_dir / "part-0-end-proposal.jpg")
        self.assertEqual(start_prompt, scene_dir / "part-1-start-proposal-prompt.txt")

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
            has_ref_image=False,
        )

        self.assertIn("KEYFRAME TARGET: START FRAME", prompt)
        self.assertIn("Time 0:00 / Opening Beat", prompt)
        self.assertIn("MRS BRISBY (<IMAGE_REF_0>)", prompt)
        self.assertIn("MR AGES (<IMAGE_REF_1>)", prompt)
        self.assertIn("<IMAGE_REF_BG>", prompt)
        self.assertNotIn("<IMAGE_REF_PREV>", prompt)
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
            has_ref_image=True,
        )

        self.assertIn("KEYFRAME TARGET: END FRAME", prompt)
        self.assertIn("Final Held Pose", prompt)
        self.assertIn("<IMAGE_REF_PREV>", prompt)
        self.assertIn("Previous Keyframe Reference", prompt)

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

    def test_discover_continuity_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)

            # Part 0 start has no prior ref
            self.assertIsNone(discover_continuity_ref(scene_dir, 0, "start"))

            # Part 1 start discovers part-0-end-proposal.jpg
            prior_end = scene_dir / "part-0-end-proposal.jpg"
            prior_end.write_bytes(b"test")
            discovered = discover_continuity_ref(scene_dir, 1, "start")
            self.assertEqual(discovered, prior_end.resolve())

            # Part 1 end discovers part-1-start-proposal.jpg
            current_start = scene_dir / "part-1-start-proposal.jpg"
            current_start.write_bytes(b"test")
            discovered_end = discover_continuity_ref(scene_dir, 1, "end")
            self.assertEqual(discovered_end, current_start.resolve())

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
                    "--ref",
                    "custom_ref.jpg",
                    "--force",
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
