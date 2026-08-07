"""Unit tests for configurable script scene part counts."""

from __future__ import annotations

import unittest

from scriptgen.cli import _build_parser
from scriptgen.config import segment_span


class TestScriptgenParts(unittest.TestCase):
    def test_parser_accepts_part_count(self) -> None:
        args = _build_parser().parse_args(["--name", "example", "--parts", "5"])
        self.assertEqual(args.parts, 5)

    def test_segment_span_uses_ten_second_parts(self) -> None:
        self.assertEqual(segment_span(0), "0:00-0:10")
        self.assertEqual(segment_span(5), "0:50-1:00")


if __name__ == "__main__":
    unittest.main()
