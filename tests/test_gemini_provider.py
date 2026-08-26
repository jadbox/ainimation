import base64
import unittest
from types import SimpleNamespace
from unittest import mock

from animator.providers import (
    GeminiVideoProvider,
    ReferenceImage,
    VideoRequest,
    create_video_provider,
)
from animator.providers.gemini import (
    build_gemini_input_items,
    create_video_interaction,
    extract_video_bytes,
    wait_for_completion,
)

KEY = "test-gemini-key"


def build_req(continuity=True, closing=False, duration=5):
    img = b"\xff\xd8fakejpeg"
    return VideoRequest(
        prompt="P",
        duration=duration,
        character_references=(ReferenceImage("MRS BRISBY", img),),
        background_reference=ReferenceImage("background", img),
        continuity_frame=ReferenceImage("continuity", img) if continuity else None,
        closing_frame=ReferenceImage("closing", img) if closing else None,
        resolution="720p",
        aspect_ratio="16:9",
    )


class TestGeminiProvider(unittest.TestCase):
    def test_build_gemini_input_items_full(self):
        req = build_req(continuity=True, closing=True)
        items = build_gemini_input_items(req)
        self.assertEqual(items[0], {"type": "text", "text": "P"})
        self.assertEqual(
            items[1]["text"], "Character reference image <IMAGE_REF_0>: MRS BRISBY"
        )
        self.assertEqual(items[2]["type"], "image")
        self.assertEqual(
            items[3]["text"],
            "Environment reference image <IMAGE_REF_1>: production background plate for this scene's set.",
        )
        self.assertIn("Mandatory opening frame <IMAGE_REF_2>", items[5]["text"])
        self.assertIn("Mandatory closing frame <IMAGE_REF_3>", items[7]["text"])

    def test_raises_when_no_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                GeminiVideoProvider(api_key=None)

    def test_create_video_provider_google_and_gemini(self):
        with mock.patch("animator.providers.gemini.genai.Client"):
            prov_google = create_video_provider("google", api_key=KEY)
            prov_gemini = create_video_provider("gemini", api_key=KEY)
        self.assertIsInstance(prov_google, GeminiVideoProvider)
        self.assertIsInstance(prov_gemini, GeminiVideoProvider)

    def test_extract_video_bytes_data(self):
        raw = b"RAWVIDEO"
        enc = base64.b64encode(raw).decode("ascii")
        interaction = SimpleNamespace(output_video=SimpleNamespace(data=enc, uri=None))
        self.assertEqual(extract_video_bytes(interaction), raw)

    def test_extract_video_bytes_uri(self):
        raw = b"URI_VIDEO"
        interaction = SimpleNamespace(
            output_video=SimpleNamespace(data=None, uri="https://example.com/v.mp4")
        )
        resp = mock.MagicMock(status_code=200, content=raw)
        with mock.patch("animator.providers.gemini.requests.get", return_value=resp):
            self.assertEqual(extract_video_bytes(interaction), raw)

    def test_extract_video_bytes_missing_raises(self):
        interaction = SimpleNamespace(output_video=None)
        with self.assertRaises(RuntimeError):
            extract_video_bytes(interaction)

    def test_wait_for_completion_success(self):
        client = mock.MagicMock()
        inter1 = SimpleNamespace(id="int-1", status="running")
        inter2 = SimpleNamespace(id="int-1", status="completed")
        client.interactions.get.return_value = inter2
        with mock.patch("animator.providers.gemini.time.sleep"):
            completed = wait_for_completion(client, inter1, timeout=10)
        self.assertEqual(completed.status, "completed")

    def test_wait_for_completion_failure_raises(self):
        client = mock.MagicMock()
        inter1 = SimpleNamespace(id="int-1", status="failed")
        with self.assertRaises(RuntimeError):
            wait_for_completion(client, inter1, timeout=10)

    def test_generate_flow(self):
        with mock.patch("animator.providers.gemini.genai.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_interaction = SimpleNamespace(
                id="int-123",
                status="completed",
                output_video=SimpleNamespace(
                    data=base64.b64encode(b"GEMINIVIDEO").decode("ascii"),
                    uri=None,
                ),
            )
            mock_client.interactions.create.return_value = mock_interaction
            p = GeminiVideoProvider(api_key=KEY)
            video_bytes = p.generate(build_req(), timeout=600)
            self.assertEqual(video_bytes, b"GEMINIVIDEO")

    def test_compatibility_shims(self):
        import animator.api as legacy_api
        import animator.provider as legacy_provider

        self.assertIs(legacy_api.GeminiVideoProvider, GeminiVideoProvider)
        self.assertIs(legacy_api.extract_video_bytes, extract_video_bytes)
        self.assertIs(legacy_provider.ReferenceImage, ReferenceImage)
        self.assertIs(legacy_provider.VideoRequest, VideoRequest)
        self.assertIs(legacy_provider.create_video_provider, create_video_provider)


if __name__ == "__main__":
    unittest.main(verbosity=2)
