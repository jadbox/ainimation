import json
import itertools
import unittest
from unittest import mock

from animator.provider import OpenRouterVideoProvider, ReferenceImage, VideoRequest


def seq():
    """Return an infinite monotonically increasing time source for mocks."""
    counter = itertools.count(1)
    return lambda: next(counter) * 1.0


class FakeResp:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.content = b""
        self.text = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


KEY = "test-key"


def build_req(closing=False):
    img = b"\xff\xd8fakejpeg"
    return VideoRequest(
        prompt="P",
        duration=10,
        character_references=(ReferenceImage("MRS BRISBY", img),),
        background_reference=ReferenceImage("background", img),
        continuity_frame=ReferenceImage("continuity", img),
        closing_frame=ReferenceImage("closing", img) if closing else None,
        resolution="768p",
        aspect_ratio="16:9",
    )


class TestOpenRouter(unittest.TestCase):
    def test_payload_shape(self):
        p = OpenRouterVideoProvider(api_key=KEY, model="minimax/hailuo-3")
        payload = p._build_payload(build_req())
        self.assertEqual(payload["model"], "minimax/hailuo-3")
        self.assertEqual(payload["resolution"], "768p")
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertEqual(payload["duration"], 10)
        self.assertEqual(len(payload["input_references"]), 2)
        self.assertTrue(payload["input_references"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(payload["frame_images"][0]["frame_type"], "first_frame")

    def test_payload_frame_images_with_closing(self):
        p = OpenRouterVideoProvider(api_key=KEY, model="minimax/hailuo-3")
        payload = p._build_payload(build_req(closing=True))
        self.assertEqual(
            [frame["frame_type"] for frame in payload["frame_images"]],
            ["first_frame", "last_frame"],
        )

    def test_generate_flow(self):
        p = OpenRouterVideoProvider(api_key=KEY, model="minimax/hailuo-3")
        submit = FakeResp({"id": "job1", "polling_url": "https://openrouter.ai/api/v1/videos/job1", "status": "pending"})
        poll = FakeResp({"status": "in_progress"})
        completed = FakeResp({"status": "completed", "unsigned_urls": ["https://cdn/x.mp4"], "usage": {"cost": 0.1}})
        dl = FakeResp({})
        dl.content = b"MP4BYTES"
        with mock.patch("animator.provider.requests.post", return_value=submit) as mp, \
             mock.patch("animator.provider.requests.get") as mg, \
             mock.patch("animator.provider.time.sleep"), \
             mock.patch("animator.provider.time.monotonic", side_effect=seq()):
            mg.side_effect = [poll, completed, dl]
            out = p.generate(build_req(), timeout=600)
        self.assertEqual(out, b"MP4BYTES")
        urls = [c.args[0] for c in mg.call_args_list]
        self.assertEqual(urls[0], "https://openrouter.ai/api/v1/videos/job1")
        self.assertEqual(urls[1], "https://openrouter.ai/api/v1/videos/job1")
        self.assertEqual(urls[2], "https://cdn/x.mp4")
        self.assertEqual(mp.call_args[1]["json"]["model"], "minimax/hailuo-3")

    def test_raises_when_no_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                OpenRouterVideoProvider(api_key=None)

    def test_failed_job_raises(self):
        p = OpenRouterVideoProvider(api_key=KEY)
        submit = FakeResp({"id": "job2", "polling_url": "https://openrouter.ai/api/v1/videos/job2", "status": "pending"})
        failed = FakeResp({"status": "failed", "error": "content policy"})
        with mock.patch("animator.provider.requests.post", return_value=submit), \
             mock.patch("animator.provider.requests.get", return_value=failed), \
             mock.patch("animator.provider.time.sleep"), \
             mock.patch("animator.provider.time.monotonic", side_effect=seq()):
            with self.assertRaises(RuntimeError) as ctx:
                p.generate(build_req(), timeout=600)
        self.assertIn("content policy", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
