#!/usr/bin/env bash
# run-batch.sh — triggered by cron at <profile>/settings.md -> batch_time (default 03:00)
# Executes the INTERMEDIATE AGENT batch workflow for ONE profile: research, write,
# evaluate, and export all scheduled editions for today to that profile's outbox/
# with status READY. Zero sending is performed in this step.
#
# Usage: run-batch.sh --profile <id> [--dry-run]
#
# ISOLATION: the script cd's into profiles/<id>/ before launching the agent. The
# agent's entire world is that directory. It must never read or write any other
# profile's directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
init_cron_env "$@" || exit 1

# Acquire per-profile lock (2 hours max for batch)
if ! acquire_lock "$WS_ROOT/cron/locks/${PROFILE_ID}-batch.lock" 7200 "$DRY_RUN"; then
  exit 0
fi

log_msg "Intermediate Agent nightly batch started for profile '$PROFILE_ID'."

# Pre-flight purge (this profile only)
run_preflight_purge

TODAY="$(date +%Y-%m-%d)"
BATCH_PROMPT="Workspace boundary: your current working directory is the ENTIRE workspace for profile '$PROFILE_ID'. Treat it as the filesystem root. NEVER read from or write to any path outside it (especially any other profile directory under profiles/). The only exceptions are shared/scripts/ (read-only) and cron/ logs (append-only). Read settings.md, vault/state.json, and content_plan.md (all relative to your current directory). Execute the INTERMEDIATE AGENT batch workflow (Steps 4–6) for ALL slots scheduled for today ($TODAY). Step 4: Dispatch PARALLEL Researcher subagents concurrently across all scheduled slots to generate research/$TODAY-slot-<HHMM>.json simultaneously. Steps 5–6: For each slot, draft structured content JSON (content/$TODAY-slot-<HHMM>.json), assemble HTML draft via shared/scripts/assemble_edition.py, run fresh Evaluator subagent with JSON patches (eval/$TODAY-slot-<HHMM>-eval.json), compile final HTML with patches, export to outbox/$TODAY/slot-<HHMM>-final.html, flip slot status to READY in content_plan.md, and record batch details (including \"profile\": \"$PROFILE_ID\") in runs/batch-$TODAY.json. NEVER send or email anyone. Pass --auto: skip interactive confirmation."

if [ "$DRY_RUN" = true ]; then
  log_msg "[DRY-RUN] Would run Intermediate Agent batch for profile '$PROFILE_ID' with prompt: $BATCH_PROMPT"
  echo "Dry run completed successfully."
  exit 0
fi

if command -v claude >/dev/null 2>&1; then
  claude -p "$BATCH_PROMPT" >> "$LOG_FILE" 2>&1 || log_msg "Intermediate batch finished with exit code $?"
else
  log_msg "Note: 'claude' CLI not in PATH. Batch prompt ready: $BATCH_PROMPT"
fi

log_msg "Intermediate Agent nightly batch finished for profile '$PROFILE_ID'."
