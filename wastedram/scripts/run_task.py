"""Run a task through wastedRAM without installing the package.

Adds the repository's ``src`` directory to ``sys.path`` so a plain checkout
works for agents that can execute Python but not pip install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from wastedram.skill_entry import run  # noqa: E402

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a task through wastedRAM")
    parser.add_argument("task")
    parser.add_argument("--cloud-url", required=True)
    parser.add_argument("--cloud-model", default="deepseek-chat")
    parser.add_argument("--cloud-key", default="")
    parser.add_argument("--local-model", default="")
    parser.add_argument("--local-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
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
