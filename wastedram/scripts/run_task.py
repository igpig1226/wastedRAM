"""Run one task through the vendored wastedRAM router engine.

Usage:
    python scripts/run_task.py "your task" --cloud-url https://api.deepseek.com/v1

No pip install required; the engine lives next to this script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import Router  # noqa: E402

_CODE_KEYWORDS = (
    "def ", "class ", "function", "implement", "refactor", "```",
    "代码", "函数", "实现", "bug", "unit test", "pytest", "sql", "api endpoint",
)


def select_mode(task: str) -> str:
    lowered = task.lower()
    if "workflow" in lowered:
        return "workflow"
    if len(task) > 500 and any(k in lowered for k in _CODE_KEYWORDS):
        return "workflow"
    return "route"


def run(
    task: str,
    cloud_url: str,
    cloud_model: str = "deepseek-chat",
    cloud_key: str = "",
    local_model: str = "",
    local_url: str = "http://127.0.0.1:8080",
) -> dict:
    """Run a task and return Router.run() unchanged."""
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be a nonempty string")
    if not cloud_url or not cloud_model:
        raise ValueError("cloud_url and cloud_model are required")
    router = Router(
        cloud_url,
        cloud_model,
        local_model,
        cloud_key=cloud_key,
        local_url=local_url,
        local_timeout=75,
    )
    try:
        return router.run(task, mode=select_mode(task))
    finally:
        router.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a task through wastedRAM")
    parser.add_argument("task")
    parser.add_argument("--cloud-url", required=True)
    parser.add_argument("--cloud-model", default="deepseek-chat")
    parser.add_argument("--cloud-key", default="")
    parser.add_argument("--local-model", default="")
    parser.add_argument("--local-url", default="http://127.0.0.1:8080")
    args = parser.parse_args(argv)
    result = run(
        task=args.task,
        cloud_url=args.cloud_url,
        cloud_model=args.cloud_model,
        cloud_key=args.cloud_key,
        local_model=args.local_model,
        local_url=args.local_url,
    )
    print(result["content"])
    print(
        f"source={result['source']} cloud_tokens={result['cloud_tokens']} "
        f"elapsed_s={result['elapsed_s']:.3f}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
