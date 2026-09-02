#!/usr/bin/env bash
# run-vault-maintenance.sh — weekly vault maintenance and correlation recompute
# Triggered by cron weekly (Sunday 02:00). v5: operates per-profile.
#
# Usage: run-vault-maintenance.sh [--profile <id>]
# With --profile: maintains only that profile's vault.
# Without: loops over every registered profile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(dirname "$SCRIPT_DIR")"
PROFILES_ROOT="$WS_ROOT/profiles"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/vault.log"
LOG_FILE="$LOG_DIR/vault.log"

PROFILE_ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE_ID="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

REGISTRY="$PROFILES_ROOT/registry.json"

if [ -z "$PROFILE_ID" ]; then
  shopt -s nullglob
  for pdir in "$PROFILES_ROOT"/*/; do
    pid="$(basename "$pdir")"
    if [ -f "$REGISTRY" ] && ! grep -q "\"$pid\"" "$REGISTRY"; then
      continue
    fi
    bash "$SCRIPT_DIR/run-vault-maintenance.sh" --profile "$pid" || true
  done
  echo "[$(date -Iseconds)] Vault maintenance sweep across all profiles finished." >> "$LOG_FILE"
  exit 0
fi

if [ -f "$REGISTRY" ] && ! grep -q "\"$PROFILE_ID\"" "$REGISTRY"; then
  echo "ERROR: profile '$PROFILE_ID' is not registered in profiles/registry.json." >&2
  exit 1
fi

WORKSPACE="$PROFILES_ROOT/$PROFILE_ID"
if [ ! -d "$WORKSPACE" ]; then
  echo "ERROR: profile directory missing: $WORKSPACE" >> "$LOG_FILE"
  exit 1
fi

LOCK_FILE="$WS_ROOT/cron/locks/${PROFILE_ID}-vault.lock"
mkdir -p "$WS_ROOT/cron/locks"

cd "$WORKSPACE"

if [ -f "$LOCK_FILE" ]; then
  if [ "$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || stat -f %m "$LOCK_FILE" 2>/dev/null || echo 0) ))" -gt 3600 ]; then
    rm -f "$LOCK_FILE"
  else
    echo "[$(date -Iseconds)] [$PROFILE_ID] Skipping: vault maintenance already running." >> "$LOG_FILE"
    exit 0
  fi
fi
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

echo "[$(date -Iseconds)] [$PROFILE_ID] Vault maintenance started." >> "$LOG_FILE"

# 1. Run HTML purge (this profile only)
bash "$WS_ROOT/cron/purge-expired.sh" --profile "$PROFILE_ID" >> "$LOG_FILE" 2>&1 || true

# 2. Vault maintenance prompt (profile-bounded)
MAINTENANCE_PROMPT="Workspace boundary: your current working directory is the ENTIRE workspace for profile '$PROFILE_ID'. Treat it as the filesystem root; NEVER read or write any path outside it (especially other profile directories). Run Vault Manager weekly maintenance: 1) Ingest unprocessed vault/inbox.json items. 2) Recompute vault/knowledge-map.json correlations and knowledge gaps. 3) Rewrite vault/learning-profile.md. 4) Verify vault/state.json counters match vault/editions.json history."

if command -v claude >/dev/null 2>&1; then
  claude -p "$MAINTENANCE_PROMPT" >> "$LOG_FILE" 2>&1 || echo "[$(date -Iseconds)] [$PROFILE_ID] Vault maintenance completed with code $?" >> "$LOG_FILE"
else
  echo "[$(date -Iseconds)] [$PROFILE_ID] Note: 'claude' CLI not installed in path. Prompt: $MAINTENANCE_PROMPT" >> "$LOG_FILE"
fi

echo "[$(date -Iseconds)] [$PROFILE_ID] Vault maintenance finished." >> "$LOG_FILE"
