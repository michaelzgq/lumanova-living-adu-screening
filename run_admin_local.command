#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"
export ADU_FORCE_PUBLIC_ONLY="false"
export ADU_ADMIN_PASSWORD="${ADU_ADMIN_PASSWORD:-launchtest}"

exec zsh "./run_app.command"
