"""File path utilities and reference image resolution for keyframe proposals."""

from __future__ import annotations

from pathlib import Path

from films import film_animations_dir


def proposal_path(
    scene_dir: Path, segment_index: int, keyframe_type: str, version: int | None = None
) -> Path:
    """Return the output proposal image file path for a given segment, type, and optional version."""
    if version is None or version == 0:
        return scene_dir / f"part-{segment_index}-{keyframe_type}-proposal.jpg"
    return scene_dir / f"part-{segment_index}-{keyframe_type}-proposal-v{version}.jpg"


def proposal_prompt_path(
    scene_dir: Path, segment_index: int, keyframe_type: str, version: int | None = None
) -> Path:
    """Return the saved prompt text path for a given segment, keyframe type, and optional version."""
    if version is None or version == 0:
        return scene_dir / f"part-{segment_index}-{keyframe_type}-proposal-prompt.txt"
    return scene_dir / f"part-{segment_index}-{keyframe_type}-proposal-v{version}-prompt.txt"


def next_proposal_paths(
    scene_dir: Path, segment_index: int, keyframe_type: str
) -> tuple[Path, Path]:
    """Return the next available output proposal image and prompt file paths for a given segment and type.

    If part-{N}-{type}-proposal.jpg does not exist, uses that (v0/base).
    If it exists, uses part-{N}-{type}-proposal-v1.jpg, -v2.jpg, etc.
    """
    base_img = proposal_path(scene_dir, segment_index, keyframe_type)
    base_prompt = proposal_prompt_path(scene_dir, segment_index, keyframe_type)
    if not base_img.is_file():
        return base_img, base_prompt

    version = 1
    while True:
        v_img = proposal_path(scene_dir, segment_index, keyframe_type, version=version)
        v_prompt = proposal_prompt_path(scene_dir, segment_index, keyframe_type, version=version)
        if not v_img.is_file():
            return v_img, v_prompt
        version += 1


def resolve_ref_image(ref_arg: str, scene_dir: Path, film: str) -> Path:
    """Resolve a reference image path specified via --ref, --ref-prev, or --ref-after."""
    direct_path = Path(ref_arg)
    if direct_path.is_file():
        return direct_path.resolve()

    scene_path = scene_dir / ref_arg
    if scene_path.is_file():
        return scene_path.resolve()

    film_anim_path = film_animations_dir(film) / ref_arg
    if film_anim_path.is_file():
        return film_anim_path.resolve()

    raise ValueError(
        f"Reference image not found: {ref_arg!r}. Checked direct path ({direct_path}), "
        f"scene dir ({scene_path}), and animations dir ({film_anim_path})."
    )
