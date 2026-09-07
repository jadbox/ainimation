"""Unit tests for blueprint generator CLI, prompt builders, and direct generation."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from blueprint_generator.utils.characters import CharacterSpec
from blueprint_generator.utils.env import DEFAULT_IMAGE_MODEL, IMAGE_MODEL_NANO_BANANA_2
from blueprint_generator.utils.models import Subject
from blueprint_generator.utils.prompts import (
    build_initial_prompt,
    build_scene_initial_prompt,
)
from blueprint_generator.utils.scenes import BackgroundSpec, SceneSpec
from blueprint import run_subject


class TestBlueprint(unittest.TestCase):
    def test_default_image_model_is_nano_banana_2(self) -> None:
        self.assertEqual(DEFAULT_IMAGE_MODEL, "gemini-3.1-flash-image-preview")
        self.assertEqual(IMAGE_MODEL_NANO_BANANA_2, "gemini-3.1-flash-image-preview")

    def test_build_initial_prompt_contains_reviewer_elements(self) -> None:
        char = CharacterSpec(
            name="Mrs Brisby",
            species="field mouse",
            identity="a widowed field mouse",
            appearance="dusty mauve-brown fur, blue-violet eyes; wearing red hooded cape",
            voice="soft",
            avoid="clean vector lines",
        )
        prompt = build_initial_prompt(char)
        # Turnaround layout
        self.assertIn("four full-body, head-to-toe views", prompt)
        self.assertIn("strict profile, back, and three-quarter", prompt)
        # Canvas background purity
        self.assertIn("slate-blue color (#4A5D6E)", prompt)
        self.assertIn("No text, labels, arrows, callouts, logos, or watermarks", prompt)
        # Reviewer criteria baked in
        self.assertIn("CHARACTER IDENTITY & ANATOMICAL INTEGRITY", prompt)
        self.assertIn("LINEWORK & RENDERING STANDARDS", prompt)
        self.assertIn("NARRATIVE CHARACTER STYLE", prompt)
        self.assertIn("2-3 stacked white highlights", prompt)

    def test_build_scene_initial_prompt_contains_reviewer_elements(self) -> None:
        scene = SceneSpec(
            name="Old Barn Field",
            slug="old-barn-field",
            logline="Mrs. Brisby makes a perilous journey across an immense overgrown field",
            backgrounds=(
                BackgroundSpec(
                    key="field-approach",
                    description="Overgrown field with towering clover and grass stalks under golden sunlight",
                ),
            ),
        )
        prompt = build_scene_initial_prompt(scene, scene.backgrounds[0])
        # Clean plate hard gate
        self.assertIn("PRODUCTION BACKGROUND PLATE MANDATE (HARD GATE)", prompt)
        self.assertIn("ABSOLUTELY NO characters, animals, creatures, people, figures, or silhouettes", prompt)
        # Environment & staging depth
        self.assertIn("ENVIRONMENT DNA & MACRO STAGING", prompt)
        self.assertIn("MEDIUM & TEXTURE", prompt)
        self.assertIn("LIGHTING, ATMOSPHERE & NARRATIVE REGISTER", prompt)
        self.assertIn("gnarled tangled roots, arched burrows, sagging beams", prompt)

    def test_run_subject_direct_generation_without_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "mrs-brisby"
            subject = Subject(
                label="character 'Mrs Brisby'",
                display_name="Mrs Brisby",
                output_dir=out_dir,
                style_slug="mrs-brisby",
                initial_prompt="Generate Mrs Brisby turnaround sheet",
            )
            args = argparse.Namespace(
                image_model="gemini-3.1-flash-image-preview",
                force=False,
                new=False,
            )

            # Mock generate_image returning mock bytes, and to_jpeg returning dummy jpeg bytes
            mock_client = MagicMock()
            with (
                patch("blueprint.generate_image", return_value=b"raw_bytes") as mock_gen,
                patch("blueprint.to_jpeg", return_value=b"fake_jpeg_bytes") as mock_to_jpeg,
            ):
                ret = run_subject(mock_client, args, subject)

            self.assertEqual(ret, 0)
            self.assertTrue(mock_gen.called)
            self.assertTrue(mock_to_jpeg.called)

            # Verify saved output files
            style_file = out_dir / "mrs-brisby-style.jpg"
            attempt_file = out_dir / "attempt-01.jpg"
            prompt_file = out_dir / "prompt.txt"
            iterations_file = out_dir / "iterations.md"

            self.assertTrue(style_file.is_file())
            self.assertTrue(attempt_file.is_file())
            self.assertTrue(prompt_file.is_file())
            self.assertTrue(iterations_file.is_file())

            self.assertEqual(style_file.read_bytes(), b"fake_jpeg_bytes")
            self.assertEqual(attempt_file.read_bytes(), b"fake_jpeg_bytes")
            self.assertIn("Generate Mrs Brisby turnaround sheet", prompt_file.read_text(encoding="utf-8"))
            self.assertIn("gemini-3.1-flash-image-preview", iterations_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
