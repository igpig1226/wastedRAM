"""Programmatic entry for host AI agents."""

from __future__ import annotations

from .optimized import Router

_CODE_KEYWORDS = (
    "def ", "class ", "function", "implement", "refactor", "```",
    "代码", "函数", "实现", "bug", "unit test", "pytest", "sql", "api endpoint",
)


def _select_mode(task: str) -> str:
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
    """Run a task and return Router.run() unchanged.

    mode="workflow" when the task asks for a workflow or is a long code-bearing
    request (>500 chars); otherwise mode="route".
    """
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
        return router.run(task, mode=_select_mode(task))
    finally:
        router.close()
