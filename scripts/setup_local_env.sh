#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3.10}"
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/.venv}"
CONDA_ENV_DIR="${CONDA_ENV_DIR:-$PROJECT_ROOT/.conda-env}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
INSTALL_PROFILE="${INSTALL_PROFILE:-local}"

setup_with_venv() {
  if [ ! -x "$PYTHON_BIN" ]; then
    return 1
  fi

  if ! "$PYTHON_BIN" -c "import ensurepip" >/dev/null 2>&1; then
    return 1
  fi

  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

setup_with_conda() {
  if ! command -v conda >/dev/null 2>&1; then
    echo "未找到 conda，且系统 Python 3.10 无法创建 venv。" >&2
    exit 1
  fi

  if [ ! -x "$CONDA_ENV_DIR/bin/python" ]; then
    conda create -y -p "$CONDA_ENV_DIR" python=3.10
  fi

  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate "$CONDA_ENV_DIR"
}

if ! setup_with_venv; then
  echo "系统 Python 3.10 无法创建 venv，改用 conda 环境..." >&2
  setup_with_conda
fi

AIOS_REQUIREMENTS_FILE="$PROJECT_ROOT/aios/requirements.txt"
CEREBRUM_REQUIREMENTS_FILE="$PROJECT_ROOT/cerebrum/requirements.txt"
TMP_AIOS_REQUIREMENTS=""
TMP_CEREBRUM_REQUIREMENTS=""

cleanup_tmp_requirements() {
  if [ -n "$TMP_AIOS_REQUIREMENTS" ] && [ -f "$TMP_AIOS_REQUIREMENTS" ]; then
    rm -f "$TMP_AIOS_REQUIREMENTS"
  fi

  if [ -n "$TMP_CEREBRUM_REQUIREMENTS" ] && [ -f "$TMP_CEREBRUM_REQUIREMENTS" ]; then
    rm -f "$TMP_CEREBRUM_REQUIREMENTS"
  fi
}

trap cleanup_tmp_requirements EXIT

if [ "$INSTALL_PROFILE" = "local" ]; then
  TMP_AIOS_REQUIREMENTS="$(mktemp)"
  TMP_CEREBRUM_REQUIREMENTS="$(mktemp)"

  # 本机启动不需要 llama_index 的整套 OpenAI 生态，也不需要比赛时的 datasets/autogen 依赖。
  grep -v '^llama_index==' "$AIOS_REQUIREMENTS_FILE" > "$TMP_AIOS_REQUIREMENTS"
  grep -Ev '^(mcp|datasets|autogen-agentchat)$' "$CEREBRUM_REQUIREMENTS_FILE" > "$TMP_CEREBRUM_REQUIREMENTS"

  AIOS_REQUIREMENTS_FILE="$TMP_AIOS_REQUIREMENTS"
  CEREBRUM_REQUIREMENTS_FILE="$TMP_CEREBRUM_REQUIREMENTS"
fi

python -m pip install --index-url "$PIP_INDEX_URL" --upgrade pip setuptools wheel
python -m pip install --index-url "$PIP_INDEX_URL" \
  -r "$AIOS_REQUIREMENTS_FILE" \
  -r "$CEREBRUM_REQUIREMENTS_FILE"
python -m pip install --index-url "$PIP_INDEX_URL" --no-deps -e "$PROJECT_ROOT/cerebrum"

echo
if [ -n "${CONDA_PREFIX:-}" ]; then
  echo "本地环境已准备完成：$CONDA_PREFIX"
else
  echo "本地环境已准备完成：$VENV_DIR"
fi
echo "下一步可运行：$PROJECT_ROOT/scripts/start_local_kernel.sh"
