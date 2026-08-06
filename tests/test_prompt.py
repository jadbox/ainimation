"""Unit tests for animator prompt building and character tagging."""

from __future__ import annotations

import unittest
from pathlib import Path

from animator.media import end_frame_path, prompt_path, start_frame_path
from animator.models import SceneSegment
from animator.prompt import (
    add_reference_tags,
    build_direction,
    tag_character_mentions,
)
from blueprint_generator.utils.characters import CharacterSpec
from blueprint_generator.utils.prompts import build_initial_prompt
from movie_config import standardize_name


class TestPromptTagging(unittest.TestCase):
    def test_standardize_name(self) -> None:
        self.assertEqual(standardize_name("Mrs. Brisby"), "MRS BRISBY")
        self.assertEqual(standardize_name("Mr. Ages"), "MR AGES")
        self.assertEqual(standardize_name("Timothy Frisby"), "TIMOTHY FRISBY")
        self.assertEqual(standardize_name("Nicodemus"), "NICODEMUS")

    def test_tag_character_mentions(self) -> None:
        text = 'MRS BRISBY enters. MRS BRISBY: "Mr. Ages... please! It is Timothy."'
        characters = ["Mrs. Brisby", "Mr. Ages"]
        tagged = tag_character_mentions(text, characters)

        # Non-quoted mentions tagged
        self.assertIn("MRS BRISBY <IMAGE_REF_0> enters", tagged)
        self.assertIn("MRS BRISBY <IMAGE_REF_0>:", tagged)
        # Inside spoken quote, "Mr. Ages" is NOT tagged
        self.assertIn('"Mr. Ages... please! It is Timothy."', tagged)
        self.assertNotIn('Mr. Ages <IMAGE_REF_1>', tagged)

    def test_no_double_tagging(self) -> None:
        already_tagged = "MRS BRISBY <IMAGE_REF_0> enters. MR AGES <IMAGE_REF_1> is sitting."
        characters = ["Mrs. Brisby", "Mr. Ages"]
        retagged = tag_character_mentions(already_tagged, characters)
        self.assertEqual(already_tagged, retagged)

    def test_build_direction(self) -> None:
        segment = SceneSegment(
            index=0,
            span="0:00-0:10",
            body="MRS BRISBY enters on the right; MR AGES sits on the left.",
        )
        characters = ["Mrs. Brisby", "Mr. Ages"]
        direction_bg = build_direction(
            scene_name="frisby_visits_mr_ages",
            logline="Mrs Brisby visits Mr Ages.",
            setting="A cavernous barn interior.",
            segment=segment,
            characters=characters,
            duration=10,
            has_continuity=False,
            has_background_reference=True,
        )

        self.assertTrue(direction_bg.startswith("[# Background scene use references <IMAGE_REF_2>]"))
        self.assertIn("<IMAGE_REF_0>", direction_bg)
        self.assertIn("<IMAGE_REF_1>", direction_bg)
        self.assertIn("<IMAGE_REF_2>", direction_bg)  # background plate reference tag
        self.assertIn("MRS BRISBY <IMAGE_REF_0>", direction_bg)
        self.assertIn("MR AGES <IMAGE_REF_1>", direction_bg)
        self.assertIn("One unbroken continuous shot", direction_bg)

        direction_cont = build_direction(
            scene_name="frisby_visits_mr_ages",
            logline="Mrs Brisby visits Mr Ages.",
            setting="A cavernous barn interior.",
            segment=segment,
            characters=characters,
            duration=10,
            has_continuity=True,
            has_background_reference=False,
        )
        self.assertTrue(direction_cont.startswith("[# Sources <FIRST_FRAME>IMAGE_REF_2]"))

    def test_prompt_path(self) -> None:
        p = prompt_path(Path("/tmp/out"), 2)
        self.assertEqual(p, Path("/tmp/out/part-2-prompt.md"))

    def test_frame_paths(self) -> None:
        self.assertEqual(
            start_frame_path(Path("/tmp/out"), 0), Path("/tmp/out/part-0-start.jpg")
        )
        self.assertEqual(
            end_frame_path(Path("/tmp/out"), 0), Path("/tmp/out/part-0-end.jpg")
        )

    def test_add_reference_tags_closing_continuity(self) -> None:
        base = (
            "Match character designs EXACTLY to visual reference images. "
            "Do NOT use character references as initial frames.\n"
            "MRS BRISBY hurries across the floor."
        )
        tagged = add_reference_tags(
            base_prompt=base,
            characters=["Mrs. Brisby"],
            has_continuity=True,
            has_closing_continuity=True,
        )
        self.assertIn("[# Sources <FIRST_FRAME>IMAGE_REF_1]", tagged)
        self.assertIn("[# Sources <LAST_FRAME>IMAGE_REF_2]", tagged)

    def test_add_reference_tags_closing_only_drops_held_pose(self) -> None:
        tagged = add_reference_tags(
            base_prompt="MRS BRISBY hurries across the floor.",
            characters=["Mrs. Brisby"],
            has_closing_continuity=True,
        )
        self.assertIn("[# Sources <LAST_FRAME>IMAGE_REF_1]", tagged)
        self.assertIn("Begin from starting pose/composition in script.", tagged)
        self.assertNotIn("clean held final pose", tagged)

    def test_build_initial_prompt(self) -> None:
        spec = CharacterSpec(
            name="Mrs Brisby",
            species="field mouse",
            identity="a widowed field mouse",
            appearance="dusty mauve-brown fur, blue-violet eyes; wearing red hooded cape; anxious but determined posture",
            voice="soft, medium-high pitch",
            avoid="clean vector lines",
        )
        prompt = build_initial_prompt(spec)
        self.assertIn("MRS BRISBY", prompt)
        self.assertIn("stacked white catchlight highlights", prompt)
        self.assertIn("tapered dark-brown linework", prompt)


if __name__ == "__main__":
    unittest.main()
