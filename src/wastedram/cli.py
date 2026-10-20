"""Small distribution CLI around the unchanged PigModel routing engine."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import requests

from .optimized import Router


MODELS = (
    (16, "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"),
    (32, "mlx-community/Qwen2.5-Coder-7B-Instruct-8bit"),
    (48, "mlx-community/Qwen2.5-Coder-14B-Instruct-8bit"),
    (64, "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"),
    (127, "mlx-community/Qwen2.5-72B-Instruct-4bit"),
    (float("inf"), "mlx-community/Qwen2.5-72B-Instruct-8bit"),
)


def recommended_model(memory_bytes=None):
    """Return a conservative MLX model based on physical unified memory."""
    if memory_bytes is None:
        try:
            memory_bytes = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True,
                stderr=subprocess.DEVNULL,
            ).strip())
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            raise ValueError("Cannot detect Mac memory; pass --local-model") from exc
    memory_gib = (memory_bytes + (1 << 30) - 1) // (1 << 30)
    if memory_gib <= 0:
        raise ValueError("Mac memory must be positive")
    return next(model for limit, model in MODELS if memory_gib <= limit)


def _env(new_name, legacy_name, default=""):
    return os.environ.get(new_name) or os.environ.get(legacy_name) or default


def _local_timeout(model):
    if "72B" in model:
        return 90
    if "32B" in model:
        return 60
    if "14B" in model:
        return 30
    return 15


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="wastedram", description="Spend spare Mac memory before cloud tokens."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("model", help="Print the recommended MLX model for this Mac")
    run = commands.add_parser("run", help="Route a text task to local MLX or cloud")
    run.add_argument("task", help="Question or task")
    run.add_argument("--cloud-model", default="deepseek-chat", help="Cloud model name")
    run.add_argument("--local-model", help="Override the memory-based local model")
    run.add_argument("--local-url", help="Override the local server URL")
    run.add_argument("--mode", choices=("route", "workflow"), default="route")
    run.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "model":
            print(recommended_model())
            return 0

        cloud_url = _env("WASTEDRAM_CLOUD_URL", "PIGMODEL_CLOUD_URL").rstrip("/")
        if not cloud_url:
            raise ValueError("Set WASTEDRAM_CLOUD_URL to an OpenAI-compatible /v1 endpoint")
        local_url = (args.local_url or _env(
            "WASTEDRAM_LOCAL_URL", "PIGMODEL_LOCAL_URL", "http://127.0.0.1:8080"
        )).rstrip("/")
        local_model = args.local_model or recommended_model()
        router = Router(
            cloud_url,
            args.cloud_model,
            local_model,
            cloud_key=_env("WASTEDRAM_CLOUD_API_KEY", "PIGMODEL_CLOUD_API_KEY"),
            local_url=local_url,
            local_timeout=_local_timeout(local_model),
            cache_path=Path.home() / ".cache/wastedram/responses.sqlite3",
        )
        try:
            result = router.run(args.task, use_cache=not args.no_cache, mode=args.mode)
        finally:
            router.close()
    except (OSError, requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"wastedram: {exc}", file=sys.stderr)
        return 1

    print(result["content"])
    print(
        f"source={result['source']} cloud_tokens={result['cloud_tokens']} "
        f"elapsed_s={result['elapsed_s']:.3f}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
