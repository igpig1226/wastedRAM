---
name: wastedram
description: Route coding and reasoning tasks through a local MLX model on Apple Silicon and fall back to an OpenAI-compatible cloud API only when needed, cutting cloud token spend. Use when the user asks to reduce API cost, run tasks locally, offload simple work to the Mac GPU, or explicitly mentions wastedRAM, local MLX routing, or spare unified memory. Do NOT use for cloud-only work, non-Mac hosts, or tasks that must not leave the machine.
license: MIT
compatibility: Apple Silicon Mac, Python 3.10+
---

# wastedRAM

Spend spare Mac memory before cloud tokens. This skill teaches any AI coding agent to split work into two layers:

1. **Local MLX** — short factual tasks and conceptual questions run on a local quantized model, cost zero cloud tokens.
2. **Cloud (OpenAI-compatible)** — planning, synthesis, code acceptance, and anything the local tier cannot finish.

The router decides automatically; the agent calls one script or one function.

## When to use

- The user wants to cut cloud API cost or run work locally.
- There is a long coding task that can be decomposed (implement, refactor, test, review).
- The host runs on an Apple Silicon Mac with spare unified memory.
- The user says "wastedRAM", "local MLX", "spare memory", "save tokens", "离线跑", "省 token".

## When NOT to use

- The host is not Apple Silicon, or the user forbids local inference.
- The task requires a cloud-only model capability (large context, vision, tools).
- The user needs deterministic output that cannot tolerate route/cache variance.

## Start the local server

```bash
mlx_lm.server --model mlx-community/Qwen2.5-Coder-7B-Instruct-8bit --port 8080 --host 127.0.0.1
```

Pick the model from the tier table below. Keep this process running in a separate terminal.

## Configure

| Variable | Meaning |
| --- | --- |
| `WASTEDRAM_CLOUD_URL` | OpenAI-compatible `/v1` endpoint. Required for cloud paths. |
| `WASTEDRAM_CLOUD_API_KEY` | Cloud credential. Required by most providers. |
| `WASTEDRAM_LOCAL_URL` | Local endpoint, default `http://127.0.0.1:8080`. |

Pure local hits (`is_simple` / `is_medium`) need no cloud key at all.

## Invoke the skill

### Path A — bundled script (no install, any shell-capable agent)

```bash
python scripts/run_task.py "Implement a Python parse_port(value) function with tests" \
  --cloud-url https://api.deepseek.com/v1 \
  --cloud-model deepseek-chat \
  --local-model mlx-community/Qwen2.5-Coder-7B-Instruct-8bit
```

The answer goes to stdout; a one-line `source=... cloud_tokens=... elapsed_s=...` summary goes to stderr. This is the lowest-friction path for Claude Code, Codex CLI, Cursor, Aider, Windsurf, Cline, and any agent with shell access.

### Path B — Python (any agent that can execute Python)

```python
import sys
sys.path.insert(0, "scripts")
from run_task import run

result = run(
    task="Implement a Python parse_port(value) function with tests",
    cloud_url="https://api.deepseek.com/v1",
    cloud_model="deepseek-chat",
    cloud_key="sk-...",              # optional for pure-local tasks
    local_model="mlx-community/Qwen2.5-Coder-7B-Instruct-8bit",
    local_url="http://127.0.0.1:8080",
)
print(result["content"])
print(result["source"], result["cloud_tokens"])
```

`run()` selects the mode itself:

- task contains `workflow`, **or** length > 500 with a code keyword → `mode="workflow"`
- otherwise → `mode="route"`

## Return value

| Key | Type | Meaning |
| --- | --- | --- |
| `content` | str | Final answer — use this as the answer. |
| `source` | str | `local`, `cloud`, `cloud_fallback`, `workflow`, or `cache`. |
| `cloud_tokens` | int | Total cloud tokens billed. |
| `cloud_prompt_tokens` / `cloud_completion_tokens` | int | Split usage when the provider reports it. |
| `local_tokens` / `local_seconds` | int / float | Local usage and wall time. |
| `elapsed_s` | float | End-to-end seconds. |
| `code_check` | bool \| None | Generated code passed executable acceptance checks. `None` when no code. |
| `cloud_calls` | int | Cloud calls made in workflow mode. |

## Modes

- **route** (default): one pass. Simple/medium → local; otherwise cloud with an adaptive token budget. Cheapest for single questions.
- **workflow**: cloud PLAN (merged plan + analysis) → local leaves in parallel → cloud synthesis with executable acceptance. Use for multi-file or "implement + test" requests.

Choose route unless the task is genuinely decomposable or asks for tests/acceptance.

## Model tiers

| Unified memory | Model |
| --- | --- |
| ≤16GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
| 17–32GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-8bit` |
| 33–48GB | `mlx-community/Qwen2.5-Coder-14B-Instruct-8bit` |
| 49–64GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` |
| 65–127GB | `mlx-community/Qwen2.5-72B-Instruct-4bit` |
| ≥128GB | `mlx-community/Qwen2.5-72B-Instruct-8bit` |

Weight size is not runtime memory. Context, the OS, and other apps also need room. If the Mac swaps or slows, step down a tier or shorten context.

## How it saves tokens

- Simple factual and conceptual requests never reach the cloud.
- Cloud prompts are compressed and use adaptive budgets (start small, step up only on truncation).
- Exact-match cache prevents duplicate calls.
- Workflow merges planning and analysis into one cloud call, then runs local leaves concurrently.
- Local failures fall back to cloud rather than failing the task.

Actual savings depend on task mix, cache hit rate, and the provider's pricing.

## Important rules

- Never paste API keys into the task text; they would be sent to the cloud and cached.
- The skill is not a general correctness guarantee. Bounded code checks (AST + execution harness) catch obvious breakage, not design errors. Review the final diff yourself.
- Do not claim a cloud saving without reading `cloud_tokens` from the result.
- If `source="cloud_fallback"`, the local tier was attempted and failed. Report that honestly.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Set WASTEDRAM_CLOUD_URL...` | Cloud URL missing | Pass `--cloud-url` or export `WASTEDRAM_CLOUD_URL`. |
| `connection refused` on run | Local server not started | Start `mlx_lm.server` on port 8080. |
| Every task is `cloud` | Local model not passed or server down | Pass `--local-model`, check `/v1/models`. |
| Mac slows or swaps | Model too large for memory | Step down a tier or reduce context. |
| `Cloud response truncated` | Budget too small and no adaptive step-up | Retry; if persistent, raise the cloud model's max tokens. |
| Wrong / hallucinated local answer | Medium tier misfire | Disable local with `--local-model ""`, or report the task. |

Full detail: [references/models.md](references/models.md), [references/troubleshooting.md](references/troubleshooting.md).
