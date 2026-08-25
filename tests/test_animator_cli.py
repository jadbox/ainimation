"""Unit tests for animator command-line argument parsing."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tempfile
from pathlib import Path

from animator.cli import main
from animator.media import (
    latest_part_path,
    next_part_paths,
    part_path,
    start_frame_path,
    end_frame_path,
    prompt_path,
)


class TestAnimatorCli(unittest.TestCase):
    def test_frame_override_arguments(self) -> None:
        with (
            patch(
                "sys.argv",
                [
                    "animator",
                    "--scene",
                    "test-scene",
                    "--frame_start",
                    "start.jpg",
                    "--frame_end",
                    "end.jpg",
                ],
            ),
            patch("animator.cli.run", return_value=0) as run,
            self.assertRaises(SystemExit) as exit_context,
        ):
            main()

        self.assertEqual(exit_context.exception.code, 0)
        args = run.call_args.args[0]
        self.assertEqual(args.frame_start, "start.jpg")
        self.assertEqual(args.frame_end, "end.jpg")
        self.assertEqual(args.duration, 5)

    def test_duration_cli_argument(self) -> None:
        with (
            patch(
                "sys.argv",
                [
                    "animator",
                    "--scene",
                    "test-scene",
                    "--duration",
                    "8",
                ],
            ),
            patch("animator.cli.run", return_value=0) as run,
            self.assertRaises(SystemExit) as exit_context,
        ):
            main()

        self.assertEqual(exit_context.exception.code, 0)
        args = run.call_args.args[0]
        self.assertEqual(args.duration, 8)

    def test_next_part_paths_and_latest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir)
            video, start, end, prompt = next_part_paths(scene_dir, 0)
            self.assertEqual(video.name, "part-0.mp4")
            self.assertEqual(start.name, "part-0-start.jpg")
            self.assertEqual(end.name, "part-0-end.jpg")
            self.assertEqual(prompt.name, "part-0-prompt.md")
            self.assertIsNone(latest_part_path(scene_dir, 0))

            video.write_bytes(b"v0")
            self.assertEqual(latest_part_path(scene_dir, 0), video)

            v1_video, v1_start, v1_end, v1_prompt = next_part_paths(scene_dir, 0)
            self.assertEqual(v1_video.name, "part-0-v1.mp4")
            self.assertEqual(v1_start.name, "part-0-v1-start.jpg")
            self.assertEqual(v1_end.name, "part-0-v1-end.jpg")
            self.assertEqual(v1_prompt.name, "part-0-v1-prompt.md")

            v1_video.write_bytes(b"v1")
            self.assertEqual(latest_part_path(scene_dir, 0), v1_video)

            v2_video, v2_start, v2_end, v2_prompt = next_part_paths(scene_dir, 0)
            self.assertEqual(v2_video.name, "part-0-v2.mp4")

    def test_legacy_unpostfixed_parts_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir)
            legacy_part0 = scene_dir / "part-0.mp4"
            legacy_part1 = scene_dir / "part-1.mp4"
            legacy_part0.write_bytes(b"part0")
            legacy_part1.write_bytes(b"part1")

            self.assertEqual(latest_part_path(scene_dir, 0), legacy_part0)
            self.assertEqual(latest_part_path(scene_dir, 1), legacy_part1)
            self.assertIsNone(latest_part_path(scene_dir, 2))

    def test_run_with_frame_start_includes_character_and_omits_bg_reference(self) -> None:
        import argparse
        from unittest.mock import MagicMock
        from animator.cli import run

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            scene_dir = temp_path / "animations" / "test_scene"
            scene_dir.mkdir(parents=True)
            scripts_dir = temp_path / "scripts"
            scripts_dir.mkdir(parents=True)
            blueprint_dir = temp_path / "blueprint"
            blueprint_dir.mkdir(parents=True)

            part0_file = scripts_dir / "test_scene_part0.md"
            part0_file.write_text(
                "Characters appearing: Mrs. Brisby\n\n[Shot 1] Mrs. Brisby walks.",
                encoding="utf-8",
            )

            frame_start_file = temp_path / "start_frame.jpg"
            frame_start_file.write_bytes(b"start_bytes")
            char_ref_file = blueprint_dir / "mrs_brisby.jpg"
            char_ref_file.write_bytes(b"char_bytes")
            bg_ref_file = blueprint_dir / "barn.jpg"
            bg_ref_file.write_bytes(b"bg_bytes")

            mock_provider = MagicMock()
            mock_provider.name = "minimax"
            mock_provider.generate.return_value = b"fake_mp4"

            args = argparse.Namespace(
                scene="test_scene",
                parts=0,
                duration=5,
                frame_start=str(frame_start_file),
                frame_end=None,
                output=str(scene_dir),
                scripts_dir=str(scripts_dir),
                blueprint_dir=str(blueprint_dir),
                compose_only=False,
                provider="minimax",
                video_model=None,
                timeout=600,
            )

            from movie_config import set_film
            set_film("rats")

            with (
                patch("animator.cli.get_film", return_value="rats"),
                patch("animator.cli.resolve_scene_slug", return_value="barn"),
                patch("animator.cli.ensure_character_reference", return_value=char_ref_file),
                patch("animator.cli.ensure_background_plate", return_value=bg_ref_file) as mock_ensure_bg,
                patch("animator.cli.create_video_provider", return_value=mock_provider),
                patch("animator.cli.build_video_request") as mock_build_req,
                patch("animator.cli.extract_first_frame"),
                patch("animator.cli.extract_last_frame"),
                patch("animator.cli.combine_parts", return_value=None),
            ):
                mock_build_req.return_value = MagicMock()
                ret = run(args)

            self.assertEqual(ret, 0)
            mock_ensure_bg.assert_not_called()
            mock_build_req.assert_called_once()
            call_args = mock_build_req.call_args[0]
            direction = call_args[0]
            references = call_args[1]
            continuity_frame = call_args[2]
            background_plate = call_args[3]

            self.assertEqual(references, [("Mrs Brisby", char_ref_file)])
            self.assertEqual(continuity_frame, frame_start_file)
            self.assertIsNone(background_plate)
            self.assertIn("Mrs. Brisby <IMAGE_REF_0>", direction)
            self.assertIn("<IMAGE_REF_1> (from [Shot 1]) is fully referenced", direction)
            self.assertNotIn("matches background reference", direction)

    def test_run_without_frames_includes_character_and_bg_reference(self) -> None:
        import argparse
        from unittest.mock import MagicMock
        from animator.cli import run

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            scene_dir = temp_path / "animations" / "test_scene"
            scene_dir.mkdir(parents=True)
            scripts_dir = temp_path / "scripts"
            scripts_dir.mkdir(parents=True)
            blueprint_dir = temp_path / "blueprint"
            blueprint_dir.mkdir(parents=True)

            part0_file = scripts_dir / "test_scene_part0.md"
            part0_file.write_text(
                "Characters appearing: Mrs. Brisby\n\n[Shot 1] Mrs. Brisby walks.",
                encoding="utf-8",
            )

            char_ref_file = blueprint_dir / "mrs_brisby.jpg"
            char_ref_file.write_bytes(b"char_bytes")
            bg_ref_file = blueprint_dir / "barn.jpg"
            bg_ref_file.write_bytes(b"bg_bytes")

            mock_provider = MagicMock()
            mock_provider.name = "minimax"
            mock_provider.generate.return_value = b"fake_mp4"

            args = argparse.Namespace(
                scene="test_scene",
                parts=0,
                duration=5,
                frame_start=None,
                frame_end=None,
                output=str(scene_dir),
                scripts_dir=str(scripts_dir),
                blueprint_dir=str(blueprint_dir),
                compose_only=False,
                provider="minimax",
                video_model=None,
                timeout=600,
            )

            from movie_config import set_film
            set_film("rats")

            with (
                patch("animator.cli.get_film", return_value="rats"),
                patch("animator.cli.resolve_scene_slug", return_value="barn"),
                patch("animator.cli.ensure_character_reference", return_value=char_ref_file),
                patch("animator.cli.ensure_background_plate", return_value=bg_ref_file),
                patch("animator.cli.create_video_provider", return_value=mock_provider),
                patch("animator.cli.build_video_request") as mock_build_req,
                patch("animator.cli.extract_first_frame"),
                patch("animator.cli.extract_last_frame"),
                patch("animator.cli.combine_parts", return_value=None),
            ):
                mock_build_req.return_value = MagicMock()
                ret = run(args)

            self.assertEqual(ret, 0)
            mock_build_req.assert_called_once()
            call_args = mock_build_req.call_args[0]
            direction = call_args[0]
            references = call_args[1]
            continuity_frame = call_args[2]
            background_plate = call_args[3]

            self.assertEqual(references, [("Mrs Brisby", char_ref_file)])
            self.assertIsNone(continuity_frame)
            self.assertEqual(background_plate, bg_ref_file)
            self.assertIn("<IMAGE_REF_0>", direction)
            self.assertIn("The environment set of this video matches background reference <IMAGE_REF_1> exactly.", direction)

    def test_run_does_not_auto_discover_closing_frame_when_next_part_exists(self) -> None:
        import argparse
        from unittest.mock import MagicMock
        from animator.cli import run

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            scene_dir = temp_path / "animations" / "test_scene"
            scene_dir.mkdir(parents=True)
            scripts_dir = temp_path / "scripts"
            scripts_dir.mkdir(parents=True)
            blueprint_dir = temp_path / "blueprint"
            blueprint_dir.mkdir(parents=True)

            part0_file = scripts_dir / "test_scene_part0.md"
            part0_file.write_text(
                "Characters appearing: Mrs. Brisby\n\n[Shot 1] Mrs. Brisby walks.",
                encoding="utf-8",
            )
            # Create next part start frame to simulate existing next part
            (scene_dir / "part-1-start.jpg").write_bytes(b"next_start")

            char_ref_file = blueprint_dir / "mrs_brisby.jpg"
            char_ref_file.write_bytes(b"char_bytes")
            bg_ref_file = blueprint_dir / "barn.jpg"
            bg_ref_file.write_bytes(b"bg_bytes")

            mock_provider = MagicMock()
            mock_provider.name = "minimax"
            mock_provider.generate.return_value = b"fake_mp4"

            args = argparse.Namespace(
                scene="test_scene",
                parts=0,
                duration=5,
                frame_start=None,
                frame_end=None,
                output=str(scene_dir),
                scripts_dir=str(scripts_dir),
                blueprint_dir=str(blueprint_dir),
                compose_only=False,
                provider="minimax",
                video_model=None,
                timeout=600,
            )

            from movie_config import set_film
            set_film("rats")

            with (
                patch("animator.cli.get_film", return_value="rats"),
                patch("animator.cli.resolve_scene_slug", return_value="barn"),
                patch("animator.cli.ensure_character_reference", return_value=char_ref_file),
                patch("animator.cli.ensure_background_plate", return_value=bg_ref_file),
                patch("animator.cli.create_video_provider", return_value=mock_provider),
                patch("animator.cli.build_video_request") as mock_build_req,
                patch("animator.cli.extract_first_frame"),
                patch("animator.cli.extract_last_frame"),
                patch("animator.cli.combine_parts", return_value=None),
            ):
                mock_build_req.return_value = MagicMock()
                ret = run(args)

            self.assertEqual(ret, 0)
            mock_build_req.assert_called_once()
            call_args = mock_build_req.call_args[1] if mock_build_req.call_args[1] else {}
            closing_frame = mock_build_req.call_args.kwargs.get("closing_frame")
            self.assertIsNone(closing_frame)


if __name__ == "__main__":
    unittest.main()
