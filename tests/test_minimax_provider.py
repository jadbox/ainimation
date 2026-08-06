import json
import itertools
import unittest
from unittest import mock

from animator.provider import MiniMaxVideoProvider, ReferenceImage, VideoRequest


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


def build_req(continuity=True, closing=False):
    img = b"\xff\xd8fakejpeg"
    return VideoRequest(
        prompt="P",
        duration=10,
        character_references=(ReferenceImage("MRS BRISBY", img),),
        background_reference=ReferenceImage("background", img),
        continuity_frame=ReferenceImage("continuity", img) if continuity else None,
        closing_frame=ReferenceImage("closing", img) if closing else None,
        resolution="768P",
        aspect_ratio="16:9",
    )


class TestMiniMax(unittest.TestCase):
    def test_payload_first_frame_mode(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        payload = p._build_payload(build_req(continuity=True))
        self.assertEqual(payload["model"], "MiniMax-H3")
        self.assertEqual(payload["resolution"], "768P")
        self.assertEqual(payload["ratio"], "16:9")
        self.assertEqual(payload["duration"], 10)
        types = [c["type"] for c in payload["content"]]
        self.assertEqual(types, ["text", "image_url"])
        self.assertEqual(payload["content"][1]["role"], "first_frame")

    def test_payload_reference_mode_without_continuity(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        payload = p._build_payload(build_req(continuity=False))
        roles = [c.get("role") for c in payload["content"] if c["type"] == "image_url"]
        self.assertEqual(
            roles, ["reference_image", "reference_image"]
        )
        for item in payload["content"]:
            if item["type"] == "image_url":
                self.assertTrue(item["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_payload_last_frame_only_mode(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        payload = p._build_payload(build_req(continuity=False, closing=True))
        roles = [c.get("role") for c in payload["content"] if c["type"] == "image_url"]
        self.assertEqual(roles, ["last_frame"])

    def test_payload_first_and_last_frame_mode(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        payload = p._build_payload(build_req(continuity=True, closing=True))
        roles = [c.get("role") for c in payload["content"] if c["type"] == "image_url"]
        self.assertEqual(roles, ["first_frame", "last_frame"])

    def test_generate_flow(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        submit = FakeResp({"task_id": "job1"})
        polling = FakeResp({"task": {"status": "in_progress"}})
        succeeded = FakeResp({"task": {"status": "succeeded", "content": {"url": "https://cdn/x.mp4"}}})
        dl = FakeResp({})
        dl.content = b"MP4BYTES"
        with mock.patch("animator.provider.requests.post", return_value=submit) as mp, \
             mock.patch("animator.provider.requests.get") as mg, \
             mock.patch("animator.provider.time.sleep"), \
             mock.patch("animator.provider.time.monotonic", side_effect=seq()):
            mg.side_effect = [polling, succeeded, dl]
            out = p.generate(build_req(), timeout=600)
        self.assertEqual(out, b"MP4BYTES")
        urls = [c.args[0] for c in mg.call_args_list]
        self.assertEqual(urls[0], "https://api.minimax.io/v2/query/video_generation/job1")
        self.assertEqual(urls[1], "https://api.minimax.io/v2/query/video_generation/job1")
        self.assertEqual(urls[2], "https://cdn/x.mp4")
        submitted = json.loads(mp.call_args[1]["json"]) if isinstance(
            mp.call_args[1]["json"], str
        ) else mp.call_args[1]["json"]
        self.assertEqual(submitted["model"], "MiniMax-H3")

    def test_raises_when_no_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                MiniMaxVideoProvider(api_key=None)

    def test_failed_job_raises(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        submit = FakeResp({"task_id": "job2"})
        failed = FakeResp({"task": {"status": "failed", "error": "content policy"}})
        with mock.patch("animator.provider.requests.post", return_value=submit), \
             mock.patch("animator.provider.requests.get", return_value=failed), \
             mock.patch("animator.provider.time.sleep"), \
             mock.patch("animator.provider.time.monotonic", side_effect=seq()):
            with self.assertRaises(RuntimeError) as ctx:
                p.generate(build_req(), timeout=600)
        self.assertIn("content policy", str(ctx.exception))

    def test_unknown_provider_defaults(self):
        from animator.provider import create_video_provider
        with mock.patch.dict("os.environ", {"MINIMAX_API_KEY": KEY}, clear=True):
            prov = create_video_provider("minimax")
        self.assertIsInstance(prov, MiniMaxVideoProvider)

    def test_cancel_sends_delete(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        ok = FakeResp({"task_id": "jobX", "action": "cancelled", "status": "cancelled"})
        with mock.patch("animator.provider.requests.delete", return_value=ok) as md:
            p.cancel("jobX", reason="test")
        url = md.call_args[0][0]
        self.assertEqual(
            url, "https://api.minimax.io/v2/video_generation/jobX"
        )
        self.assertEqual(md.call_args[1]["headers"]["Authorization"], "Bearer test-key")

    def test_cancel_ignores_http_error(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        err = FakeResp({"error": "nope"}, status=400)
        with mock.patch("animator.provider.requests.delete", return_value=err):
            p.cancel("jobY", reason="test")  # should not raise

    def test_cancel_active_tasks_on_signal(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        p._active_tasks.update({"job1", "job2"})
        ok = FakeResp({"task_id": "job1", "action": "cancelled", "status": "cancelled"})
        with mock.patch("animator.provider.requests.delete", return_value=ok) as md:
            p._cancel_active_tasks()
        ids = {c.args[0].rsplit("/", 1)[-1] for c in md.call_args_list}
        self.assertEqual(ids, {"job1", "job2"})
        self.assertEqual(len(md.call_args_list), 2)
        self.assertEqual(p._active_tasks, set())

    def test_generate_registers_active_task_then_clears(self):
        p = MiniMaxVideoProvider(api_key=KEY)
        submit = FakeResp({"task_id": "job-clear"})
        succeeded = FakeResp(
            {"task": {"status": "succeeded", "content": {"url": "https://cdn/x.mp4"}}}
        )
        dl = FakeResp({})
        dl.content = b"MP4BYTES"
        with mock.patch("animator.provider.requests.post", return_value=submit), \
             mock.patch("animator.provider.requests.get", side_effect=[succeeded, dl]), \
             mock.patch("animator.provider.time.sleep"), \
             mock.patch("animator.provider.time.monotonic", side_effect=seq()):
            out = p.generate(build_req(), timeout=600)
        self.assertEqual(out, b"MP4BYTES")
        self.assertEqual(p._active_tasks, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
