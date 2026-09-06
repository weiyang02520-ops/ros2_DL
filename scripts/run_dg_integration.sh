#!/usr/bin/env bash
set -euo pipefail

integration_ws="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WS_DIR="${WS_DIR:-${integration_ws}}"

exec "${integration_ws}/scripts/run_on_jetson.sh" dg_integration "$@"
