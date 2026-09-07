#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fal-client>=0.13,<1"]
# ///
"""Submit an ordered-reference test to FAL; run with uv run fal_test.py --help."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.request import urlopen


MODEL = "minimax/h3-max/reference-to-video"
REFERENCE_TAG = re.compile(r"<IMAGE_REF_(\d+)>")
ALIGNMENT = re.compile(
    r";\s*<IMAGE_REF_(\d+)> \(from \[Shot \d+\]\) "
    r"aligns with the [\d.]+-second mark of the target video"
)


def prepare_prompt(text: str, reference_count: int) -> str:
    """Adapt pipeline tags to FAL's one-based image labels."""
    def alignment(match: re.Match) -> str:
        if int(match[1]) < reference_count:
            return match[0]
        print(f"Omitting alignment for unsupplied <IMAGE_REF_{match[1]}>.",
              file=sys.stderr)
        return ""

    text = ALIGNMENT.sub(alignment, text)
    missing = sorted({int(i) for i in REFERENCE_TAG.findall(text)
                      if int(i) >= reference_count})
    if missing:
        raise ValueError(f"Prompt refers to missing reference indices: {missing}")
    text = REFERENCE_TAG.sub(lambda m: f"Image {int(m[1]) + 1}", text)
    if not text.strip() or len(text) > 50000:
        raise ValueError("Prompt must contain 1–50,000 characters.")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--references", type=Path, nargs="+", required=True,
                        help="Local images in exact submission order (indices 0, 1, ...).")
    parser.add_argument("--output", type=Path, required=True,
                        help="Destination MP4; metadata is saved alongside it.")
    parser.add_argument("--duration", type=int, choices=range(5, 16), default=10)
    parser.add_argument("--resolution", choices=("480P", "768P"), default="768P")
    parser.add_argument("--aspect-ratio", default="adaptive",
                        choices=("adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"))
    parser.add_argument("--timeout", type=int, default=1200,
                        help="Maximum queue wait in seconds (default: 1200).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate inputs and print the payload without network calls.")
    args = parser.parse_args()

    if not 1 <= len(args.references) <= 9:
        parser.error("Provide 1–9 reference images.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")
    paths = [path.expanduser().resolve() for path in args.references]
    for path in [args.prompt.expanduser(), *paths]:
        if not path.is_file():
            parser.error(f"File not found: {path}")
    prompt = prepare_prompt(args.prompt.expanduser().read_text(encoding="utf-8"), len(paths))
    payload = {
        "prompt": prompt,
        "reference_image_urls": [str(path) for path in paths],
        "duration": args.duration,
        "resolution": args.resolution,
        "aspect_ratio": args.aspect_ratio,
        "prompt_expansion_mode": "balanced",
    }
    print(f"Model: {MODEL}", flush=True)
    for index, path in enumerate(paths):
        print(f"Reference {index} / Image {index + 1}: {path}", flush=True)
    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        parser.error("Set FAL_KEY in the environment.")

    import fal_client

    output = args.output.expanduser().resolve()
    metadata = output.with_suffix(".json")
    partial = output.with_suffix(".mp4.part")
    for path in (output, metadata, partial):
        if path.exists():
            parser.error(f"Output already exists: {path}; choose another --output.")
    output.parent.mkdir(parents=True, exist_ok=True)

    client = fal_client.SyncClient(key=key)
    urls = []
    for index, path in enumerate(paths):
        print(f"Uploading Image {index + 1}...", flush=True)
        urls.append(client.upload_file(str(path)))
    payload["reference_image_urls"] = urls
    handle = client.submit(MODEL, arguments=payload)
    print(f"Request ID: {handle.request_id}", flush=True)
    print(f"Result URL: {handle.response_url}", flush=True)
    record = {
        "model": MODEL,
        "request_id": handle.request_id,
        "response_url": handle.response_url,
        "status_url": handle.status_url,
        "cancel_url": handle.cancel_url,
        "reference_paths": [str(path) for path in paths],
        "input": payload,
    }
    metadata.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    deadline = time.monotonic() + args.timeout
    previous_status = None
    while True:
        status = handle.status(with_logs=True)
        summary = type(status).__name__
        if isinstance(status, fal_client.Queued):
            summary += f" (position {status.position})"
        if summary != previous_status:
            print(summary, flush=True)
            previous_status = summary
        if isinstance(status, fal_client.Completed):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Queue wait timed out; request remains on FAL. Details: {metadata}")
        time.sleep(5)

    result = handle.get()
    record["result"] = result
    metadata.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    video_url = result.get("video", {}).get("url")
    if not video_url:
        raise ValueError(f"FAL returned no video URL; inspect {metadata}")
    print(f"Downloading: {video_url}", flush=True)
    with urlopen(video_url, timeout=120) as response, partial.open("wb") as target:
        shutil.copyfileobj(response, target)
    partial.replace(output)
    print(f"Saved: {output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Interrupted; any submitted request remains on FAL (see saved metadata).")
    except Exception as exc:
        sys.exit(f"Error: {exc}")
