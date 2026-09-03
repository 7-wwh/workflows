#!/usr/bin/env bash
# sync-cron.sh — synchronizes Hermes Cron and system crontab from settings.md
# Part of the newsletter-v3 workflow (Hermes Agent Scheduled Tasks)
#
# Usage:
#   bash sync-cron.sh [--profile <id>] [--dry-run] [--system-only]
#   bash sync-cron.sh --check [--profile <id>]
#   bash sync-cron.sh --uninstall [--profile <id>]
#
# Self-relative path derivation (Portability Rule 1):
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3 || echo "python3")"

exec "$PYTHON_BIN" "$SCRIPT_DIR/manage_cron.py" sync "$@"
