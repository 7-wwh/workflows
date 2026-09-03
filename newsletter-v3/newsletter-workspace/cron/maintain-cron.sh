#!/usr/bin/env bash
# maintain-cron.sh — nightly maintain runner for newsletter-v3 workflow
# Triggered by Hermes Cron / system cron nightly (default 02:30).
#
# Inspects settings.md vs active schedules for all profiles,
# detects drift, auto-repairs missing/outdated jobs, sweeps stale locks,
# verifies permissions, and records results in cron/logs/maintain.log.
#
# Usage:
#   bash maintain-cron.sh [--profile <id>] [--no-repair]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3 || echo "python3")"

exec "$PYTHON_BIN" "$SCRIPT_DIR/manage_cron.py" maintain "$@"
