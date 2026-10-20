#!/usr/bin/env bash
set -euo pipefail

if ! command -v mlx_lm.server >/dev/null 2>&1; then
  echo "mlx_lm.server 未安装。请运行: pip install 'wastedram[mlx] @ git+https://github.com/igpig1226/wastedRAM.git'" >&2
  exit 1
fi

if lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
  echo 'Port 8080 is in use; skipping model startup.'
else
  model="${1:-}"
  if [ -z "$model" ]; then
    if ! command -v wastedram >/dev/null 2>&1; then
      echo "wastedram 未安装。请运行: pip install 'wastedram[mlx] @ git+https://github.com/igpig1226/wastedRAM.git'" >&2
      exit 1
    fi
    model="$(wastedram model)"
  fi
  log_file="${TMPDIR:-/tmp}/wastedram-mlx-server.log"
  nohup mlx_lm.server --model "$model" --port 8080 --host 127.0.0.1 >"$log_file" 2>&1 </dev/null &
  server_pid=$!
  echo "Starting $model (PID $server_pid; log: $log_file)"
fi

ready_timeout="${WASTEDRAM_READY_TIMEOUT:-30}"
for ((attempt=0; attempt<ready_timeout; attempt++)); do
  if curl --silent --fail --max-time 1 http://127.0.0.1:8080/v1/models >/dev/null; then
    echo '✓ Local model ready'
    exit 0
  fi
  sleep 1
done

echo "Local model was not ready within $ready_timeout seconds." >&2
exit 1
