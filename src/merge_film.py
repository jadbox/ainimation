#!/usr/bin/env python3
"""Combine existing scene ``full.mp4`` files into a film-level video."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from films import film_animations_dir
from movie_config import get_film, list_story_scenes, set_film

FILM_VIDEO_NAME = "film.mpeg"
FILM_THUMB_NAME = "film-thumb.jpg"


def run(args: argparse.Namespace) -> int:
    """Compose every available scene full video in story order."""
    animations_dir = film_animations_dir(get_film())
    animations_dir.mkdir(parents=True, exist_ok=True)
    scene_videos: list[Path] = []
    for story in list_story_scenes():
        video = animations_dir / story.name / "full.mp4"
        if video.is_file():
            scene_videos.append(video)
        else:
            print(f"Skipping {story.name}: no full.mp4")
    if not scene_videos:
        raise RuntimeError(f"No scene full.mp4 files found in {animations_dir}.")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must be installed to merge film scenes.")

    concat_file = animations_dir / "film-concat.txt"
    film_path = animations_dir / FILM_VIDEO_NAME
    thumb_path = animations_dir / FILM_THUMB_NAME
    concat_file.write_text(
        "".join(f"file '{video.as_posix()}'\n" for video in scene_videos), encoding="utf-8"
    )
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file.name,
                "-map", "0:v:0", "-map", "0:a?", "-c:v", "mpeg2video", "-q:v", "2",
                "-c:a", "mp2", "-b:a", "192k", film_path.name,
            ],
            cwd=animations_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ffmpeg could not merge scene videos:\n{error.stderr}") from error
    finally:
        concat_file.unlink(missing_ok=True)

    duration = float(subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", film_path.name,
        ],
        cwd=animations_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip())
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", f"{duration / 2:.3f}", "-i", film_path.name,
                "-frames:v", "1", "-q:v", "2", thumb_path.name,
            ],
            cwd=animations_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ffmpeg could not extract the film thumbnail:\n{error.stderr}") from error
    print(f"Wrote film video: {film_path}")
    print(f"Wrote film thumbnail: {thumb_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge existing scene full.mp4 files into film.mpeg.")
    parser.add_argument("--film", default=None, help="Film slug under films/<film>.")
    args = parser.parse_args()
    try:
        set_film(args.film)
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
