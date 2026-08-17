"""OpenRouter text-generation client for :mod:`scriptgen`."""

from __future__ import annotations

import json
import logging

import requests

from scriptgen.config import OPENROUTER_CHAT_URL, REASONING_EFFORT

logger = logging.getLogger("scriptgen.api")


def generate_document(
    model: str,
    user_prompt: str,
    system_instruction: str,
    openrouter_key: str,
    verbose: bool = False,
) -> str:
    """Generate the scene document via OpenRouter and return its text.

    When ``verbose`` is true the request streams token deltas from OpenRouter's
    SSE endpoint, printing them to the terminal as they arrive (reasoning/
    thinking tokens are shown on stderr, final content on stdout) so the
    operator can watch the model write the scene. The accumulated text is
    returned either way.
    """
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
        # OpenRouter's SSE responses often omit a charset, which makes requests
        # fall back to latin-1 and mojibake every UTF-8 character (em dashes,
        # degree signs) in the generated script. Force UTF-8.
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