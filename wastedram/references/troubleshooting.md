# Troubleshooting

## `Set WASTEDRAM_CLOUD_URL to an OpenAI-compatible /v1 endpoint`

Export the cloud URL:

```bash
export WASTEDRAM_CLOUD_URL=https://api.deepseek.com/v1
```

Trailing `/v1` is required. The legacy `PIGMODEL_CLOUD_URL` alias also works.

## `Connection refused` or a timeout on `run`

The local model server is not running. Start it:

```bash
mlx_lm.server --model "$(wastedram model)" --port 8080 --host 127.0.0.1
```

Verify it:

```bash
curl http://127.0.0.1:8080/v1/models
```

## Every task reports `source=cloud`

Possible causes:

1. `--local-model` was not passed and `wastedram model` failed to detect memory.
2. The server is running a different model ID than the one passed.
3. `is_simple` / `is_medium` did not match the task; long conceptual questions
   may be classified conservatively.

Check which model the server actually exposes with `/v1/models`, then pass that
exact ID.

## Mac slows down or swaps

The model does not fit comfortably in unified memory. Step down a tier (see
`references/models.md`) or reduce the prompt/context length.

## `Cloud response truncated`

The cloud budget was too small. The router already retries with larger budgets;
if the error persists, the provider truncated a response that genuinely needs
more room. Raise the cloud model's limit or split the task.

## `Invalid plan`

Workflow mode asked the cloud for a JSON plan and received malformed output.
Retry once; if it repeats, the task is probably too ambiguous for the planner.
Use route mode instead.

## `Cloud fallback failed executable acceptance`

The generated code did not pass the bounded AST + execution checks. This is
usually a real defect (wrong function name, unsafe file write, missing cleanup).
Read the generated code, fix the prompt, and retry. The check is intentionally
narrow: passing it does not prove correctness.

## Nothing is being cached

Cache key includes the cloud URL, cloud model, local URL, local model, and the
task. Changing any of them produces a different key. `--no-cache` disables the
lookup entirely.
