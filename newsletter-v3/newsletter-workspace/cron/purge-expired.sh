#!/usr/bin/env bash
# purge-expired.sh — automated artifact retention & expiry manager
# Purges transient pipeline artifacts (html/, outbox/, research/, eval/, runs/)
# older than settings.md -> artifact_retention_days (default 7 days).
#
# HARD SAFETY INVARIANTS:
# 1. NEVER deletes vault/ (knowledge-map, learning-profile, editions, state, followups)
# 2. NEVER deletes settings.md, config.json, content_plan.md, or plan.json
# 3. NEVER deletes base templates in assets/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(dirname "$SCRIPT_DIR")"
PROFILES_ROOT="$WS_ROOT/profiles"
LOG="$SCRIPT_DIR/logs/purge.log"
mkdir -p "$SCRIPT_DIR/logs"

# ─── Profile resolution (v5) ───
# Usage: purge-expired.sh [--profile <id>]
# With --profile: purges only that profile's transient artifacts.
# Without: loops over every profile directory (registry-validated when present).

PROFILE_ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE_ID="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

REGISTRY="$PROFILES_ROOT/registry.json"

if [ -z "$PROFILE_ID" ]; then
  touch "$LOG"
  shopt -s nullglob
  for pdir in "$PROFILES_ROOT"/*/; do
    pid="$(basename "$pdir")"
    if [ -f "$REGISTRY" ] && ! grep -q "\"$pid\"" "$REGISTRY"; then
      continue  # skip unregistered/ghost dirs
    fi
    bash "$SCRIPT_DIR/purge-expired.sh" --profile "$pid" || true
  done
  echo "[$(date -Iseconds)] Purge sweep across all profiles complete." >> "$LOG"
  exit 0
fi

if [ -f "$REGISTRY" ] && ! grep -q "\"$PROFILE_ID\"" "$REGISTRY"; then
  echo "ERROR: profile '$PROFILE_ID' is not registered in profiles/registry.json." >&2
  exit 1
fi

WORKSPACE="$PROFILES_ROOT/$PROFILE_ID"
if [ ! -d "$WORKSPACE" ]; then
  echo "ERROR: profile directory missing: $WORKSPACE" >&2
  exit 1
fi

SETTINGS_FILE="$WORKSPACE/settings.md"

NOW_EPOCH="$(date +%s)"
touch "$LOG"

# Read retention days from settings.md (check artifact_retention_days, then html_expiry_days)
RETENTION_DAYS=7
if [ -f "$SETTINGS_FILE" ]; then
  PARSED_DAYS="$(grep -E '^[[:space:]]*artifact_retention_days:' "$SETTINGS_FILE" | head -1 | awk '{print $2}' | tr -d ' ' || true)"
  if [ -z "$PARSED_DAYS" ]; then
    PARSED_DAYS="$(grep -E '^[[:space:]]*html_expiry_days:' "$SETTINGS_FILE" | head -1 | awk '{print $2}' | tr -d ' ' || true)"
  fi
  if [[ "$PARSED_DAYS" =~ ^[0-9]+$ ]]; then
    RETENTION_DAYS="$PARSED_DAYS"
  fi
fi

if [ "$RETENTION_DAYS" -eq 0 ]; then
  echo "[$(date -Iseconds)] Retention set to 0 (keep forever). Purge skipped." >> "$LOG"
  exit 0
fi

RETENTION_SECONDS=$(( RETENTION_DAYS * 86400 ))
CUTOFF_EPOCH=$(( NOW_EPOCH - RETENTION_SECONDS ))

echo "[$(date -Iseconds)] Purge scan started (retention: ${RETENTION_DAYS} days, cutoff: $(date -d "@$CUTOFF_EPOCH" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -r "$CUTOFF_EPOCH" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "$CUTOFF_EPOCH"))." >> "$LOG"

# ─── 1. Purge HTML drafts & direct-edits (html/) ───
HTML_DIR="$WORKSPACE/html"
if [ -d "$HTML_DIR" ]; then
  shopt -s nullglob
  for f in "$HTML_DIR"/*.html; do
    base="$(basename "$f")"
    case "$base" in
      *-template.html|template-*.html) continue ;;
    esac

    # Check embedded expiry marker first
    expiry="$(sed -n 's/.*newsletter-expiry:[[:space:]]*\([^>]*\)-->.*/\1/p' "$f" | head -1 | tr -d '[:space:]' || true)"
    if [ -n "$expiry" ] && [ "$expiry" != "never" ]; then
      expiry_epoch="$(date -d "$expiry" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S%z" "$expiry" +%s 2>/dev/null || echo 0)"
      if [ "$expiry_epoch" -gt 0 ] && [ "$NOW_EPOCH" -ge "$expiry_epoch" ]; then
        rm -f "$f"
        echo "[$(date -Iseconds)] DELETED html/$base — expired marker ($expiry)" >> "$LOG"
        continue
      fi
    fi

    # Check file modification time against retention cutoff
    mtime="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo "$NOW_EPOCH")"
    if [ "$mtime" -lt "$CUTOFF_EPOCH" ]; then
      rm -f "$f"
      echo "[$(date -Iseconds)] DELETED html/$base — older than ${RETENTION_DAYS} days" >> "$LOG"
    fi
  done
fi

# ─── 2. Purge Outbox deliverables (outbox/) ───
OUTBOX_DIR="$WORKSPACE/outbox"
if [ -d "$OUTBOX_DIR" ]; then
  shopt -s nullglob
  for date_dir in "$OUTBOX_DIR"/*; do
    if [ -d "$date_dir" ]; then
      dir_name="$(basename "$date_dir")"
      dir_epoch="$(date -d "$dir_name" +%s 2>/dev/null || echo 0)"
      if [ "$dir_epoch" -gt 0 ] && [ "$dir_epoch" -lt "$CUTOFF_EPOCH" ]; then
        rm -rf "$date_dir"
        echo "[$(date -Iseconds)] DELETED outbox/$dir_name/ — older than ${RETENTION_DAYS} days" >> "$LOG"
      fi
    fi
  done
fi

# ─── 3. Purge Research dumps (research/) ───
RESEARCH_DIR="$WORKSPACE/research"
if [ -d "$RESEARCH_DIR" ]; then
  shopt -s nullglob
  for f in "$RESEARCH_DIR"/*.json; do
    mtime="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo "$NOW_EPOCH")"
    if [ "$mtime" -lt "$CUTOFF_EPOCH" ]; then
      rm -f "$f"
      echo "[$(date -Iseconds)] DELETED research/$(basename "$f") — older than ${RETENTION_DAYS} days" >> "$LOG"
    fi
  done
fi

# ─── 4. Purge Evaluation dumps (eval/) ───
EVAL_DIR="$WORKSPACE/eval"
if [ -d "$EVAL_DIR" ]; then
  shopt -s nullglob
  for f in "$EVAL_DIR"/*; do
    base="$(basename "$f")"
    # Never delete active plan evaluation
    [ "$base" = "plan-eval.json" ] && continue

    mtime="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo "$NOW_EPOCH")"
    if [ "$mtime" -lt "$CUTOFF_EPOCH" ]; then
      rm -f "$f"
      echo "[$(date -Iseconds)] DELETED eval/$base — older than ${RETENTION_DAYS} days" >> "$LOG"
    fi
  done
fi

# ─── 5. Purge Old Run Manifests & Reports (runs/) ───
RUNS_DIR="$WORKSPACE/runs"
RUNS_CUTOFF_EPOCH=$(( NOW_EPOCH - (RETENTION_DAYS * 2 * 86400) )) # Keep run reports for 2x retention window
if [ -d "$RUNS_DIR" ]; then
  shopt -s nullglob
  for f in "$RUNS_DIR"/*; do
    [ -d "$f" ] && continue
    mtime="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo "$NOW_EPOCH")"
    if [ "$mtime" -lt "$RUNS_CUTOFF_EPOCH" ]; then
      rm -f "$f"
      echo "[$(date -Iseconds)] DELETED runs/$(basename "$f") — older than $(( RETENTION_DAYS * 2 )) days" >> "$LOG"
    fi
  done
fi

echo "[$(date -Iseconds)] Purge scan complete. Vault and live state intact." >> "$LOG"