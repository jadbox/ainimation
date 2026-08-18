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


if __name__ == "__main__":
    unittest.main()
