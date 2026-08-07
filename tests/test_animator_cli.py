"""Unit tests for animator command-line argument parsing."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from animator.cli import main


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


if __name__ == "__main__":
    unittest.main()
