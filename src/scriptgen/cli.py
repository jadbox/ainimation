"""Command-line interface for :mod:`scriptgen`."""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

from films import film_scripts_dir
from movie_config import get_film, get_movie_info, get_scene, get_story_scene, list_story_scenes, set_film
from scriptgen.api import generate_document
from scriptgen.config import (
    DEFAULT_PARTS,
    DEFAULT_MODEL,
    GEMINI_OPENROUTER_MODEL,
    MAX_PARTS,
    MAX_RETRIES,
    MAX_SCRIPT_CHARS,
    MAX_SCRIPT_PROMPT_CHARS,
    MIN_PARTS,
    resolve_openrouter_model,
)
from scriptgen.format import format_segment_base_prompt
from scriptgen.parse import (
    extract_segment_body,
    parse_characters_in_scene,
    parse_part_file,
    part_index_from_path,
    parse_section,
    parse_segments_from_document,
    part_file_path,
    slugify_name,
)
from scriptgen.prompts import (
    build_condense_prompt,
    build_critique_prompt,
    build_next_part_prompt,
    build_part0_prompt,
    build_polish_prompt,
    build_system_instruction,
    build_treatment_prompt,
    build_treatment_system_instruction,
)

logger = logging.getLogger("scriptgen")

CRITIQUE_PASS_THRESHOLD = 8

log_capture_stream = io.StringIO()
log_capture_handler = logging.StreamHandler(log_capture_stream)
log_capture_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
)


def ensure_log_capture() -> None:
    root = logging.getLogger()
    if log_capture_handler not in root.handlers:
        root.addHandler(log_capture_handler)


def get_invocation_cmd() -> str:
    """Return the full CLI command used to call scriptgen."""
    argv = list(sys.argv)
    if not argv:
        return "uv run scriptgen"
    prog = Path(argv[0]).name
    if prog in ("scriptgen", "scriptgen.py", "cli.py", "__main__.py"):
        args = argv[1:]
        if args:
            return f"uv run scriptgen {shlex.join(args)}"
        return "uv run scriptgen"
    return shlex.join(argv)


def format_script_metadata_text(cmd: str, logs: str) -> str:
    """Format metadata text file with the starting CLI command and an <OUTPUT> section."""
    cleaned_logs = logs.strip()
    return f"{cmd}\n\n<OUTPUT>\n{cleaned_logs}\n</OUTPUT>\n"


def write_script_metadata(script_path: Path, cmd: str, logs: str) -> Path:
    """Write the script's accompanying .txt metadata file."""
    txt_path = script_path.with_suffix(".txt")
    txt_path.write_text(format_script_metadata_text(cmd, logs), encoding="utf-8")
    return txt_path


def backup_part_file(scripts_dir: Path, part_file: Path, part_idx: int) -> Path | None:
    """Make a backup of an existing part file in scripts/part[N]_backup/."""
    if not part_file.exists():
        return None
    backup_dir = scripts_dir / f"part{part_idx}_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(part_file, backup_dir / part_file.name)
    txt_meta = part_file.with_suffix(".txt")
    if txt_meta.exists():
        shutil.copy2(txt_meta, backup_dir / txt_meta.name)
    logger.info("Backed up existing part %d script to: %s", part_idx, backup_dir)
    return backup_dir


def run(args: argparse.Namespace) -> int:
    ensure_log_capture()
    cmd = get_invocation_cmd()
    log_start_pos = log_capture_stream.tell()
    written_scripts: list[Path] = []

    try:
        story = get_story_scene(args.name)
        scene = get_scene(story.scene)
        scene_name = slugify_name(story.name)

        if args.output:
            out_path = Path(args.output)
            if out_path.suffix == ".md":
                base_path = out_path.with_suffix("")
            else:
                base_path = out_path / scene_name
        else:
            base_path = film_scripts_dir(get_film()) / scene_name

        base_path.parent.mkdir(parents=True, exist_ok=True)
        scripts_dir = base_path.parent

        existing = [
            idx
            for idx in range(args.parts)
            if part_file_path(base_path, idx).exists()
        ]
        if existing and args.force:
            logger.info("--force given: regenerating all %d parts from scratch.", args.parts)
            existing = []
        if existing != list(range(len(existing))):
            raise RuntimeError(
                "Existing scene segment scripts are not a contiguous run starting "
                f"at part 0 (found parts {existing}). Delete the scripts or pass "
                "--force to regenerate from scratch."
            )
        start_idx = len(existing)
        if start_idx == args.parts:
            print(
                f"All {args.parts} part script(s) already exist for {scene_name}. "
                "Pass --force to regenerate them."
            )
            return 0

        model = resolve_openrouter_model(args.model)
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if not openrouter_key:
            raise RuntimeError(
                "Set OPENROUTER_API_KEY before using an OpenRouter model."
            )

        logger.info("=== Expanding story scene %r with model=%s ===", scene_name, model)
        system_instruction = build_system_instruction(args.parts)
        header = f"<!-- Generated by scriptgen: {story.name} -->\n\n"

        treatment = _generate_treatment(
            story, scene, args.parts, system_instruction, model, openrouter_key, args.verbose
        )

        shared: tuple[str, str, list[str]] | None = None
        prev_body: str | None = None

        if start_idx > 0:
            logline, setting, characters, prev_body = parse_part_file(
                part_file_path(base_path, 0).read_text(encoding="utf-8")
            )
            shared = (logline, setting, characters or list(story.characters))
            for idx in range(1, start_idx):
                prev_body = extract_segment_body(
                    part_file_path(base_path, idx).read_text(encoding="utf-8")
                )
            logger.info(
                "Resuming: parts 0-%d already exist, generating parts %d-%d.",
                start_idx - 1, start_idx, args.parts - 1,
            )

        for idx in range(start_idx, args.parts):
            content, prev_body, shared = _generate_part(
                idx,
                story=story,
                scene=scene,
                scene_name=scene_name,
                part_count=args.parts,
                treatment=treatment,
                shared=shared,
                prev_body=prev_body,
                header=header,
                system_instruction=system_instruction,
                model=model,
                openrouter_key=openrouter_key,
                verbose=args.verbose,
            )
            part_file = part_file_path(base_path, idx)
            backup_part_file(scripts_dir, part_file, idx)
            part_file.write_text(content, encoding="utf-8")
            written_scripts.append(part_file)
            logger.info(">>> Scene segment part %d [%d chars] <<<", idx, len(content))
            print(f"Wrote scene segment script: {part_file}")

        for part_file in base_path.parent.glob(f"{base_path.name}_part*.md"):
            if part_index_from_path(part_file) >= args.parts:
                part_file.unlink()
                txt_meta = part_file.with_suffix(".txt")
                if txt_meta.exists():
                    txt_meta.unlink()
                logger.info("Removed obsolete scene segment script: %s", part_file)

        return 0
    finally:
        log_capture_stream.seek(log_start_pos)
        logs = log_capture_stream.read()
        log_capture_stream.seek(0, io.SEEK_END)
        for script_path in written_scripts:
            if script_path.exists():
                write_script_metadata(script_path, cmd, logs)


def _generate_treatment(
    story,
    scene,
    part_count: int,
    system_instruction: str,
    model: str,
    openrouter_key: str,
    verbose: bool,
) -> str:
    """Generate the whole-scene Director's Treatment that every part executes."""
    logger.info("=== Generating Director's Treatment for the full scene ===")
    treatment = generate_document(
        model,
        build_treatment_prompt(story, scene, part_count),
        build_treatment_system_instruction(part_count),
        openrouter_key,
        verbose=verbose,
    )
    if not treatment:
        raise RuntimeError("The model returned an empty Director's Treatment.")
    return treatment


def _render_part(scene_name, logline, setting, chars, span, body, header) -> str:
    return (
        header
        + format_segment_base_prompt(
            scene_name=scene_name,
            logline=logline,
            setting=setting,
            characters=chars,
            span=span,
            segment_body=body,
        )
        + "\n"
    )


def _extract_segment(idx: int, doc: str) -> tuple[str, str]:
    """Return (span, body) for the generated segment matching ``idx``."""
    for seg_idx, span, body in parse_segments_from_document(doc):
        if seg_idx == idx:
            return span, body
    for _, span, body in parse_segments_from_document(doc):
        return span, body
    return "", doc.strip()


def _generate(
    model: str,
    prompt: str,
    system_instruction: str,
    openrouter_key: str,
    verbose: bool,
) -> str:
    """Call the model and return its document, raising on empty output."""
    doc = generate_document(
        model, prompt, system_instruction, openrouter_key, verbose=verbose
    )
    if not doc:
        raise RuntimeError("The model returned an empty scene document.")
    return doc


def _critique(
    treatment: str,
    doc: str,
    model: str,
    system_instruction: str,
    openrouter_key: str,
    verbose: bool,
) -> str:
    """Score the document against the treatment; return fixes for weak axes."""
    critique = _generate(
        model,
        build_critique_prompt(treatment, doc),
        system_instruction,
        openrouter_key,
        verbose,
    )
    scores = re.search(r"SCORES:\s*([^\n]+)", critique, flags=re.IGNORECASE)
    if scores:
        logger.info("Critique scores: %s", scores.group(1).strip())
    fixes_match = re.search(r"FIXES:\s*(.*)", critique, flags=re.IGNORECASE | re.DOTALL)
    fixes = fixes_match.group(1).strip() if fixes_match else ""
    if scores:
        nums = [int(n) for n in re.findall(r"=(\d+)", scores.group(1))]
        if nums and min(nums) >= CRITIQUE_PASS_THRESHOLD:
            return ""
    return fixes


def _generate_part(
    idx: int,
    *,
    story,
    scene,
    scene_name: str,
    part_count: int,
    treatment: str,
    shared: tuple[str, str, list[str]] | None,
    prev_body: str | None,
    header: str,
    system_instruction: str,
    model: str,
    openrouter_key: str,
    verbose: bool,
) -> tuple[str, str, tuple[str, str, list[str]]]:
    """Generate one part, critiquing once and condensing until it fits.

    Returns (rendered content, segment body, shared sections). Raises
    RuntimeError if the part cannot be squeezed under MAX_SCRIPT_CHARS,
    rather than silently writing an oversized prompt the video model would
    reject after ~1,000 characters of animator instructions are prepended.
    """
    assert idx == 0 or shared is not None
    prompt = (
        build_part0_prompt(story, scene, part_count, treatment)
        if idx == 0
        else build_next_part_prompt(story, scene, idx, prev_body, *shared, treatment)
    )
    doc = _generate(model, prompt, system_instruction, openrouter_key, verbose)

    fixes = _critique(treatment, doc, model, system_instruction, openrouter_key, verbose)
    if fixes:
        logger.info("Applying critique fixes to part %d.", idx)
        doc = _generate(
            model,
            build_polish_prompt(doc, fixes),
            system_instruction,
            openrouter_key,
            verbose,
        )

    for attempt in range(MAX_RETRIES + 1):
        span, body = _extract_segment(idx, doc)
        if idx == 0:
            shared = (
                parse_section(doc, r"Logline"),
                parse_section(doc, r"Setting[^\n]*"),
                parse_characters_in_scene(doc) or story.characters,
            )
        logline, setting, chars = shared
        content = _render_part(scene_name, logline, setting, chars, span, body, header)
        if len(content) <= MAX_SCRIPT_CHARS:
            return content, body, shared
        if attempt == MAX_RETRIES:
            break
        logger.warning(
            "Part %d too long (%d chars, limit %d); condensing (%d/%d).",
            idx, len(content), MAX_SCRIPT_CHARS, attempt + 1, MAX_RETRIES,
        )
        prompt = build_condense_prompt(doc, len(content), MAX_SCRIPT_PROMPT_CHARS)
        doc = _generate(model, prompt, system_instruction, openrouter_key, verbose)

    raise RuntimeError(
        f"Part {idx} is still {len(content)} characters after {MAX_RETRIES} "
        f"condense attempts (limit {MAX_SCRIPT_CHARS}). Aborting without "
        "writing — rerun or regenerate with --force."
    )


def main() -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--film", default=None)
    pre_args, _ = pre.parse_known_args()
    try:
        set_film(pre_args.film)
    except ValueError as error:
        pre.error(str(error))

    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.name:
        print("Available story scenes in movie.yml (pass one to --name):\n")
        for spec in list_story_scenes():
            print(f"  {spec.name}")
            if spec.title:
                print(f"      {spec.title}")
            print(f"      scene: {spec.scene} | characters: {', '.join(spec.characters)}")
        return

    try:
        raise SystemExit(run(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


def _build_parser() -> argparse.ArgumentParser:
    info = get_movie_info()
    scripts_dir = film_scripts_dir(get_film())
    parser = argparse.ArgumentParser(
        description=(
            f"Expand an abridged story scene from movie.yml for {info.title} "
            "into detailed segment design files written to "
            f"{scripts_dir}/<name>_part0.md, etc. Run without --name to "
            "list the available story scenes."
        )
    )
    parser.add_argument(
        "--film",
        default=get_film(),
        help=(
            "Film slug under films/<film>/ whose movie.yml and out/ to use "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--name",
        default=None,
        help=(
            "Story scene name from the movie.yml `story:` section; segment "
            f"scripts are written to {scripts_dir}/<name>_part0.md, etc. (e.g. "
            "frisby_visits_mr_ages). Omit to list all available story scenes."
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "OpenRouter model slug used to expand the scene "
            f"(default: {DEFAULT_MODEL}). Shortcut 'gemini' maps to "
            f"{GEMINI_OPENROUTER_MODEL} on OpenRouter. Requires "
            "OPENROUTER_API_KEY."
        ),
    )
    parser.add_argument(
        "--parts",
        type=int,
        choices=range(MIN_PARTS, MAX_PARTS + 1),
        default=DEFAULT_PARTS,
        metavar="N",
        help=(
            f"Number of 10-second script parts to generate ({MIN_PARTS}-{MAX_PARTS}; "
            f"default: {DEFAULT_PARTS})."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "Stream the LLM output from OpenRouter and print it as it is "
            "generated, with a log header marking each scene part."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"Output base path or directory (default: {scripts_dir}/<name>).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Regenerate all parts from scratch, ignoring existing scripts. "
            "Without --force, existing contiguous parts are kept and generation "
            "resumes at the next missing part."
        ),
    )
    return parser
