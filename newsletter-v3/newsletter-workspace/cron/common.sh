#!/usr/bin/env bash
# common.sh — shared helper library for newsletter cron runner scripts (v5 multi-profile)
# Provides: profile resolution/validation, lock management, stale lock recovery, preflight.
#
# Profile model (v5):
#   newsletter-workspace/
#   ├── profiles/<profile-id>/     ← self-contained workspace (settings.md, vault/, outbox/, ...)
#   ├── profiles/registry.json     ← canonical list of profiles
#   └── cron/                      ← shared, profile-aware runners + logs/
#
# Every runner accepts:  --profile <id>  (required)  and  --dry-run (optional).
# The runner cd's INTO the profile workspace before launching any agent, so all
# agent-facing relative paths (settings.md, vault/state.json, ...) resolve inside
# that profile only. Agents never see another profile's files.

set -euo pipefail

# Resolve + validate the profile and set up the environment. Args are the
# runner script's own arguments. Returns 1 (after logging) on any failure.
init_cron_env() {
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
  WS_ROOT="$(dirname "$SCRIPT_DIR")"
  PROFILE_ID=""
  DRY_RUN=false

  while [ $# -gt 0 ]; do
    case "$1" in
      --profile) PROFILE_ID="${2:-}"; shift 2 ;;
      --dry-run) DRY_RUN=true; shift ;;
      *) shift ;;
    esac
  done

  LOG_DIR="$WS_ROOT/cron/logs"
  mkdir -p "$LOG_DIR"

  # Fallback: if exactly one profile is registered, allow omitting --profile
  if [ -z "$PROFILE_ID" ] && [ -f "$WS_ROOT/profiles/registry.json" ]; then
    SOLE="$(grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' "$WS_ROOT/profiles/registry.json" | sed 's/.*"\([^"]*\)"$/\1/' | sort -u)"
    if [ "$(echo "$SOLE" | grep -c .)" -eq 1 ]; then
      PROFILE_ID="$SOLE"
    fi
  fi

  if [ -z "$PROFILE_ID" ]; then
    echo "[$(date -Iseconds)] ERROR: --profile <id> is required (multiple profiles registered, none specified)." >> "$LOG_DIR/global.log" 2>/dev/null || true
    echo "ERROR: --profile <id> is required." >&2
    return 1
  fi

  REGISTRY="$WS_ROOT/profiles/registry.json"
  PROFILE_WS="$WS_ROOT/profiles/$PROFILE_ID"
  PROFILE_LOG="$LOG_DIR/${PROFILE_ID}.log"

  if [ ! -f "$REGISTRY" ] || ! grep -q "\"$PROFILE_ID\"" "$REGISTRY"; then
    echo "ERROR: profile '$PROFILE_ID' is not registered in profiles/registry.json." >&2
    return 1
  fi
  if [ ! -d "$PROFILE_WS" ]; then
    echo "ERROR: profile directory missing: $PROFILE_WS" >&2
    return 1
  fi

  LOG_FILE="$PROFILE_LOG"
  cd "$PROFILE_WS"
  return 0
}

# Centralized lock acquisition with stale lock detection (per-profile locks)
acquire_lock() {
  local lock_file="$1"
  local max_age_seconds="${2:-3600}" # default 1 hour
  local is_dry_run="${3:-false}"

  if [ -f "$lock_file" ]; then
    local lock_mtime
    lock_mtime=$(stat -c %Y "$lock_file" 2>/dev/null || stat -f %m "$lock_file" 2>/dev/null || echo 0)
    local lock_age=$(( $(date +%s) - lock_mtime ))

    if [ "$lock_age" -gt "$max_age_seconds" ]; then
      echo "[$(date -Iseconds)] WARN: Removing stale lock file $(basename "$lock_file") (age: ${lock_age}s > ${max_age_seconds}s)." >> "$LOG_FILE"
      rm -f "$lock_file"
    else
      echo "[$(date -Iseconds)] Skipping execution: previous run still active ($(basename "$lock_file") age: ${lock_age}s)." >> "$LOG_FILE"
      return 1
    fi
  fi

  if [ "$is_dry_run" = false ]; then
    touch "$lock_file"
    trap 'rm -f "$lock_file"' EXIT
  fi
  return 0
}

# Pre-flight HTML expiry cleanup (scoped to the current profile unless --all)
run_preflight_purge() {
  bash "$WS_ROOT/cron/purge-expired.sh" --profile "$PROFILE_ID" >> "$LOG_FILE" 2>&1 || true
}

# Timestamped logging helper
log_msg() {
  local msg="$1"
  echo "[$(date -Iseconds)] $msg" >> "$LOG_FILE"
}
