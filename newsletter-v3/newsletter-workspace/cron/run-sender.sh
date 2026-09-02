#!/usr/bin/env bash
# run-sender.sh — triggered by cron at EACH <profile>/settings.md -> slot_times
# Executes the SENDER AGENT delivery workflow for ONE profile: retrieves the
# pre-compiled edition from THAT profile's outbox/, verifies eval pass, delivers
# instantly with ZERO writing delay, updates that profile's vault/editions.json,
# and marks the slot DELIVERED in that profile's content_plan.md.
#
# Usage: run-sender.sh --profile <id> [--dry-run]
#
# ISOLATION: the script cd's into profiles/<id>/ before launching the agent and
# INJECTS the recipient address (read from that profile's settings.md) into the
# prompt. The agent never has to guess the recipient and is forbidden from
# touching any other profile's files. If the recipient is missing, we hard-fail.
#
# Delivery uses the Hermes google-workspace skill (google_api.py) which authenticates
# via the persistent OAuth token at ~/.hermes/google_token.json. The token auto-refreshes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
init_cron_env "$@" || exit 1

# --- Recipient resolution: strictly from THIS profile's settings.md ---
RECIPIENT="$(grep -E '^[[:space:]]*email:' settings.md | head -1 | sed -E 's/^[[:space:]]*email:[[:space:]]*//' | tr -d '\"' | tr -d "'" | awk '{print $1}')"

if [ -z "$RECIPIENT" ]; then
  log_msg "ERROR: no 'email' set in profiles/$PROFILE_ID/settings.md — refusing to send. Set the recipient or use email: null + present-file mode."
  [ "$DRY_RUN" = true ] && echo "Dry run: recipient missing (would hard-fail in production)."
  [ "$DRY_RUN" = true ] && exit 0
  exit 1
fi

# --- Google Workspace API path (google-workspace skill) ---
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
GWS_API="$HERMES_HOME/skills/productivity/google-workspace/scripts/google_api.py"

# Verify GWS credentials exist
if [ ! -f "$HERMES_HOME/google_token.json" ]; then
  log_msg "ERROR: Google Workspace token not found at $HERMES_HOME/google_token.json. Run setup first."
  exit 1
fi

# Acquire per-profile lock (30 min max for sender)
if ! acquire_lock "$WS_ROOT/cron/locks/${PROFILE_ID}-sender.lock" 1800 "$DRY_RUN"; then
  exit 0
fi

log_msg "Sender Agent delivery run started for profile '$PROFILE_ID' (recipient: $RECIPIENT)."

# Pre-flight purge (this profile only)
run_preflight_purge

CURRENT_TIME="$(date +%H:%M)"
TODAY="$(date +%Y-%m-%d)"

# Build the sender prompt with GWS integration instructions
SENDER_PROMPT="Workspace boundary: your current working directory is the ENTIRE workspace for profile '$PROFILE_ID'. Treat it as the filesystem root. NEVER read from or write to any path outside it (especially any other profile directory under profiles/). Read content_plan.md, settings.md, and vault/state.json (all relative to your current directory). Match the current time ($CURRENT_TIME) on date $TODAY to the nearest slot_time in settings.md. Role: SENDER AGENT (Step 7). If the slot is DELIVERED or EMPTY, exit quietly. If the slot is SCHEDULED (batch has not produced it yet), log 'slot not ready' and exit cleanly without writing or blocking. If the slot is READY, retrieve outbox/$TODAY/slot-<HHMM>-final.html, verify matching eval pass status in eval/, send the email edition (or present the file if email is null) with ZERO writing latency, re-stamp HTML expiry, run cron/purge-expired.sh with --profile $PROFILE_ID, flip the slot to DELIVERED in content_plan.md, append the delivery record (including \"profile\": \"$PROFILE_ID\" and \"sent_to\": \"$RECIPIENT\") to vault/editions.json, and update vault/state.json. Zero production work allowed. Pass --auto: skip interactive confirmation.

Delivery mode: the ONLY permitted recipient for this profile is: $RECIPIENT (injected from this profile's settings.md). Never send to any other address. Use the Hermes google-workspace skill at $GWS_API to send the HTML edition. Read the outbox HTML file content, then send via: python3 $GWS_API gmail send --to $RECIPIENT --subject '[Newsletter] <headline from content_plan.md>' --body '<html content>' --html. If the GWS script returns an error, fall back to presenting the file to the user. Parse the JSON response for status and id."

if [ "$DRY_RUN" = true ]; then
  log_msg "[DRY-RUN] Would run Sender Agent delivery for profile '$PROFILE_ID' to $RECIPIENT with prompt: $SENDER_PROMPT"
  echo "Dry run completed successfully."
  exit 0
fi

if command -v claude >/dev/null 2>&1; then
  claude -p "$SENDER_PROMPT" >> "$LOG_FILE" 2>&1 || log_msg "Sender run finished with exit code $?"
else
  log_msg "Note: 'claude' CLI not in PATH. Sender prompt ready: $SENDER_PROMPT"
fi

log_msg "Sender Agent delivery run finished for profile '$PROFILE_ID'."
