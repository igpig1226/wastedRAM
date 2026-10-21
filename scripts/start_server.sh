#!/usr/bin/env bash
# Start a local MLX server for the wastedRAM skill.
# Usage: ./scripts/start_server.sh [model-id] [port]
set -euo pipefail

MODEL="${1:-mlx-community/Qwen2.5-Coder-7B-Instruct-8bit}"
PORT="${2:-8080}"

command -v mlx_lm.server >/dev/null 2>&1 || {
  echo "mlx_lm.server not found. Install with: pip install mlx-lm" >&2
  exit 1
}

echo "Starting $MODEL on 127.0.0.1:$PORT ..."
exec mlx_lm.server --model "$MODEL" --port "$PORT" --host 127.0.0.1
