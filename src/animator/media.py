"""Media file utilities and ffmpeg video processing for animation parts."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from animator.config import FULL_VIDEO_NAME, TRANSITION_SECONDS
from animator.models import SceneSegment

import re

logger = logging.getLogger("animator.media")


def part_path(
    scene_dir: Path, segment_or_index: int | SceneSegment, version: int | None = None
) -> Path:
    """Return the clip file path for a given segment and optional version."""
    index = segment_or_index.index if isinstance(segment_or_index, SceneSegment) else segment_or_index
    if version is None or version == 0:
        return scene_dir / f"part-{index}.mp4"
    return scene_dir / f"part-{index}-v{version}.mp4"


def start_frame_path(
    scene_dir: Path, segment_index: int, version: int | None = None
) -> Path:
    """Return the first-frame image file path for a given segment index and optional version."""
    if version is None or version == 0:
        return scene_dir / f"part-{segment_index}-start.jpg"
    return scene_dir / f"part-{segment_index}-v{version}-start.jpg"


def end_frame_path(
    scene_dir: Path, segment_index: int, version: int | None = None
) -> Path:
    """Return the last-frame image file path for a given segment index and optional version."""
    if version is None or version == 0:
        return scene_dir / f"part-{segment_index}-end.jpg"
    return scene_dir / f"part-{segment_index}-v{version}-end.jpg"


def prompt_path(
    scene_dir: Path, segment_index: int, version: int | None = None
) -> Path:
    """Return the prompt markdown file path for a given segment index and optional version."""
    if version is None or version == 0:
        return scene_dir / f"part-{segment_index}-prompt.md"
    return scene_dir / f"part-{segment_index}-v{version}-prompt.md"


def metadata_path(
    scene_dir: Path, segment_index: int, version: int | None = None
) -> Path:
    """Return the metadata txt file path for a given segment index and optional version."""
    if version is None or version == 0:
        return scene_dir / f"part-{segment_index}.txt"
    return scene_dir / f"part-{segment_index}-v{version}.txt"


def next_part_paths(
    scene_dir: Path, segment_index: int
) -> tuple[Path, Path, Path, Path]:
    """Return the next available output video, start frame, end frame, and prompt paths for a segment.

    If part-{N}.mp4 does not exist, returns base (v0) paths.
    If it exists, searches for the first available -v1, -v2, etc.
    """
    base_video = part_path(scene_dir, segment_index)
    base_start = start_frame_path(scene_dir, segment_index)
    base_end = end_frame_path(scene_dir, segment_index)
    base_prompt = prompt_path(scene_dir, segment_index)
    if not base_video.exists():
        return base_video, base_start, base_end, base_prompt

    version = 1
    while True:
        v_video = part_path(scene_dir, segment_index, version=version)
        v_start = start_frame_path(scene_dir, segment_index, version=version)
        v_end = end_frame_path(scene_dir, segment_index, version=version)
        v_prompt = prompt_path(scene_dir, segment_index, version=version)
        if not v_video.exists():
            return v_video, v_start, v_end, v_prompt
        version += 1


def latest_part_path(scene_dir: Path, segment_index: int) -> Path | None:
    """Return the highest version video path for a segment index, or None if none exists."""
    if not scene_dir.exists():
        return None

    pattern = re.compile(rf"^part-{segment_index}(?:-v(\d+))?\.mp4$")
    highest_version = -1
    highest_file: Path | None = None

    for item in scene_dir.iterdir():
        if not item.is_file():
            continue
        match = pattern.match(item.name)
        if match:
            ver = int(match.group(1)) if match.group(1) else 0
            if ver > highest_version:
                highest_version = ver
                highest_file = item

    return highest_file


def latest_end_frame_path(scene_dir: Path, segment_index: int) -> Path | None:
    """Return the end-frame image corresponding to the latest video version for a segment index."""
    video = latest_part_path(scene_dir, segment_index)
    if video is None:
        return None

    match = re.match(rf"^part-{segment_index}(?:-v(\d+))?\.mp4$", video.name)
    version = int(match.group(1)) if (match and match.group(1)) else 0
    frame = end_frame_path(scene_dir, segment_index, version=version)
    if frame.exists():
        return frame

    # Fallback to base end frame if versioned is missing
    base_frame = end_frame_path(scene_dir, segment_index)
    if base_frame.exists():
        return base_frame

    # Legacy frame name
    legacy_frame = scene_dir / f"part-{segment_index}.jpg"
    if legacy_frame.exists():
        return legacy_frame

    # Extract from the latest video
    if extract_last_frame(video, frame):
        return frame
    return None


def latest_start_frame_path(scene_dir: Path, segment_index: int) -> Path | None:
    """Return the start-frame image corresponding to the latest video version for a segment index."""
    video = latest_part_path(scene_dir, segment_index)
    if video is None:
        return None

    match = re.match(rf"^part-{segment_index}(?:-v(\d+))?\.mp4$", video.name)
    version = int(match.group(1)) if (match and match.group(1)) else 0
    frame = start_frame_path(scene_dir, segment_index, version=version)
    if frame.exists():
        return frame

    # Fallback to base start frame
    base_frame = start_frame_path(scene_dir, segment_index)
    if base_frame.exists():
        return base_frame

    # Extract from the latest video
    if extract_first_frame(video, frame):
        return frame
    return None


def _extract_frame(video_path: Path, destination: Path, first: bool) -> bool:
    """Extract the first (or last) frame of a clip to a JPEG (requires ffmpeg)."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found; cannot extract a frame of %s.", video_path)
        return False
    command = ["ffmpeg", "-y"]
    if not first:
        command += ["-sseof", "-0.1"]
    command += [
        "-i",
        video_path.name,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        destination.name,
    ]
    try:
        subprocess.run(
            command,
            cwd=video_path.parent,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        logger.warning(
            "ffmpeg failed to extract the %s frame of %s:\n%s",
            "first" if first else "last",
            video_path,
            error.stderr,
        )
        return False
    logger.info("Saved %s frame: %s", "first" if first else "last", destination)
    return True


def extract_first_frame(video_path: Path, destination: Path) -> bool:
    """Extract the first frame of a clip to a JPEG next to it (requires ffmpeg)."""
    return _extract_frame(video_path, destination, first=True)


def extract_last_frame(video_path: Path, destination: Path) -> bool:
    """Extract the last frame of a clip to a JPEG next to it (requires ffmpeg)."""
    return _extract_frame(video_path, destination, first=False)


def previous_frame(scene_dir: Path, segment: SceneSegment) -> Path | None:
    """Return the previous segment's last-frame image for continuity, if available."""
    if segment.index == 0:
        return None
    previous_index = segment.index - 1
    frame = latest_end_frame_path(scene_dir, previous_index)
    if frame and frame.exists():
        logger.info("Continuity: using previous segment's last frame %s", frame)
        return frame
    logger.info(
        "Continuity: no part-%d-end.jpg or part-%d.mp4 found; generating segment %d "
        "without an opening continuity reference.",
        previous_index,
        previous_index,
        segment.index,
    )
    return None


def next_frame(scene_dir: Path, segment: SceneSegment) -> Path | None:
    """Return the next segment's first-frame image for closing continuity, if available."""
    next_index = segment.index + 1
    frame = latest_start_frame_path(scene_dir, next_index)
    if frame and frame.exists():
        logger.info("Continuity: using next segment's first frame %s", frame)
        return frame
    logger.info(
        "Continuity: no part-%d-start.jpg or part-%d.mp4 found; generating segment %d "
        "without a closing continuity reference.",
        next_index,
        next_index,
        segment.index,
    )
    return None


def clip_duration(video_path: Path) -> float:
    """Return the clip's duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path.name,
        ],
        cwd=video_path.parent,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return float(result)


def build_crossfade_filter(durations: list[float]) -> tuple[str, list[str]]:
    """Build an ffmpeg xfade/acrossfade filtergraph chaining all clips.

    Every clip is assumed to carry an audio stream, so each video xfade join
    is paired with an audio acrossfade. Each join overlaps TRANSITION_SECONDS,
    so the offset of each xfade is the accumulated output length minus the
    transition. Returns the filtergraph string and the output labels to -map.
    """
    filters: list[str] = []
    accumulated = durations[0]
    previous_video = "[0:v]"
    previous_audio = "[0:a]"
    for index in range(1, len(durations)):
        offset = accumulated - TRANSITION_SECONDS
        last = index == len(durations) - 1
        video_label = "vout" if last else f"v{index}"
        audio_label = "aout" if last else f"a{index}"
        filters.append(
            f"{previous_video}[{index}:v]xfade=transition=fade:"
            f"duration={TRANSITION_SECONDS}:offset={offset:.3f}[{video_label}]"
        )
        filters.append(
            f"{previous_audio}[{index}:a]acrossfade=d={TRANSITION_SECONDS}[{audio_label}]"
        )
        previous_video = f"[{video_label}]"
        previous_audio = f"[{audio_label}]"
        accumulated = accumulated + durations[index] - TRANSITION_SECONDS
    return ";".join(filters), ["[vout]", "[aout]"]


def concat_copy(scene_dir: Path, part_files: list[Path], full_path: Path) -> None:
    """Plain stream-copy concatenation (no transitions) via the concat demuxer."""
    concat_file = scene_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{part.name}'\n" for part in part_files),
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file.name,
                "-c",
                "copy",
                full_path.name,
            ],
            cwd=scene_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        concat_file.unlink(missing_ok=True)


def combine_parts(scene_dir: Path, segments: list[SceneSegment]) -> Path | None:
    """Concatenate part clips in order into full.mp4 with 0.2s crossfades.

    full.mp4 is always (re)written so it reflects the current part clips.
    Segments whose clip is missing are excluded (with a warning). Falls back
    to plain stream-copy concatenation when the crossfade pass cannot run.
    Returns the combined file path, or None when ffmpeg is unavailable.
    """
    full_path = scene_dir / FULL_VIDEO_NAME
    if shutil.which("ffmpeg") is None:
        logger.warning(
            "ffmpeg is not installed — skipping combination. "
            "Install ffmpeg and re-run to produce %s.",
            full_path,
        )
        return None

    part_files: list[Path] = []
    for segment in segments:
        part = latest_part_path(scene_dir, segment.index)
        if part and part.exists():
            part_files.append(part)
        else:
            logger.warning(
                "Part %d clip missing; excluded from the combination.",
                segment.index,
            )
    if not part_files:
        raise RuntimeError(f"No part-*.mp4 clips found in {scene_dir} to combine.")

    logger.info(
        "Combining %d part(s) into %s with %.1fs crossfade transitions ...",
        len(part_files),
        full_path,
        TRANSITION_SECONDS,
    )
    try:
        if len(part_files) == 1:
            subprocess.run(
                ["ffmpeg", "-y", "-i", part_files[0].name, "-c", "copy", full_path.name],
                cwd=scene_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            durations = [clip_duration(part) for part in part_files]
            filtergraph, maps = build_crossfade_filter(durations)
            command = ["ffmpeg", "-y"]
            for part in part_files:
                command += ["-i", part.name]
            command += ["-filter_complex", filtergraph]
            for stream in maps:
                command += ["-map", stream]
            command += [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "18",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                full_path.name,
            ]
            subprocess.run(
                command,
                cwd=scene_dir,
                check=True,
                capture_output=True,
                text=True,
            )
    except (subprocess.CalledProcessError, ValueError) as error:
        stderr = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        logger.warning(
            "Crossfade composition failed (%s); falling back to plain "
            "concatenation without transitions.",
            stderr.strip()[:500],
        )
        try:
            concat_copy(scene_dir, part_files, full_path)
        except subprocess.CalledProcessError as fallback_error:
            raise RuntimeError(
                f"ffmpeg failed to combine the scene parts:\n{fallback_error.stderr}"
            )
    logger.info("Combined video written: %s", full_path)
    return full_path
