#!/usr/bin/env bash
# 一键启动 AutoSim Web（包装 run_web.py）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

# 把便携 Node 放进 PATH（若存在）
if [[ -d "$HOME/.local/node/bin" ]]; then
  export PATH="$HOME/.local/node/bin:$PATH"
fi

exec "$PY" "$ROOT/run_web.py" "$@"
