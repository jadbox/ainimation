"""Reviewer LLM integration and iteration documentation utilities."""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests
from google import genai
from google.genai import types

from blueprint_generator.utils.env import MAX_ITERATIONS
from blueprint_generator.utils.models import Attempt
from blueprint_generator.utils.prompts import build_history_context

logger = logging.getLogger("blueprint_generator.reviewer")


def parse_json_response(content: str) -> dict[str, Any]:
    """Extract and parse JSON object from LLM output string."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Reviewer did not return a JSON object.")
    payload = json.loads(content[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Reviewer response was not a JSON object.")
    return payload


def review_image_gemini(
    client: genai.Client,
    model: str,
    system_instruction: str,
    prompt: str,
    image_data: bytes,
    history: list[tuple[Attempt, bytes]] | None = None,
) -> dict[str, Any]:
    """Execute image review using Gemini models."""
    logger.info("Starting Gemini review with model=%s ...", model)
    contents: list[Any] = []
    if history:
        history_text = build_history_context(history)
        contents.append(history_text)
        for attempt, prev_img in history:
            contents.append(f"[Past Image for Iteration {attempt.number}]")
            contents.append(types.Part.from_bytes(data=prev_img, mime_type="image/jpeg"))

    contents.append(
        f"=== CURRENT ITERATION TO REVIEW ===\n"
        f"Prompt used for image generation:\n{prompt}\n\n"
        f"Please review the image below against the prompt and previous iteration history."
    )
    contents.append(types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini review returned empty response.")
    logger.info("Gemini review completed. Raw response length: %d chars", len(response.text))
    return parse_json_response(response.text)


def review_image_openrouter(
    openrouter_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    image_data: bytes,
    history: list[tuple[Attempt, bytes]] | None = None,
) -> dict[str, Any]:
    """Execute image review using OpenRouter API."""
    logger.info("Starting OpenRouter review with model=%s ...", model)
    logger.info(
        "Encoding image for OpenRouter (image size: %d bytes, %d history items)...",
        len(image_data),
        len(history) if history else 0,
    )
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
    }
    user_content: list[dict[str, Any]] = []

    if history:
        history_text = build_history_context(history)
        user_content.append({"type": "text", "text": history_text})
        for attempt, prev_img in history:
            prev_b64 = base64.b64encode(prev_img).decode("utf-8")
            user_content.append(
                {"type": "text", "text": f"[Past Image for Iteration {attempt.number}]"}
            )
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{prev_b64}"},
                }
            )

    image_b64 = base64.b64encode(image_data).decode("utf-8")
    user_content.append(
        {
            "type": "text",
            "text": (
                f"=== CURRENT ITERATION TO REVIEW ===\n"
                f"Prompt used for image generation:\n{prompt}\n\n"
                f"Please review the image below against the prompt and previous iteration history."
            ),
        }
    )
    user_content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        }
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_instruction,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    logger.info(
        "Sending OpenRouter review request (payload size: ~%d KB)...",
        len(json.dumps(payload)) // 1024,
    )
    t0 = time.monotonic()
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    elapsed = time.monotonic() - t0
    logger.info("OpenRouter responded in %.1fs with status %d", elapsed, response.status_code)
    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter API error ({response.status_code}): {response.text}")
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected OpenRouter response format: {data}")
    if not content:
        raise RuntimeError("OpenRouter review returned empty response.")
    logger.info("OpenRouter review completed. Response content length: %d chars", len(content))
    return parse_json_response(content)


def review_image(
    client: genai.Client | None,
    openrouter_key: str | None,
    model: str,
    system_instruction: str,
    prompt: str,
    image_data: bytes,
    history: list[tuple[Attempt, bytes]] | None = None,
) -> dict[str, Any]:
    """Route review request to Gemini or OpenRouter based on model name."""
    if "/" in model:
        if not openrouter_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY environment variable is required for OpenRouter models."
            )
        return review_image_openrouter(
            openrouter_key, model, system_instruction, prompt, image_data, history
        )
    else:
        if not client:
            raise RuntimeError("Gemini client is required for Gemini models.")
        return review_image_gemini(
            client, model, system_instruction, prompt, image_data, history
        )


def write_iterations(
    destination: Path, subject_name: str, attempts: list[Attempt], accepted: bool
) -> None:
    """Write iterations.md documentation detailing each review attempt."""
    result = (
        "accepted"
        if accepted
        else f"not accepted within the {MAX_ITERATIONS}-iteration limit"
    )
    lines = [
        f"# {subject_name} Generation Iterations",
        "",
        f"- Iterations run: {len(attempts)}",
        f"- Final result: {result}",
        "",
    ]
    for attempt in attempts:
        verdict = "accepted" if attempt.accepted else "rejected"
        score = str(attempt.score) if attempt.score is not None else "not supplied"
        lines.extend(
            [
                f"## Iteration {attempt.number} ({verdict})",
                f"- Reviewer score: {score}/100",
                f"- Learned: {attempt.learning}",
                f"- Feedback: {attempt.feedback}",
                f"- Prompt change: {attempt.prompt_change}",
                "",
                "### Prompt Used for Image Generation",
                "```",
                attempt.prompt_used,
                "```",
                "",
            ]
        )
    destination.write_text("\n".join(lines), encoding="utf-8")
