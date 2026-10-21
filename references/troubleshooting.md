# Troubleshooting

## `cannot reach http://127.0.0.1:8080`

The local server is not running. Start it:

```bash
./scripts/start_server.sh
```

Check:

```bash
curl -s http://127.0.0.1:8080/v1/models
```

## `mlx_lm.server not found`

Install the runtime:

```bash
pip install mlx-lm
```

## Output stops mid-sentence

The answer hit `--max-tokens` (default 768). The script prints a warning to
stderr. Raise the cap and retry:

```bash
python scripts/local_chat.py "..." --max-tokens 2048
```

## `local server reports no models`

The server started but has not loaded a model yet, or the model failed to load.
Check the server console for download or memory errors.

## Mac slows down or swaps

The model does not fit comfortably in unified memory. Step down a tier using
`references/models.md`, or use a shorter prompt.

## Garbage or hallucinated answer

The local model is small. Usually the prompt is too vague, or the task needs
more reasoning than a 7B model can do. Tighten the contract: list input types,
output shape, and every invalid case. If it still fails, do the task with the
host model.

## Wrong / missing code in the answer

Local output is not verified. Run it, compile it, or test it before use. The
skill intentionally does not claim correctness.

## No network access

By design. This skill never calls the internet; it only talks to
`127.0.0.1`.
