"""OpenRouter text-generation client for :mod:`scriptgen`."""

from __future__ import annotations

import json
import logging

import os
import requests

from scriptgen.config import OPENROUTER_CHAT_URL, REASONING_EFFORT

logger = logging.getLogger("scriptgen.api")


def generate_document_openrouter(
    model: str,
    user_prompt: str,
    system_instruction: str,
    openrouter_key: str,
    verbose: bool = False,
) -> str:
    """Generate the scene document via OpenRouter and return its text."""
    if not openrouter_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is required for OpenRouter models."
        )
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "reasoning": {"effort": REASONING_EFFORT},
    }

    if verbose:
        payload["stream"] = True
        response = requests.post(
            OPENROUTER_CHAT_URL, headers=headers, json=payload, stream=True, timeout=300
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error ({response.status_code}): {response.text}"
            )
        response.encoding = "utf-8"
        return _read_stream(response).strip()

    response = requests.post(
        OPENROUTER_CHAT_URL, headers=headers, json=payload, timeout=300
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter API error ({response.status_code}): {response.text}"
        )
    response.encoding = "utf-8"
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected OpenRouter response format: {data}")
    return (content or "").strip()


def generate_document_gemini(
    model: str,
    user_prompt: str,
    system_instruction: str,
    gemini_key: str,
    verbose: bool = False,
) -> str:
    """Generate the scene document directly via Google GenAI SDK with High thinking."""
    from google import genai
    from google.genai import types

    # Strip vendor prefix if provided (e.g. "google/gemini-3.8-flash" -> "gemini-3.8-flash")
    gemini_model = model.split("/")[-1] if "/" in model else model
    client = genai.Client(api_key=gemini_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH),
    )

    if verbose:
        response = client.models.generate_content_stream(
            model=gemini_model,
            contents=[user_prompt],
            config=config,
        )
        content_parts: list[str] = []
        for chunk in response:
            text = chunk.text or ""
            if text:
                content_parts.append(text)
                print(text, end="", flush=True)
        print(flush=True)
        return "".join(content_parts).strip()

    response = client.models.generate_content(
        model=gemini_model,
        contents=[user_prompt],
        config=config,
    )
    return (response.text or "").strip()


def generate_document(
    model: str,
    user_prompt: str,
    system_instruction: str,
    openrouter_key: str | None = None,
    verbose: bool = False,
) -> str:
    """Generate the scene document via OpenRouter or Google GenAI and return its text.

    When ``verbose`` is true the request streams token deltas to stdout/stderr.
    Defaults to OpenRouter if an OpenRouter key is available; falls back to
    Google GenAI SDK if GEMINI_API_KEY/GOOGLE_API_KEY is available.
    """
    opt_openrouter = openrouter_key or os.environ.get("OPENROUTER_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    # If an explicit OpenRouter key was passed or openrouter key exists and model contains "/"
    if opt_openrouter and ("/" in model or not gemini_key):
        return generate_document_openrouter(
            model=model,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            openrouter_key=opt_openrouter,
            verbose=verbose,
        )

    if gemini_key:
        return generate_document_gemini(
            model=model,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            gemini_key=gemini_key,
            verbose=verbose,
        )

    if opt_openrouter:
        return generate_document_openrouter(
            model=model,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            openrouter_key=opt_openrouter,
            verbose=verbose,
        )

    raise RuntimeError(
        "Either OPENROUTER_API_KEY or GEMINI_API_KEY (GOOGLE_API_KEY) must be set."
    )


def _read_stream(response: requests.Response) -> str:
    """Consume an SSE stream, printing deltas, and return the joined content.

    Results part of a streaming response are delivered as Server-Sent Events
    (``data: {json}`` lines); some endpoints emit bare JSON lines instead, so
    both forms are accepted. Reasoning/thinking deltas are echoed to stderr
    (with a small margin) and final content to stdout, so a long thinking phase
    is visibly active rather than appearing frozen.
    """
    content_parts: list[str] = []
    reasoning_started = False
    for raw in response.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.strip()
        if line.startswith("data:"):
            line = line[len("data:"):].strip()
        if line == "[DONE]":
            break
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue

        try:
            delta = chunk["choices"][0].get("delta") or {}
        except (KeyError, IndexError):
            continue

        reasoning = delta.get("reasoning")
        if reasoning:
            if not reasoning_started:
                reasoning_started = True
                print("\n--- model thinking ---")
            print(reasoning, end="", flush=True)

        content = delta.get("content")
        if content:
            content_parts.append(content)
            print(content, end="", flush=True)

    if reasoning_started:
        print("\n\n--- /model thinking ---\n")
    else:
        print(flush=True)
    return "".join(content_parts)