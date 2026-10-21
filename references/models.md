# Model tiers

Pick a model based on physical unified memory:

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

- KV cache (grows with context length)
- the OS and other applications
- MLX overhead

If the Mac swaps, the fan spins up, or generation slows, step down a tier.

## Starting a tier

```bash
./scripts/start_server.sh mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
```

The second argument is the port:

```bash
./scripts/start_server.sh mlx-community/Qwen2.5-Coder-14B-Instruct-8bit 8081
```

Then point the client at it:

```bash
python scripts/local_chat.py "..." --url http://127.0.0.1:8081
```

## Ollama

Ollama exposes the same OpenAI-compatible route:

```bash
ollama serve
python scripts/local_chat.py "..." \
  --url http://127.0.0.1:11434 \
  --model qwen2.5-coder:7b
```
