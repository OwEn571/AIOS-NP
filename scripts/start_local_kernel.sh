#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
if [ -x "$PROJECT_ROOT/.conda-env/bin/python" ]; then
  DEFAULT_PYTHON_BIN="$PROJECT_ROOT/.conda-env/bin/python"
fi
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON_BIN}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "未找到本地 Python 环境：$PYTHON_BIN" >&2
  echo "请先运行 ./scripts/setup_local_env.sh" >&2
  exit 1
fi

if [ -f "$PROJECT_ROOT/.env.local" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env.local"
  set +a
fi

export PATH="$(dirname "$PYTHON_BIN"):$PATH"
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
export AIOS_NP_DATA_DIR="${AIOS_NP_DATA_DIR:-$PROJECT_ROOT}"
export AIOS_NP_ROOT_DIR="${AIOS_NP_ROOT_DIR:-$PROJECT_ROOT/root}"
export CEREBRUM_ROOT_DIR="${CEREBRUM_ROOT_DIR:-$PROJECT_ROOT/root}"
export CEREBRUM_KERNEL_URL="${CEREBRUM_KERNEL_URL:-http://localhost:8001}"

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -m runtime.launch
