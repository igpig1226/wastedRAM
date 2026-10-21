# Model tiers

`wastedram model` reads `hw.memsize` and picks a conservative MLX model. The
mapping is:

| Unified memory | Model | Weight file (approx.) |
| --- | --- | ---: |
| ≤16GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | 4.0 GiB |
| 17–32GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-8bit` | 7.5 GiB |
| 33–48GB | `mlx-community/Qwen2.5-Coder-14B-Instruct-8bit` | 14.6 GiB |
| 49–64GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` | 17.2 GiB |
| 65–127GB | `mlx-community/Qwen2.5-72B-Instruct-4bit` | 38.1 GiB |
| ≥128GB | `mlx-community/Qwen2.5-72B-Instruct-8bit` | 71.9 GiB |

The 65GB+ tiers use general Qwen2.5 Instruct models because no matching Coder
quantization is published at that size. Compare quality on your own tasks before
assuming a larger tier is better.

## Runtime memory

Weight size is not runtime memory. Add:

- KV cache (grows with context length and batch size)
- the OS and other applications
- MLX overhead

If the Mac swaps, the fan spins up, or generation slows noticeably, step down a
tier or shorten the prompt. For 8GB machines prefer the 4bit 7B tier.

## Overriding

```bash
mlx_lm.server --model <model-id> --port 8080
wastedram run "..." --local-model <model-id>
```

Pass the same ID to both commands. `--local-url` changes the endpoint if the
server is not on 8080.

## Ollama

```bash
export WASTEDRAM_LOCAL_URL=http://127.0.0.1:11434
wastedram run "..." --local-model qwen2.5-coder:7b
```

Ollama must expose the OpenAI-compatible `/v1` route.
