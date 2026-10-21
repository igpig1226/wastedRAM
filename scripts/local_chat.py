#!/usr/bin/env python3
"""Send one prompt to a local MLX (or Ollama) OpenAI-compatible server.

No API key. No cloud. Talks only to 127.0.0.1 by default.

Usage:
    python scripts/local_chat.py "Explain what a Python decorator is"
    echo "summarize this" | python scripts/local_chat.py -
    python scripts/local_chat.py "code this" --max-tokens 1024 --model <id>
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8080"


def _get(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def _post(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def first_model(base_url: str, timeout: float) -> str:
    data = _get(base_url.rstrip("/") + "/v1/models", timeout)
    models = data.get("data") or []
    if not models:
        raise SystemExit("local server reports no models")
    return models[0]["id"]


def chat(
    prompt: str,
    base_url: str = DEFAULT_URL,
    model: str = "",
    max_tokens: int = 768,
    temperature: float = 0.0,
    timeout: float = 120.0,
) -> str:
    base_url = base_url.rstrip("/")
    model = model or first_model(base_url, timeout)
    data = _post(
        base_url + "/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout,
    )
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        print("warning: response hit max_tokens; raise --max-tokens", file=sys.stderr)
    return choice["message"].get("content", "")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ask the local MLX model")
    parser.add_argument("prompt", help="Prompt text, or - to read stdin")
    parser.add_argument("--url", default=DEFAULT_URL, help="Local server base URL")
    parser.add_argument("--model", default="", help="Model id; auto-detected if omitted")
    parser.add_argument("--max-tokens", type=int, default=768)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
    if not prompt.strip():
        parser.error("prompt is empty")
    try:
        answer = chat(
            prompt,
            base_url=args.url,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
        )
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"cannot reach {args.url}: {exc.reason}\n"
            "Start the server first: mlx_lm.server --model <id> --port 8080"
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise SystemExit(f"unexpected response shape: {exc}")
    sys.stdout.write(answer.rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
