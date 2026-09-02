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
    --batch|--send|--help|-h)
      MODE="$1"; shift ;;
    --profile)
      PROFILE_ARG="--profile $2"; REST+=(--profile "$2"); shift 2 ;;
    *)
      REST+=("$1"); shift ;;
  esac
done

case "${MODE:-}" in
  --batch)
    exec bash "$SCRIPT_DIR/run-batch.sh" ${PROFILE_ARG} "${REST[@]:-}"
    ;;
  --send|"")
    exec bash "$SCRIPT_DIR/run-sender.sh" ${PROFILE_ARG} "${REST[@]:-}"
    ;;
  --help|-h)
    echo "Usage: run-newsletter.sh --profile <id> [--batch | --send | --dry-run]"
    echo "  --profile <id>  Target profile (optional if exactly one profile is registered)"
    echo "  --batch         Run Intermediate Agent batch production for the profile"
    echo "  --send          Run Sender Agent delivery for the profile (default)"
    exit 0
    ;;
esac
