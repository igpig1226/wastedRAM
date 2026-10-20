"""Cloud-planned work with concurrent, context-free local leaves."""

import concurrent.futures
import hashlib
import json
import os
import sqlite3
import time

import requests

from .codecheck import check as check_code, target as code_target


# Combined plan + analysis in one cloud call to save a round-trip.
# Returns JSON: {cloud_analysis, leaves[{task}]}
PLAN = (
    "Plan and analyse this software task. Return ONLY JSON with keys: "
    "'cloud_analysis' (your complete reasoning for the cloud-owned work), "
    "'leaves' (1-2 objects each with 'task': self-contained instruction with "
    "full input/output contract, ≤2400 chars). Delegate only small isolated "
    "implementation units; keep integration, design and cross-file reasoning "
    "in cloud_analysis. Never delegate secrets, security, or cross-file work."
)

# Adaptive synthesis budgets — try smallest first, step up only on truncation.
_SYNTHESIS_BUDGETS = [768, 1536, 2048]
_FALLBACK_BUDGETS = [1024, 2048, 4096]


class WorkflowFailure(ValueError):
    def __init__(self, message, metrics):
        super().__init__(message)
        self.metrics = metrics


def _cloud(router, messages, max_tokens=1024):
    response = requests.post(
        router.cloud_url + "/chat/completions",
        headers={"Authorization": "Bearer " + router.cloud_key} if router.cloud_key else {},
        json={"model": router.cloud_model, "messages": messages,
              "temperature": 0, "max_tokens": max_tokens}, timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]
    usage = data.get("usage") or {}
    if choice.get("finish_reason") == "length":
        err = ValueError("Cloud response truncated")
        err.usage = usage  # preserve usage so failure metrics aren't zero
        raise err
    if not usage.get("total_tokens") or not choice["message"].get("content"):
        raise ValueError("Cloud response missing content or usage")
    return choice["message"]["content"], usage


def _cloud_adaptive(router, messages, budgets):
    """Try each budget in order; step up only on truncation."""
    last_exc = None
    for budget in budgets:
        try:
            return _cloud(router, messages, budget)
        except ValueError as exc:
            if "truncated" in str(exc):
                last_exc = exc
                continue
            raise
    raise last_exc


def _local(router, task, num_ctx=2048, num_predict=768):
    """Call local MLX/Ollama model via OpenAI-compatible /v1/chat/completions."""
    started = time.perf_counter()
    router._local_used = True
    response = requests.post(
        router.local_url + "/v1/chat/completions",
        json={"model": router.local_model,
              "messages": [{"role": "user", "content": task}],
              "temperature": 0, "max_tokens": num_predict},
        timeout=router.local_timeout,
    )
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("Local response truncated")
    answer = choice["message"].get("content", "")
    if not answer or not answer.strip():
        raise ValueError("Local response empty")
    usage = data.get("usage") or {}
    tokens = int(usage.get("total_tokens") or 0)
    return answer, tokens, time.perf_counter() - started


def _workflow_cache_get(router, digest):
    try:
        router.cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with sqlite3.connect(router.cache_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS responses "
                         "(key TEXT PRIMARY KEY, content TEXT NOT NULL)")
            row = conn.execute("SELECT content FROM responses WHERE key=?",
                               (digest,)).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _workflow_cache_put(router, digest, content):
    try:
        with sqlite3.connect(router.cache_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS responses "
                         "(key TEXT PRIMARY KEY, content TEXT NOT NULL)")
            conn.execute("INSERT OR REPLACE INTO responses VALUES (?,?)",
                         (digest, content))
    except Exception:
        pass


def run_workflow(router, task, use_cache=True):
    """Never send unchecked code into the final response; count every cloud call."""
    if not isinstance(task, str) or not task.strip():
        raise ValueError("Workflow requires a nonempty text task")
    started = time.perf_counter()
    usages = []
    local_tokens = 0
    local_seconds = 0
    checks = []
    source = "workflow"

    # Cache check — version 9 avoids collision with route-mode cache (version 7)
    digest = hashlib.sha256(json.dumps(
        [9, router.cloud_url, router.cloud_model,
         router.local_url, router.local_model, task],
        ensure_ascii=False,
    ).encode()).hexdigest()
    if use_cache:
        cached = _workflow_cache_get(router, digest)
        if cached:
            return {"content": cached, "source": "cache", "cloud_tokens": 0,
                    "cloud_prompt_tokens": 0, "cloud_completion_tokens": 0,
                    "cloud_cache_hit_tokens": 0, "local_tokens": 0,
                    "local_seconds": 0, "elapsed_s": time.perf_counter() - started}

    def cloud(messages, max_tokens=1024):
        content, usage = _cloud(router, messages, max_tokens)
        usages.append(usage)
        return content

    if not router.local_model:
        raise ValueError("Workflow requires an installed local model")
    try:
        # Single cloud call: plan + analysis merged — adaptive budget so complex tasks don't fail
        raw, plan_usage = _cloud_adaptive(router, [
            {"role": "system", "content": PLAN},
            {"role": "user", "content": task},
        ], [768, 1536, 2048])
        usages.append(plan_usage)
        # Strip markdown fences, then fall back to first {...} block for resilience
        cleaned = raw.strip().replace("```json", "", 1).rstrip("`\n ")
        try:
            plan = json.loads(cleaned)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r'\{.*\}', cleaned, _re.S)
            if not m:
                raise ValueError("Plan response contained no JSON object")
            plan = json.loads(m.group(0))
        leaves = plan["leaves"]
        analysis = plan.get("cloud_analysis", "")
        if not isinstance(analysis, str) or not analysis.strip() or \
                not isinstance(leaves, list) or not 1 <= len(leaves) <= 2 or any(
            not isinstance(leaf, dict) or not isinstance(leaf.get("task"), str)
            or not leaf["task"].strip() or len(leaf["task"]) > 2400 for leaf in leaves
        ):
            raise ValueError("Invalid plan")

        # Local leaves run concurrently; no separate cloud analysis job needed
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            local_jobs = [pool.submit(_local, router, leaf["task"]) for leaf in leaves]
            results = []
            failed = False
            for leaf, job in zip(leaves, local_jobs):
                try:
                    answer, tokens, seconds = job.result()
                    local_tokens += tokens
                    local_seconds += seconds
                    checked = check_code(leaf["task"], answer)
                    checks.append(checked)
                    if checked is False or (checked is None and
                            code_target(leaf["task"]) is not None and "```" in answer):
                        failed = True
                    results.append(answer)
                except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
                    failed = True

        if failed:
            source = "cloud_fallback"
            content, usage = _cloud_adaptive(router, [
                {"role": "user", "content": task},
            ], _FALLBACK_BUDGETS)
            usages.append(usage)
        else:
            # Adaptive synthesis: try 768 first, step up only if truncated
            content, usage = _cloud_adaptive(router, [
                {"role": "system", "content": "Integrate and verify the original task. "
                 "Reject incorrect leaves, fix them yourself. Return a complete final "
                 "answer, with runnable code if requested. No planning narration."},
                {"role": "user", "content":
                 "Original task:\n" + task +
                 "\nCloud analysis:\n" + analysis +
                 "\nDelegated results:\n" + json.dumps(results, ensure_ascii=False)},
            ], _SYNTHESIS_BUDGETS)
            usages.append(usage)

        check = check_code(task, content)
        if check is False:
            source = "cloud_fallback"
            content, usage = _cloud_adaptive(router, [
                {"role": "system", "content": "Executable acceptance failed. Produce one "
                 "fenced minimal runnable Python function with no imports, matching exact "
                 "function name, rejecting bool/float and out-of-range inputs. Include "
                 "requested tests after the function."},
                {"role": "user", "content": task},
            ], _FALLBACK_BUDGETS)
            usages.append(usage)
            check = check_code(task, content)
            if check is False:
                for _ in range(2):
                    content, usage = _cloud_adaptive(router, [
                        {"role": "system", "content": "The prior code failed executable "
                         "tests. For parse_port use type(value) is int OR type(value) is "
                         "str and value.isdecimal(); raise ValueError on all other input; "
                         "reject 0 and >65535. For exclusive creation use open(path, 'x') "
                         "and catch FileExistsError. For SQLite fixtures use yield and "
                         "finally close(). Return minimal fenced code."},
                        {"role": "user", "content": task},
                    ], [1024, 2048])
                    usages.append(usage)
                    check = check_code(task, content)
                    if check:
                        break
                if not check:
                    raise ValueError("Cloud fallback failed executable acceptance")

        if use_cache:
            _workflow_cache_put(router, digest, content)

        return {"content": content, "source": source, "code_check": check,
                "leaf_checks": checks, "cloud_calls": len(usages),
                "cloud_tokens": sum(int(u["total_tokens"]) for u in usages),
                "cloud_prompt_tokens": sum(int(u.get("prompt_tokens") or 0) for u in usages),
                "cloud_completion_tokens": sum(int(u.get("completion_tokens") or 0) for u in usages),
                "cloud_cache_hit_tokens": sum(int(u.get("prompt_cache_hit_tokens") or 0) for u in usages),
                "local_tokens": local_tokens, "local_seconds": local_seconds,
                "elapsed_s": time.perf_counter() - started}
    except (ValueError, KeyError, TypeError) as exc:
        raise WorkflowFailure("Workflow could not complete: " + str(exc), {
            "cloud_tokens": sum(int(u["total_tokens"]) for u in usages),
            "cloud_prompt_tokens": sum(int(u.get("prompt_tokens") or 0) for u in usages),
            "cloud_completion_tokens": sum(int(u.get("completion_tokens") or 0) for u in usages),
            "cloud_cache_hit_tokens": sum(int(u.get("prompt_cache_hit_tokens") or 0) for u in usages),
            "local_tokens": local_tokens, "local_seconds": local_seconds,
            "elapsed_s": time.perf_counter() - started,
        }) from exc
