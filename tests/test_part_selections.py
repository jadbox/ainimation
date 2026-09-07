from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from animator.media import (
    combine_parts,
    load_part_selections,
    save_part_selections,
    selected_part_path,
    selections_path,
    set_selected_part_video,
)
from animator.models import SceneSegment


class TestPartSelections(unittest.TestCase):
    def test_load_and_save_part_selections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir)
            self.assertEqual(load_part_selections(scene_dir), {})

            set_selected_part_video(scene_dir, 0, "part-0-v1.mp4")
            set_selected_part_video(scene_dir, 1, "part-1.mp4")

            selections = load_part_selections(scene_dir)
            self.assertEqual(selections, {0: "part-0-v1.mp4", 1: "part-1.mp4"})

            # Check JSON content on disk
            sel_file = selections_path(scene_dir)
            self.assertTrue(sel_file.is_file())
            raw = json.loads(sel_file.read_text(encoding="utf-8"))
            self.assertEqual(raw, {"0": "part-0-v1.mp4", "1": "part-1.mp4"})

    def test_selected_part_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir)
            # Create base and v1 files
            part0_base = scene_dir / "part-0.mp4"
            part0_v1 = scene_dir / "part-0-v1.mp4"
            part0_base.write_bytes(b"base")
            part0_v1.write_bytes(b"v1")

            # Default: no selections.json, should return latest (v1)
            self.assertEqual(selected_part_path(scene_dir, 0), part0_v1)

            # Explicitly select base version
            set_selected_part_video(scene_dir, 0, "part-0.mp4")
            self.assertEqual(selected_part_path(scene_dir, 0), part0_base)

            # If selected file is removed, falls back to latest existing
            part0_base.unlink()
            self.assertEqual(selected_part_path(scene_dir, 0), part0_v1)

            # If segment is not in selections, falls back to latest
            part1_base = scene_dir / "part-1.mp4"
            part1_base.write_bytes(b"part1")
            self.assertEqual(selected_part_path(scene_dir, 1), part1_base)

    def test_combine_parts_uses_selected_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir)
            part0_base = scene_dir / "part-0.mp4"
            part0_v1 = scene_dir / "part-0-v1.mp4"
            part1_base = scene_dir / "part-1.mp4"
            part1_v1 = scene_dir / "part-1-v1.mp4"

            part0_base.write_bytes(b"0_base")
            part0_v1.write_bytes(b"0_v1")
            part1_base.write_bytes(b"1_base")
            part1_v1.write_bytes(b"1_v1")

            # Select part 0 base and part 1 v1
            set_selected_part_video(scene_dir, 0, "part-0.mp4")
            set_selected_part_video(scene_dir, 1, "part-1-v1.mp4")

            segments = [
                SceneSegment(index=0, span="", body=""),
                SceneSegment(index=1, span="", body=""),
            ]

            with (
                patch("shutil.which", return_value="/usr/bin/ffmpeg"),
                patch("animator.media.clip_duration", return_value=5.0),
                patch("subprocess.run") as mock_subproc,
            ):
                full_path = combine_parts(scene_dir, segments)
                self.assertIsNotNone(full_path)
                mock_subproc.assert_called_once()
                cmd = mock_subproc.call_args[0][0]
                # Verify ffmpeg inputs match the selected versions
                self.assertIn("-i", cmd)
                input_indices = [i + 1 for i, val in enumerate(cmd) if val == "-i"]
                inputs = [cmd[idx] for idx in input_indices]
                self.assertEqual(inputs, ["part-0.mp4", "part-1-v1.mp4"])

    def test_animator_run_updates_selections(self) -> None:
        from animator.cli import run

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            scene_dir = temp_path / "scene"
            scripts_dir = temp_path / "scripts"
            blueprint_dir = temp_path / "blueprints"
            scene_dir.mkdir(parents=True, exist_ok=True)
            scripts_dir.mkdir(parents=True, exist_ok=True)
            blueprint_dir.mkdir(parents=True, exist_ok=True)

            script_file = scripts_dir / "scene_part0.md"
            script_file.write_text(
                "<!-- characters: Mrs Brisby -->\n"
                "## Scene segment part 0: 0:00–0:10\n"
                "Segment 0 text",
                encoding="utf-8",
            )

            mock_provider = MagicMock()
            mock_provider.generate.return_value = b"fake-video-bytes"

            args = MagicMock()
            args.film = "rats"
            args.scene = "scene"
            args.parts = 0
            args.duration = 5
            args.frame_start = None
            args.frame_end = None
            args.output = str(scene_dir)
            args.scripts_dir = str(scripts_dir)
            args.blueprint_dir = str(blueprint_dir)
            args.compose_only = False
            args.combine = False
            args.model = "minimax:MiniMax-H3"
            del args.deprecated_provider
            del args.deprecated_video_model
            args.timeout = 600

            with (
                patch("animator.cli.get_film", return_value="rats"),
                patch("animator.cli.resolve_scene_slug", return_value="barn"),
                patch("animator.cli.ensure_character_reference", return_value=temp_path / "char.jpg"),
                patch("animator.cli.ensure_background_plate", return_value=None),
                patch("animator.cli.create_video_provider", return_value=mock_provider),
                patch("animator.cli.build_video_request", return_value=MagicMock()),
                patch("animator.cli.extract_first_frame"),
                patch("animator.cli.extract_last_frame"),
                patch("animator.cli.combine_parts", return_value=None),
            ):
                ret = run(args)
                self.assertEqual(ret, 0)

            # Check that selections.json was written and Part 0 is selected to part-0.mp4
            selections = load_part_selections(scene_dir)
            self.assertEqual(selections, {0: "part-0.mp4"})

            # Run again to generate part-0-v1.mp4
            with (
                patch("animator.cli.get_film", return_value="rats"),
                patch("animator.cli.resolve_scene_slug", return_value="barn"),
                patch("animator.cli.ensure_character_reference", return_value=temp_path / "char.jpg"),
                patch("animator.cli.ensure_background_plate", return_value=None),
                patch("animator.cli.create_video_provider", return_value=mock_provider),
                patch("animator.cli.build_video_request", return_value=MagicMock()),
                patch("animator.cli.extract_first_frame"),
                patch("animator.cli.extract_last_frame"),
                patch("animator.cli.combine_parts", return_value=None),
            ):
                ret = run(args)
                self.assertEqual(ret, 0)

            # Check that selections.json was updated to the newest version (part-0-v1.mp4)
            selections = load_part_selections(scene_dir)
            self.assertEqual(selections, {0: "part-0-v1.mp4"})


if __name__ == "__main__":
    unittest.main()
