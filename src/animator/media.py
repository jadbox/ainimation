"""Media file utilities and ffmpeg video processing for animation parts."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from animator.config import FULL_VIDEO_NAME, TRANSITION_SECONDS
from animator.models import SceneSegment

logger = logging.getLogger("animator.media")


def part_path(scene_dir: Path, segment: SceneSegment) -> Path:
    """Return the clip file path for a given segment."""
    return scene_dir / f"part-{segment.index}.mp4"


def frame_path(scene_dir: Path, segment_index: int) -> Path:
    """Return the frame image file path for a given segment index."""
    return scene_dir / f"part-{segment_index}.jpg"


def extract_last_frame(video_path: Path, destination: Path) -> bool:
    """Extract the last frame of a clip to a JPEG next to it (requires ffmpeg)."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found; cannot extract the last frame of %s.", video_path)
        return False
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-sseof",
                "-0.1",
                "-i",
                video_path.name,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                destination.name,
            ],
            cwd=video_path.parent,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        logger.warning(
            "ffmpeg failed to extract the last frame of %s:\n%s",
            video_path,
            error.stderr,
        )
        return False
    logger.info("Saved last frame: %s", destination)
    return True


def previous_frame(scene_dir: Path, segment: SceneSegment) -> Path | None:
    """Return the previous segment's last-frame image for continuity, if available.

    Falls back to extracting it from the previous segment's existing clip.
    """
    if segment.index == 0:
        return None
    previous_index = segment.index - 1
    frame = frame_path(scene_dir, previous_index)
    if frame.exists():
        logger.info("Continuity: using previous segment's last frame %s", frame)
        return frame
    previous_video = scene_dir / f"part-{previous_index}.mp4"
    if previous_video.exists():
        logger.info("Continuity: extracting last frame from existing %s ...", previous_video)
        if extract_last_frame(previous_video, frame):
            return frame
        return None
    logger.info(
        "Continuity: no part-%d.jpg or part-%d.mp4 found; generating segment %d "
        "without a continuity reference.",
        previous_index,
        previous_index,
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
        part = part_path(scene_dir, segment)
        if part.exists():
            part_files.append(part)
        else:
            logger.warning(
                "Part %d clip missing (%s); excluded from the combination.",
                segment.index,
                part,
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
