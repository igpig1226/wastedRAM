---
name: wastedram
description: Offload routine text and coding subtasks to a local MLX model on Apple Silicon instead of spending the host model's context and tokens on them. Use when a task is mechanical, well-specified, or easily verifiable — summarizing, translating, explaining a concept, drafting boilerplate, writing a small self-contained function, or generating test cases. Do NOT use for architecture decisions, cross-file refactors, security-sensitive changes, or anything that needs the host model's judgment.
license: MIT
compatibility: Apple Silicon Mac, Python 3.10+, local mlx-lm server
---

# wastedRAM

Your host model is expensive. This skill lets you hand mechanical subtasks to a local MLX model on the same Mac — no API key, no cloud, no network.

**The rule: delegate the easy, verifiable work. Keep the judgment.**

## When to use

Delegate to the local model when the subtask is:

- Self-contained: one prompt in, one answer out, no repo context needed
- Mechanical: translate, summarize, explain a concept, rename, format, convert
- Boilerplate: a small function, a regex, a SQL snippet, a test scaffold
- Independently checkable: you can verify the answer quickly

## When NOT to use

Keep these yourself:

- Architecture, design tradeoffs, debugging across files
- Security-sensitive code, auth, crypto, credentials
- Anything needing repo-wide context or the user's intent
- Final review of generated code

## Prerequisites

```bash
pip install mlx-lm
```

Start the local server once per session:

```bash
./scripts/start_server.sh
# or explicitly:
mlx_lm.server --model mlx-community/Qwen2.5-Coder-7B-Instruct-8bit --port 8080 --host 127.0.0.1
```

Verify it is up:

```bash
curl -s http://127.0.0.1:8080/v1/models
```

The model is auto-detected from that endpoint, so you do not need to pass an ID.

## How to delegate

```bash
python scripts/local_chat.py "Explain what a Python context manager is in 3 sentences"
```

```bash
python scripts/local_chat.py "Write a Python function that parses a TCP port from int or decimal string, raising ValueError otherwise. Include tests." --max-tokens 1024
```

Long input via stdin:

```bash
cat notes.txt | python scripts/local_chat.py - --max-tokens 1024
```

Options:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--url` | `http://127.0.0.1:8080` | Local server base URL |
| `--model` | auto-detected | Model id override |
| `--max-tokens` | `768` | Output cap; raise it for code |
| `--temperature` | `0.0` | Keep 0 for deterministic work |
| `--timeout` | `120` | Seconds before giving up |

The script prints the answer to stdout and a truncation warning to stderr if the output hit the cap. **Always check the warning** — a cut-off answer is worse than no answer.

## Workflow

1. Split the user's request into judgment work (you) and mechanical work (local).
2. For each mechanical piece, call `local_chat.py` with a complete, self-contained prompt. Include the exact contract: input types, output shape, error behavior.
3. Read the answer. Verify it cheaply — run it, compile it, or sanity-check the output.
4. Fix or rewrite anything wrong. You own the final result.
5. Compose the final response yourself. Do not paste local output verbatim if it is verbose or off-format.

## Writing good delegation prompts

The local model is small. It needs explicit contracts.

Good:

```text
Write a Python function parse_port(value) that:
- accepts int (not bool) or base-10 decimal string
- returns int in 1..65535
- raises ValueError for float, bool, None, "443.0", 0, 65536
Return only the function and a short test block.
```

Bad:

```text
Write a port parser
```

Rules:

- State input types and every invalid case you care about
- Ask for only what you need (no preamble, no explanation unless asked)
- For code, ask for a minimal runnable block plus tests
- Keep prompts under a few hundred words; split larger tasks

## Model tiers

| Unified memory | Model |
| --- | --- |
| ≤16GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
| 17–32GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-8bit` |
| 33–48GB | `mlx-community/Qwen2.5-Coder-14B-Instruct-8bit` |
| 49–64GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` |
| 65–127GB | `mlx-community/Qwen2.5-72B-Instruct-4bit` |
| ≥128GB | `mlx-community/Qwen2.5-72B-Instruct-8bit` |

Weight size is not runtime memory. If the Mac swaps or slows, step down a tier. Pass the chosen ID to `start_server.sh`.

## Important rules

- Never send secrets, credentials, or private user data to the local model unnecessarily — it is local, but do not paste keys into prompts anyway.
- The local model is not a correctness guarantee. Verify every generated function before using it.
- Do not claim you delegated something unless you actually called the script.
- If the server is down, either start it or do the task yourself. Do not silently fail.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `cannot reach http://127.0.0.1:8080` | Server not running | `./scripts/start_server.sh` |
| `mlx_lm.server not found` | mlx-lm missing | `pip install mlx-lm` |
| Output ends mid-sentence | Hit `--max-tokens` | Raise it and retry |
| Mac slows or swaps | Model too large | Step down a tier |
| Garbage or hallucinated answer | Prompt too vague or task too hard | Tighten the contract or do it yourself |

More: [references/models.md](references/models.md), [references/troubleshooting.md](references/troubleshooting.md).
