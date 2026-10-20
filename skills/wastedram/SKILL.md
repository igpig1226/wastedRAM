---
name: wastedram
description: Route text tasks through a memory-matched local MLX model and an OpenAI-compatible cloud API on Apple Silicon Macs. Use when the user asks to run wastedRAM or reduce cloud tokens with spare Mac memory.
---

# wastedRAM

Install from Git with `pip install 'wastedram[mlx] @ git+https://github.com/igpig1226/wastedRAM.git'` until a PyPI release exists. Set `WASTEDRAM_CLOUD_URL` to an OpenAI-compatible `/v1` endpoint and `WASTEDRAM_CLOUD_API_KEY` for authenticated providers. Existing `PIGMODEL_CLOUD_URL`, `PIGMODEL_CLOUD_API_KEY`, and `PIGMODEL_LOCAL_URL` remain compatible aliases. `wastedram run` defaults to cloud model `deepseek-chat`; pass `--cloud-model` for another provider.

## Choose the local model

On an Apple Silicon Mac, `wastedram model` prints the recommendation from physical unified memory. Start the same model on the local server. `wastedram run` selects that tier automatically unless `--local-model` is passed. Model weight size is not runtime memory; step down if the Mac swaps, slows, or lacks free memory.

| Unified memory | MLX model ID |
| --- | --- |
| 8–16GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
| 17–32GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-8bit` |
| 33–48GB | `mlx-community/Qwen2.5-Coder-14B-Instruct-8bit` |
| 49–64GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` |
| 65–127GB | `mlx-community/Qwen2.5-72B-Instruct-4bit` |
| 128GB+ | `mlx-community/Qwen2.5-72B-Instruct-8bit` |

Start with `mlx_lm.server --model "$(wastedram model)" --port 8080 --host 127.0.0.1`. Then run `wastedram run "<question>"`. For a custom model, pass its ID to both `mlx_lm.server --model` and `wastedram run --local-model`. `WASTEDRAM_LOCAL_URL` or `--local-url` changes the local endpoint; default is `http://127.0.0.1:8080`.

For Ollama, set `WASTEDRAM_LOCAL_URL=http://127.0.0.1:11434` and pass an installed Ollama model with `--local-model`. Use `wastedram run "<task>" --mode workflow` only for requested cloud-planned work. Local failures fall back to cloud. Bounded code checks do not establish general correctness. The 65GB+ tiers use general 72B Instruct models rather than Coder variants; compare task quality before assuming a larger tier is better.
