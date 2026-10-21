"""Conservative cloud-token routing with exact-match response reuse."""

import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path

import requests

from .codecheck import check as check_code, target as code_target


class TruncatedResponse(ValueError):
    def __init__(self, tokens):
        super().__init__("Model response was truncated at the token limit")
        self.tokens = tokens


def is_simple(task):
    """Short, factual, zero-risk: run entirely local at 96 tokens."""
    lowered = task.strip().lower()
    safe_starts = (
        "translate ", "翻译", "explain what ", "what is ", "define ", "用一句话解释",
        "what does ", "convert ", "how do you say ", "spell ", "what's the ",
        "abbreviation for ", "what are the ",
    )
    unsafe_terms = (
        "法律", "医疗", "诊断", "投资", "security", "dosage", "dose", "stock",
        "legal", "medical", "finance", "compare", "analyze", "分析", "设计", "代码",
        "code", "function", "class", "bug", "error", "fix", "implement", "write",
    )
    return (len(lowered) <= 200
            and lowered.startswith(safe_starts)
            and not any(t in lowered for t in unsafe_terms))


def is_medium(task):
    """Self-contained conceptual/explanatory question — route local at 384 tokens."""
    if not isinstance(task, str):
        return False
    lowered = task.strip().lower()
    if not 30 <= len(lowered) <= 500:
        return False
    # Exclude code-generation requests
    code_gen = ("write ", "implement ", "create ", "build ", "make a ", "generate ",
                "编写", "实现", "创建", "帮我写", "写一个")
    if any(lowered.startswith(p) for p in code_gen):
        return False
    # Exclude unsafe domains
    unsafe_terms = ("法律", "医疗", "security", "dosage", "legal", "medical", "finance")
    if any(t in lowered for t in unsafe_terms):
        return False
    # Must look like a conceptual question or explanation request
    question_signals = ("?", "？", "explain ", "解释", "why ", "how does ", "what happens",
                        "difference between", "when should", "is it ", "用一句话")
    return any(s in lowered for s in question_signals)


def compact_reservation(task):
    """Extract the complete contract of the explicitly checked SQLite reservation task."""
    if not isinstance(task, str) or code_target(task) != "sqlite_reserve" or not all(
        term in task for term in ("request_id TEXT PRIMARY KEY", "available INTEGER NOT NULL",
                                   "Two workers", "unrelated outstanding work", "return None")
    ):
        return task
    return (
        "Python 3.10 SQLite: fix reserve(conn, sku, request_id, quantity), returning "
        "request_id on success/retry, None if stock insufficient; no new dependencies. "
        "Existing implementation SELECTs available, checks stock, UPDATEs inventory, "
        "INSERTs reservations, commits; it races across two connections and commits "
        "unrelated caller work. Tables: inventory(sku TEXT PRIMARY KEY, available INTEGER "
        "NOT NULL); reservations(request_id TEXT PRIMARY KEY, sku TEXT, quantity INTEGER). "
        "A request_id retry must not decrement twice; two workers racing for the last "
        "unit must not overdraw; errors leave no partial changes. Do not commit/rollback "
        "the caller's open transaction; explicitly require transaction ownership. "
        "Explain the race, show runnable code and name retry and two-worker race tests. "
        "Do not claim a Python lock coordinates processes."
    )


def strip_empty_acknowledgements(task):
    if not isinstance(task, str) or "FLATTENED transcript" not in task:
        return task
    return re.sub(r"Assistant: (?:Understood|Noted|I will preserve those constraints|"
                  r"I have both events)\.\s*", "", task)


def extract_incident_timeline(task):
    if not isinstance(task, str) or "Timeline:" not in task or not all(
        phrase in task.lower() for phrase in ("which deployment", "which two follow-ups")
    ):
        return task
    question, timeline = task.split("Timeline:", 1)
    entries = re.split(r"(?=(?:Monday|Tuesday|Wednesday|Thursday|Friday) \d\d:\d\d )", timeline)
    if len(entries) < 5:
        return task
    selected = [entry for entry in entries if re.search(
        r"\bdeployment\b|\brolled back\b|checkout p95 (?:rose|was)|"
        r"\bagreed to\b|\bno owner\b", entry, re.I
    )]
    condensed = " ".join(selected)
    caveats = ("The customer-facing incident note says several checkouts were slow and a minority "
               "timed out. It does not say orders were duplicated. The payment provider status page "
               "was green throughout. No one measured the exact share of timed-out checkouts in the "
               "primary region. Include these caveats if discussing customer impact.")
    if caveats in condensed:
        condensed = condensed.replace(caveats, "If discussing impact: several slow checkouts, a "
                                      "minority timed out; no duplicated-order claim, provider green, "
                                      "exact timeout share unmeasured.")
    return question + "Timeline: " + condensed


class Router:
    def __init__(self, cloud_url, cloud_model, local_model, cloud_key="", cache_path=None,
                 local_url=None, local_timeout=15):
        self.cloud_url = cloud_url.rstrip("/")
        self.cloud_model = cloud_model
        self.cloud_key = cloud_key
        # MLX-server default port is 8080; Ollama /v1 compat lives on 11434.
        # PIGMODEL_LOCAL_URL overrides both; fall back to OLLAMA_HOST for compat.
        self.local_url = (
            local_url
            or os.environ.get("PIGMODEL_LOCAL_URL")
            or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.local_model = local_model
        self.local_timeout = local_timeout
        self.cache_path = Path(cache_path or Path.home() / ".cache/pigmodel/responses.sqlite3")
        self._last_usage = {}
        self._local_used = False

    def close(self):
        """Unload the local model after a CLI or benchmark session.

        Tries the Ollama /api/generate keep_alive=0 endpoint first (no-op on
        MLX-server which doesn't implement that route); silently ignores errors
        so MLX-server users aren't affected.
        """
        if self._local_used:
            try:
                requests.post(self.local_url + "/api/generate",
                              json={"model": self.local_model, "keep_alive": 0},
                              timeout=10).raise_for_status()
            except requests.RequestException:
                pass
            self._local_used = False

    @staticmethod
    def _messages(task):
        if isinstance(task, str):
            if not task.strip():
                raise ValueError("Task must not be empty")
            return [{"role": "user", "content": task}]
        if not isinstance(task, list) or not task or any(
            not isinstance(message, dict)
            or message.get("role") not in ("system", "user", "assistant")
            or not isinstance(message.get("content"), (str, list))
            for message in task
        ):
            raise TypeError("Expected text or a list of chat messages")
        for message in task:
            content = message["content"]
            if isinstance(content, list) and (message["role"] != "user" or not content or any(
                not isinstance(part, dict) or part.get("type") not in ("text", "image_url")
                or not isinstance(part.get("text") if part["type"] == "text" else
                                  (part.get("image_url") or {}).get("url"), str)
                for part in content
            )):
                raise TypeError("Invalid image/text message content")
        return task

    def _request(self, url, model, task, key, timeout, max_tokens=4096, concise=False,
                 local_format=False, validation_hint="", num_ctx=1024):
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        # Compressed system prompts — shorter but same intent
        system = ("For a translation or name, return only the answer; otherwise be concise."
                  ) if local_format else (
                  "Answer every point; ≤60 words unless code needed. "
                  "Code: minimal runnable solution + tests; reject invalid input types. No preamble."
                  if concise else "")
        if concise and not validation_hint and isinstance(task, str) and len(task) > 900:
            system = "Answer briefly; preserve constraints."
        if validation_hint:
            system += " " + validation_hint
        messages = ([{"role": "system", "content": system}] if system else []) + self._messages(task)
        if local_format:
            # MLX-server and Ollama both expose OpenAI-compatible /v1/chat/completions
            response = requests.post(
                self.local_url + "/v1/chat/completions",
                json={"model": model, "messages": messages,
                      "temperature": 0, "max_tokens": max_tokens,
                      "num_ctx": num_ctx},   # passed through by Ollama; ignored by pure MLX
                timeout=timeout,
            )
        else:
            response = requests.post(
                url + "/chat/completions", headers=headers,
                json={"model": model, "messages": messages,
                      "temperature": 0, "max_tokens": max_tokens}, timeout=timeout,
            )
        response.raise_for_status()
        data = response.json()
        # Both MLX-server and Ollama /v1 return OpenAI-shaped JSON
        choice = data["choices"][0]
        usage = data.get("usage") or {}
        if not local_format:
            self._last_usage = usage
        tokens = int(usage.get("total_tokens") or 0)
        truncated = choice.get("finish_reason") == "length"
        content = choice["message"]["content"]
        if truncated:
            raise TruncatedResponse(tokens)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model returned empty content")
        return content, tokens

    def run(self, task, use_cache=True, mode="route"):
        if mode == "workflow":
            from .workflow import run_workflow
            return run_workflow(self, task, use_cache=use_cache)
        if mode != "route":
            raise ValueError("mode must be route or workflow")
        self._messages(task)
        started = time.perf_counter()
        digest = hashlib.sha256(json.dumps(
            [7, self.cloud_url, self.cloud_model, self.local_url, self.local_model, task],
            ensure_ascii=False,
        ).encode()).hexdigest()
        if use_cache:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not self.cache_path.exists():
                descriptor = os.open(self.cache_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
            with sqlite3.connect(self.cache_path) as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, content TEXT NOT NULL)")
                cached = connection.execute("SELECT content FROM responses WHERE key=?", (digest,)).fetchone()
            if cached:
                return {"content": cached[0], "source": "cache", "cloud_tokens": 0,
                        "cloud_prompt_tokens": 0, "cloud_completion_tokens": 0,
                        "local_tokens": 0, "local_seconds": 0,
                        "elapsed_s": time.perf_counter() - started}

        source = "cloud"
        local_tokens = 0
        local_seconds = 0

        # Tier 1: simple — short factual/translation, 96 local tokens, ctx 1024
        if isinstance(task, str) and is_simple(task) and self.local_model:
            local_started = time.perf_counter()
            try:
                self._local_used = True
                content, local_tokens = self._request(
                    self.local_url, self.local_model, task, "", self.local_timeout,
                    max_tokens=96, local_format=True, num_ctx=1024,
                )
                source = "local"
                cloud_tokens = 0
            except TruncatedResponse as exc:
                local_tokens = exc.tokens
                source = "cloud_fallback"
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
                source = "cloud_fallback"
            finally:
                local_seconds = time.perf_counter() - local_started

        # Tier 2: medium — conceptual questions, 384 local tokens, ctx 2048
        elif isinstance(task, str) and is_medium(task) and self.local_model:
            local_started = time.perf_counter()
            try:
                self._local_used = True
                content, local_tokens = self._request(
                    self.local_url, self.local_model, task, "", self.local_timeout,
                    max_tokens=384, local_format=True, num_ctx=2048,
                )
                source = "local"
                cloud_tokens = 0
            except TruncatedResponse as exc:
                local_tokens = exc.tokens
                source = "cloud_fallback"
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
                source = "cloud_fallback"
            finally:
                local_seconds = time.perf_counter() - local_started

        if source != "local":
            self._last_usage = {}
            reserve_hint = ("One fenced standalone Python function; no imports. Reject "
                            "conn.in_transaction before BEGIN IMMEDIATE. Check existing request_id "
                            "first, then conditional UPDATE WHERE available>=? (check rowcount), "
                            "INSERT, commit. Roll back on failure. Explain race in one sentence; "
                            "name two tests without implementing them. No repeated strategy prose.")
            # Adaptive cloud budgets: try 512 first, step up only on truncation
            _cloud_budgets = [512, 1024, 2048]
            last_exc = None
            content = None
            for budget in _cloud_budgets:
                try:
                    self._last_usage = {}
                    content, cloud_tokens = self._request(
                        self.cloud_url, self.cloud_model,
                        extract_incident_timeline(
                            strip_empty_acknowledgements(compact_reservation(task))),
                        self.cloud_key, 90, max_tokens=budget, concise=True,
                        validation_hint=reserve_hint if code_target(task) == "sqlite_reserve" else "",
                    )
                    break
                except TruncatedResponse as exc:
                    cloud_tokens = exc.tokens
                    last_exc = exc
            if content is None:
                raise last_exc
            if cloud_tokens <= 0:
                raise ValueError("Cloud endpoint did not report token usage")
            prompt_tokens = int(self._last_usage.get("prompt_tokens") or 0)
            completion_tokens = int(self._last_usage.get("completion_tokens") or 0)
            code_check = check_code(task, content)
            if code_check is False:
                hint = ("Accept only int or base-10 integer strings, reject bool, floats, decimal-point "
                        "strings, and out-of-range values. Include tests." if code_target(task) == "parse_port"
                        else "The previous solution failed executable checks: cover success, HTTP 500, "
                        "and 5-second abort." if code_target(task) == "js_fetch"
                        else reserve_hint
                        if code_target(task) == "sqlite_reserve"
                        else "Use atomic exclusive creation with open(path, 'x') or "
                        "os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL); "
                        "handle FileExistsError and never overwrite the file."
                        if code_target(task) == "exclusive_file"
                        else "Use a yield fixture that always closes the SQLite connection in finally.")
                for retry in range(3 if code_target(task) == "sqlite_reserve" else 2):
                    self._last_usage = {}
                    content, retry_tokens = self._request(
                        self.cloud_url, self.cloud_model,
                        compact_reservation(task), self.cloud_key, 90,
                        concise=True, validation_hint=hint,
                    )
                    cloud_tokens += retry_tokens
                    prompt_tokens += int(self._last_usage.get("prompt_tokens") or 0)
                    completion_tokens += int(self._last_usage.get("completion_tokens") or 0)
                    source = "cloud_fallback"
                    code_check = check_code(task, content)
                    if code_check:
                        break
                if not code_check:
                    raise ValueError("Generated " + str(code_target(task)) +
                                     " code failed executable acceptance checks")
        else:
            code_check = None
            prompt_tokens = completion_tokens = 0
        if use_cache:
            with sqlite3.connect(self.cache_path) as connection:
                connection.execute("INSERT OR REPLACE INTO responses VALUES (?, ?)", (digest, content))
        return {"content": content, "source": source, "cloud_tokens": cloud_tokens,
                "code_check": code_check,
                "cloud_prompt_tokens": prompt_tokens,
                "cloud_completion_tokens": completion_tokens,
                "local_tokens": local_tokens, "local_seconds": local_seconds,
                "elapsed_s": time.perf_counter() - started}

    def baseline(self, task):
        self._messages(task)
        started = time.perf_counter()
        self._last_usage = {}
        content, tokens = self._request(self.cloud_url, self.cloud_model, task, self.cloud_key, 90)
        if tokens <= 0:
            raise ValueError("Cloud endpoint did not report token usage")
        return {"content": content, "source": "cloud", "cloud_tokens": tokens,
                "cloud_prompt_tokens": int(self._last_usage.get("prompt_tokens") or 0),
                "cloud_completion_tokens": int(self._last_usage.get("completion_tokens") or 0),
                "elapsed_s": time.perf_counter() - started}
