import itertools
import unittest
from unittest import mock

import fal_client

from animator.config import parse_model_spec
from animator.generator import FalVideoProvider, create_video_provider
from animator.providers.base import ReferenceImage, VideoRequest
from animator.providers.fal import (
    DEFAULT_FAL_VIDEO_MODEL,
    prepare_image_to_video_prompt,
    prepare_reference_prompt,
)

KEY = "test-fal-key"


def fake_image_bytes():
    return b"\xff\xd8fakejpegdata"


def build_req(
    continuity: bool = True,
    closing: bool = False,
    background: bool = True,
    duration: int = 5,
    prompt: str = "A scene with TIMMY <IMAGE_REF_0>.",
) -> VideoRequest:
    img = fake_image_bytes()
    return VideoRequest(
        prompt=prompt,
        duration=duration,
        character_references=(ReferenceImage("TIMMY", img),),
        background_reference=ReferenceImage("background", img) if background else None,
        continuity_frame=ReferenceImage("continuity", img) if continuity else None,
        closing_frame=ReferenceImage("closing", img) if closing else None,
        resolution="768P",
        aspect_ratio="16:9",
    )


class FakeHandle:
    def __init__(self, request_id="req-123", video_url="https://fal.media/video.mp4"):
        self.request_id = request_id
        self.response_url = f"https://fal.run/status/{request_id}"
        self.status_url = self.response_url
        self.cancel_url = f"https://fal.run/cancel/{request_id}"
        self.cancelled = False
        self._video_url = video_url
        self._status_calls = 0

    def status(self, with_logs=True):
        self._status_calls += 1
        if self._status_calls == 1:
            return fal_client.Queued(position=1)
        return fal_client.Completed(logs=[], metrics={})

    def get(self):
        return {"video": {"url": self._video_url}}

    def cancel(self):
        self.cancelled = True


class FakeResponse:
    def __init__(self, content=b"fake-mp4-data", status_code=200):
        self.content = content
        self.status_code = status_code
        self.text = "OK"


class TestFalProvider(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                FalVideoProvider(api_key=None)

    def test_factory_and_model_resolution(self):
        provider = create_video_provider("fal", api_key=KEY)
        self.assertIsInstance(provider, FalVideoProvider)
        self.assertEqual(provider.model, "minimax/h3-max/image-to-video")
        self.assertEqual(provider.resolution, "480P")
        self.assertTrue(provider.is_image_to_video)

        p2 = create_video_provider(
            "fal",
            model="fal:minimax/h3-max/reference-to-video",
            api_key=KEY,
        )
        self.assertEqual(p2.model, "minimax/h3-max/reference-to-video")
        self.assertFalse(p2.is_image_to_video)

    def test_parse_model_spec(self):
        prov, model = parse_model_spec("fal")
        self.assertEqual(prov, "fal")
        self.assertEqual(model, "minimax/h3-max/image-to-video")

        prov, model = parse_model_spec("fal:minimax/h3-max/reference-to-video")
        self.assertEqual(prov, "fal")
        self.assertEqual(model, "minimax/h3-max/reference-to-video")

    def test_prepare_reference_prompt(self):
        prompt = (
            "How the reference pictures align with the target video — "
            "<IMAGE_REF_1> (from [Shot 1]) aligns with the 0.00-second mark of the target video.\n\n"
            "TIMMY <IMAGE_REF_0> walks into the kitchen."
        )
        transformed = prepare_reference_prompt(prompt)
        self.assertIn("Image 2 (from [Shot 1])", transformed)
        self.assertIn("TIMMY Image 1", transformed)
        self.assertNotIn("<IMAGE_REF_", transformed)

    def test_prepare_image_to_video_prompt(self):
        prompt = (
            "How the reference pictures align with the target video — <IMAGE_REF_1> aligns with 0.00s mark.\n"
            "The environment set of this video matches background reference <IMAGE_REF_2> exactly.\n\n"
            "Match designs EXACTLY to reference images (<IMAGE_REF_0>); never use references as opening frames.\n\n"
            "TIMMY <IMAGE_REF_0> turns his head and speaks.\n"
        )
        cleaned = prepare_image_to_video_prompt(prompt)
        self.assertNotIn("How the reference pictures align", cleaned)
        self.assertNotIn("The environment set of this video", cleaned)
        self.assertNotIn("Match designs EXACTLY to reference images", cleaned)
        self.assertNotIn("<IMAGE_REF_", cleaned)
        self.assertEqual(cleaned, "TIMMY turns his head and speaks.")

    def test_reference_to_video_payload(self):
        provider = FalVideoProvider(
            model="minimax/h3-max/reference-to-video",
            api_key=KEY,
        )
        req = build_req(
            continuity=True,
            closing=True,
            background=True,
            duration=8,
            prompt="TIMMY <IMAGE_REF_0> runs past background <IMAGE_REF_1>.",
        )
        with mock.patch.object(
            provider,
            "_upload_image",
            side_effect=["https://fal/ref0.jpg", "https://fal/ref1.jpg", "https://fal/cont.jpg", "https://fal/close.jpg"],
        ) as mock_upload:
            payload = provider._build_payload(req)

        self.assertEqual(mock_upload.call_count, 4)
        self.assertIn("reference_image_urls", payload)
        self.assertEqual(
            payload["reference_image_urls"],
            ["https://fal/ref0.jpg", "https://fal/ref1.jpg", "https://fal/cont.jpg", "https://fal/close.jpg"],
        )
        self.assertEqual(payload["duration"], 8)
        self.assertEqual(payload["resolution"], "768P")
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertEqual(payload["prompt"], "TIMMY Image 1 runs past background Image 2.")
        self.assertNotIn("image_url", payload)
        self.assertNotIn("end_image_url", payload)

    def test_image_to_video_payload_ignores_references(self):
        provider = FalVideoProvider(
            model="minimax/h3-max/image-to-video",
            api_key=KEY,
        )
        req = build_req(
            continuity=True,
            closing=True,
            background=True,
            duration=7,
            prompt=(
                "How the reference pictures align with the target video — <IMAGE_REF_2> aligns with 0.00.\n"
                "Match designs EXACTLY to reference images (<IMAGE_REF_0>); never use references as opening frames.\n"
                "TIMMY <IMAGE_REF_0> reaches for the door handle."
            ),
        )
        with mock.patch.object(
            provider,
            "_upload_image",
            side_effect=["https://fal/start.jpg", "https://fal/end.jpg"],
        ) as mock_upload:
            payload = provider._build_payload(req)

        # Only continuity frame and closing frame should be uploaded
        self.assertEqual(mock_upload.call_count, 2)
        self.assertEqual(payload.get("image_url"), "https://fal/start.jpg")
        self.assertEqual(payload.get("end_image_url"), "https://fal/end.jpg")
        self.assertNotIn("reference_image_urls", payload)
        self.assertEqual(payload["duration"], 7)
        self.assertEqual(payload["resolution"], "768P")
        self.assertEqual(payload["prompt"], "TIMMY reaches for the door handle.")

    def test_image_to_video_payload_optional_frames(self):
        provider = FalVideoProvider(
            model="minimax/h3-max/image-to-video",
            api_key=KEY,
        )
        # Without continuity or closing frame
        req = build_req(continuity=False, closing=False, background=True)
        with mock.patch.object(provider, "_upload_image") as mock_upload:
            payload = provider._build_payload(req)

        self.assertEqual(mock_upload.call_count, 0)
        self.assertNotIn("image_url", payload)
        self.assertNotIn("end_image_url", payload)
        self.assertNotIn("reference_image_urls", payload)

    def test_generate_success(self):
        provider = FalVideoProvider(api_key=KEY)
        req = build_req(continuity=False, closing=False)
        handle = FakeHandle(video_url="https://fal.media/output.mp4")

        mock_client = mock.MagicMock()
        mock_client.upload.return_value = "https://fal/img.jpg"
        mock_client.submit.return_value = handle
        provider._client = mock_client

        with (
            mock.patch("time.sleep", return_value=None),
            mock.patch("requests.get", return_value=FakeResponse(b"rendered-mp4-data")) as mock_get,
        ):
            video_bytes = provider.generate(req, timeout=30)

        self.assertEqual(video_bytes, b"rendered-mp4-data")
        mock_client.submit.assert_called_once()
        mock_get.assert_called_once_with("https://fal.media/output.mp4", timeout=120)

    def test_generate_timeout_cancels(self):
        provider = FalVideoProvider(api_key=KEY)
        req = build_req(continuity=False, closing=False)
        handle = FakeHandle()

        # Mock status always Queued
        handle.status = lambda with_logs=True: fal_client.Queued(position=2)

        counter = itertools.count(1)
        time_fn = lambda: next(counter) * 100.0

        mock_client = mock.MagicMock()
        mock_client.upload.return_value = "https://fal/img.jpg"
        mock_client.submit.return_value = handle
        provider._client = mock_client

        with (
            mock.patch("time.monotonic", side_effect=time_fn),
            mock.patch("time.sleep", return_value=None),
        ):
            with self.assertRaises(TimeoutError):
                provider.generate(req, timeout=10)

        self.assertTrue(handle.cancelled)


if __name__ == "__main__":
    unittest.main()
