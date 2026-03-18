#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"
python3 tools/prepare_google_sheets_setup.py
