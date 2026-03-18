#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

typeset -a CANDIDATES
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  CANDIDATES+=("$SCRIPT_DIR/.venv/bin/python")
fi
if [[ -x "/opt/anaconda3/bin/python3.12" ]]; then
  CANDIDATES+=("/opt/anaconda3/bin/python3.12")
fi
if command -v python3 >/dev/null 2>&1; then
  CANDIDATES+=("$(command -v python3)")
fi

PYTHON_BIN=""
for candidate in "${CANDIDATES[@]}"; do
  if "$candidate" -c "import streamlit, yaml" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  BOOTSTRAP_BIN=""
  for candidate in "${CANDIDATES[@]}"; do
    if [[ "$candidate" != "$SCRIPT_DIR/.venv/bin/python" ]]; then
      BOOTSTRAP_BIN="$candidate"
      break
    fi
  done

  if [[ -z "$BOOTSTRAP_BIN" ]]; then
    echo "No usable Python interpreter was found."
    exit 1
  fi

  "$BOOTSTRAP_BIN" -m venv "$SCRIPT_DIR/.venv"
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
  "$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
  "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null
fi

exec "$PYTHON_BIN" -m streamlit run "$SCRIPT_DIR/app.py"

