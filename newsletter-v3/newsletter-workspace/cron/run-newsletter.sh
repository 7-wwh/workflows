#!/usr/bin/env bash
# run-newsletter.sh — unified CLI wrapper for newsletter cron tasks (v5 multi-profile)
# Usage:
#   bash run-newsletter.sh --profile <id> --batch    # Runs Intermediate Agent production for one profile
#   bash run-newsletter.sh --profile <id> --send     # Runs Sender Agent delivery for one profile
#   bash run-newsletter.sh --profile <id> --dry-run  # Dry-run (implies --send)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE=""
PROFILE_ARG=""
REST=()
while [ $# -gt 0 ]; do
  case "$1" in
    --batch|--send|--sync-cron|--maintain|--summary|-s|--help|-h)
      MODE="$1"; shift ;;
    --profile)
      PROFILE_ARG="--profile $2"; REST+=(--profile "$2"); shift 2 ;;
    *)
      REST+=("$1"); shift ;;
  esac
done

case "${MODE:-}" in
  --batch)
    if [ ${#REST[@]} -gt 0 ]; then
      exec bash "$SCRIPT_DIR/run-batch.sh" "${REST[@]}"
    else
      exec bash "$SCRIPT_DIR/run-batch.sh"
    fi
    ;;
  --send|"")
    if [ ${#REST[@]} -gt 0 ]; then
      exec bash "$SCRIPT_DIR/run-sender.sh" "${REST[@]}"
    else
      exec bash "$SCRIPT_DIR/run-sender.sh"
    fi
    ;;
  --sync-cron)
    if [ ${#REST[@]} -gt 0 ]; then
      exec bash "$SCRIPT_DIR/sync-cron.sh" "${REST[@]}"
    else
      exec bash "$SCRIPT_DIR/sync-cron.sh"
    fi
    ;;
  --maintain)
    if [ ${#REST[@]} -gt 0 ]; then
      exec bash "$SCRIPT_DIR/maintain-cron.sh" "${REST[@]}"
    else
      exec bash "$SCRIPT_DIR/maintain-cron.sh"
    fi
    ;;
  --summary|-s)
    if [ ${#REST[@]} -gt 0 ]; then
      exec python3 "$SCRIPT_DIR/cron-summary.py" "${REST[@]}"
    else
      exec python3 "$SCRIPT_DIR/cron-summary.py"
    fi
    ;;

  --help|-h)
    echo "Usage: run-newsletter.sh [--profile <id>] [--batch | --send | --summary | --sync-cron | --maintain | --dry-run]"
    echo "  --profile <id>  Target profile (optional if exactly one profile is registered)"
    echo "  --batch         Run Intermediate Agent batch production for the profile"
    echo "  --send          Run Sender Agent delivery for the profile (default)"
    echo "  --summary, -s   Show cron & delivery queue summary (.json and table)"
    echo "  --sync-cron     Sync Hermes cron jobs and system crontab from settings.md"
    echo "  --maintain      Run nightly maintain mode (drift check, auto-repair, stale lock cleanup)"
    exit 0
    ;;
esac

