#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"
export ADU_FORCE_PUBLIC_ONLY="true"
unset ADU_ADMIN_PASSWORD || true

exec zsh "./run_app.command"
