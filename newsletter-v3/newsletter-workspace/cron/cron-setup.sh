#!/usr/bin/env bash
# cron-setup.sh — Automated cron scheduler installer/synchroniser for newsletter skill (v5 multi-profile)
# Reads batch_time, slot_times, delivery_days, and timezone from profiles/<id>/settings.md,
# generates cron expressions, and installs per-profile, tagged cron entries.
#
# Usage:
#   cron-setup.sh --profile <id> [--install|--remove|--dry-run|--systemd]
#   --profile <id>  Required unless exactly one profile is registered
#   --install       Install/update cron entries (default)
#   --remove        Remove this profile's cron entries
#   --dry-run       Show what would be installed without writing
#   --systemd       Generate systemd .timer/.service units instead of crontab (Linux)
#
# Portability: self-relative paths only (see cron-setup.md § Portability Rules).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(dirname "$SCRIPT_DIR")"
PROFILES_ROOT="$WS_ROOT/profiles"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# ─── Argument parsing ─────────────────────────────────────────────────────────

PROFILE_ID=""
ACTION="install"
USE_SYSTEMD=false

while [ $# -gt 0 ]; do
  case "$1" in
    --profile)  PROFILE_ID="${2:-}"; shift 2 ;;
    --install)  ACTION="install"; shift ;;
    --remove)   ACTION="remove"; shift ;;
    --dry-run)  ACTION="dry-run"; shift ;;
    --systemd)  USE_SYSTEMD=true; shift ;;
    --help|-h)
      echo "Usage: cron-setup.sh --profile <id> [--install|--remove|--dry-run] [--systemd]"
      echo "  --profile <id>   Target profile (required unless one profile registered)"
      echo "  --install       Install or update cron entries (default)"
      echo "  --remove        Remove this profile's cron entries"
      echo "  --dry-run       Show what would be installed without writing"
      echo "  --systemd       Generate systemd timer/service units instead of crontab"
      exit 0
      ;;
    *)          shift ;;
  esac
done

# ─── Profile resolution ───────────────────────────────────────────────────────

REGISTRY="$PROFILES_ROOT/registry.json"

if [ -z "$PROFILE_ID" ] && [ -f "$REGISTRY" ]; then
  SOLE="$(grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' "$REGISTRY" | sed 's/.*"\([^"]*\)"$/\1/' | sort -u)"
  if [ "$(echo "$SOLE" | grep -c .)" -eq 1 ]; then
    PROFILE_ID="$SOLE"
  fi
fi

if [ -z "$PROFILE_ID" ]; then
  echo "ERROR: --profile <id> is required (multiple profiles registered, none specified)." >&2
  exit 1
fi

if [ -f "$REGISTRY" ] && ! grep -q "\"$PROFILE_ID\"" "$REGISTRY"; then
  echo "ERROR: profile '$PROFILE_ID' is not registered in profiles/registry.json." >&2
  exit 1
fi

PROFILE_WS="$PROFILES_ROOT/$PROFILE_ID"
if [ ! -d "$PROFILE_WS" ]; then
  echo "ERROR: profile directory missing: $PROFILE_WS" >&2
  exit 1
fi

SETTINGS_FILE="$PROFILE_WS/settings.md"
if [ ! -f "$SETTINGS_FILE" ]; then
  echo "ERROR: settings.md not found at $SETTINGS_FILE" >&2
  exit 1
fi

# ─── Parse settings.md ────────────────────────────────────────────────────────

# Parse a scalar value from settings.md
settings_value() {
  local key="$1"
  grep -E "^[[:space:]]*${key}:" "$SETTINGS_FILE" | head -1 | sed -E "s/^[[:space:]]*${key}:[[:space:]]*//; s/[[:space:]]*#.*$//" | tr -d '"'\'
}

# Parse a JSON-array-style value like ["08:00", "13:00", "18:00"] -> space-separated items
parse_array() {
  local raw
  raw="$(settings_value "$1")"
  echo "$raw" | sed 's/\[//; s/\]//; s/"//g; s/,/ /g'
}

# Day-of-week mapping: mon=1, tue=2, wed=3, thu=4, fri=5, sat=6, sun=0/7
day_to_cron_dow() {
  local days
  days="$(parse_array "delivery_days")"
  local result=""
  for d in $days; do
    case "$d" in
      sun|Sun|SUN) result="${result}0," ;;
      mon|Mon|MON) result="${result}1," ;;
      tue|Tue|TUE) result="${result}2," ;;
      wed|Wed|WED) result="${result}3," ;;
      thu|Thu|THU) result="${result}4," ;;
      fri|Fri|FRI) result="${result}5," ;;
      sat|Sat|SAT) result="${result}6," ;;
    esac
  done
  echo "$result" | sed 's/,$//'
}

# Extract HH:MM -> returns "min hour" (minutes as integer, no leading zero)
time_to_cron() {
  local t="$1"
  local hh mm
  hh="${t%%:*}"
  mm="${t##*:}"
  mm=$((10#$mm))
  echo "$mm $hh"
}

# ─── Read settings values ─────────────────────────────────────────────────────

BATCH_TIME="$(settings_value "batch_time")"
SLOT_TIMES_RAW="$(parse_array "slot_times")"
DELIVERY_DAYS="$(day_to_cron_dow)"
TIMEZONE="$(settings_value "timezone")"
RETENTION_DAYS="$(settings_value "artifact_retention_days")"

# Fallbacks
BATCH_TIME="${BATCH_TIME:-03:00}"
DELIVERY_DAYS="${DELIVERY_DAYS:-0,1,2,3,4,5,6}"
TIMEZONE="${TIMEZONE:-UTC}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# ─── Generate cron schedule expressions ───────────────────────────────────────

# 1. Batch job: once daily at batch_time, on delivery_days
BATCH_MIN_HH="$(time_to_cron "$BATCH_TIME")"
BATCH_MIN="${BATCH_MIN_HH% *}"
BATCH_HH="${BATCH_MIN_HH#* }"
BATCH_CRON="$BATCH_MIN $BATCH_HH * * $DELIVERY_DAYS"

# 2. Sender jobs: one entry per slot_time (pre-computed for display + systemd)
SENDER_CRON_LIST=()
for st in $SLOT_TIMES_RAW; do
  MIN_HH="$(time_to_cron "$st")"
  SENDER_MIN="${MIN_HH% *}"
  SENDER_HH="${MIN_HH#* }"
  SENDER_CRON_LIST+=("$SENDER_MIN $SENDER_HH * * $DELIVERY_DAYS")
done

# Consolidate: if all slots share the same minute, use single entry with comma-hours
SENDER_CRON_CONSOLIDATED=""
if [ "${#SENDER_CRON_LIST[@]}" -gt 0 ]; then
  FIRST_MIN_HH="$(time_to_cron "$(echo "$SLOT_TIMES_RAW" | awk '{print $1}')")"
  FIRST_MIN="${FIRST_MIN_HH% *}"

  ALL_HOURS=""
  SAME_MIN=true
  for st in $SLOT_TIMES_RAW; do
    MIN_HH="$(time_to_cron "$st")"
    M="${MIN_HH% *}"
    H="${MIN_HH#* }"
    [ -n "$ALL_HOURS" ] && ALL_HOURS="${ALL_HOURS},"
    ALL_HOURS="${ALL_HOURS}${H}"
    [ "$M" != "$FIRST_MIN" ] && SAME_MIN=false
  done

  if [ "$SAME_MIN" = true ]; then
    SENDER_CRON_CONSOLIDATED="$FIRST_MIN $ALL_HOURS * * $DELIVERY_DAYS"
  fi
fi

# 3. Weekly vault maintenance: Sunday 02:00
VAULT_CRON="0 2 * * 0"

# 4. Daily purge safety net: at batch_time
PURGE_CRON="$BATCH_MIN $BATCH_HH * * $DELIVERY_DAYS"

# ─── Build cron command strings ────────────────────────────────────────────────

BATCH_CMD="$WS_ROOT/cron/run-batch.sh --profile $PROFILE_ID >> $WS_ROOT/cron/logs/${PROFILE_ID}-batch.log 2>&1"
SENDER_CMD="$WS_ROOT/cron/run-sender.sh --profile $PROFILE_ID >> $WS_ROOT/cron/logs/${PROFILE_ID}-sender.log 2>&1"
VAULT_CMD="$WS_ROOT/cron/run-vault-maintenance.sh >> $WS_ROOT/cron/logs/vault.log 2>&1"
PURGE_CMD="$WS_ROOT/cron/purge-expired.sh >> $WS_ROOT/cron/logs/purge.log 2>&1"

CRON_TAG_PREFIX="newsletter-skill:${PROFILE_ID}"

# ─── Remove action ─────────────────────────────────────────────────────────────

if [ "$ACTION" = "remove" ]; then
  if [ "$USE_SYSTEMD" = true ]; then
    echo "Removing systemd units for profile '$PROFILE_ID'..."
    rm -f "$HOME/.config/systemd/user/newsletter-batch-${PROFILE_ID}.service"
    rm -f "$HOME/.config/systemd/user/newsletter-batch-${PROFILE_ID}.timer"
    rm -f "$HOME/.config/systemd/user/newsletter-send-${PROFILE_ID}.service"
    rm -f "$HOME/.config/systemd/user/newsletter-send-${PROFILE_ID}.timer"
    systemctl --user daemon-reload 2>/dev/null || true
    echo "Systemd units for profile '$PROFILE_ID' removed."
  else
    if ! command -v crontab &>/dev/null; then
      echo "ERROR: crontab not available." >&2
      exit 1
    fi
    (crontab -l 2>/dev/null | grep -v "$CRON_TAG_PREFIX" || true) | crontab -
    echo "Cron entries for profile '$PROFILE_ID' removed."
  fi
  exit 0
fi

# ─── Print schedule summary ───────────────────────────────────────────────────

echo "=== Cron Schedule Sync for Profile '$PROFILE_ID' ==="
echo "Settings source: $SETTINGS_FILE"
echo ""
echo "Parsed values:"
echo "  batch_time:     $BATCH_TIME  -> cron: $BATCH_CRON"
echo "  slot_times:     $SLOT_TIMES_RAW"
echo "  delivery_days:  $DELIVERY_DAYS"
echo "  timezone:       $TIMEZONE"
echo "  retention_days: $RETENTION_DAYS"
echo ""
echo "Generated cron entries:"

echo "  Batch:  $BATCH_CRON  # $CRON_TAG_PREFIX-batch"
echo "    -> $BATCH_CMD"

if [ -n "$SENDER_CRON_CONSOLIDATED" ]; then
  echo "  Sender: $SENDER_CRON_CONSOLIDATED  # $CRON_TAG_PREFIX-send"
  echo "    -> $SENDER_CMD"
else
  idx=0
  for entry in "${SENDER_CRON_LIST[@]}"; do
    SLOT_TIME="$(echo "$SLOT_TIMES_RAW" | awk "{print \$$((idx + 1))}")"
    echo "  Sender: $entry  # $CRON_TAG_PREFIX-send-${SLOT_TIME}"
    echo "    -> $SENDER_CMD"
    idx=$((idx + 1))
  done
fi

echo "  Vault:  $VAULT_CRON  # newsletter-skill:vault-all"
echo "    -> $VAULT_CMD"
echo "  Purge:  $PURGE_CRON  # newsletter-skill:purge-all"
echo "    -> $PURGE_CMD"
echo ""

if [ "$ACTION" = "dry-run" ]; then
  echo "[DRY-RUN] No changes made."
  exit 0
fi

# ─── Install ──────────────────────────────────────────────────────────────────

if [ "$USE_SYSTEMD" = true ]; then
  echo "Installing systemd timers for profile '$PROFILE_ID'..."
  SYSTEMD_DIR="$HOME/.config/systemd/user"
  mkdir -p "$SYSTEMD_DIR"

  cat > "$SYSTEMD_DIR/newsletter-batch-${PROFILE_ID}.service" <<EOF
[Unit]
Description=Newsletter Batch Production (${PROFILE_ID})
Wants=newsletter-batch-${PROFILE_ID}.timer

[Service]
Type=oneshot
WorkingDirectory=$PROFILE_WS
ExecStart=$SCRIPT_DIR/run-batch.sh --profile $PROFILE_ID
EOF

  cat > "$SYSTEMD_DIR/newsletter-batch-${PROFILE_ID}.timer" <<EOF
[Unit]
Description=Newsletter Nightly Batch (${PROFILE_ID})

[Timer]
OnCalendar=*-*-* ${BATCH_HH}:${BATCH_MIN}:00
Persistent=true
EOF

  cat > "$SYSTEMD_DIR/newsletter-send-${PROFILE_ID}.service" <<EOF
[Unit]
Description=Newsletter Sender Delivery (${PROFILE_ID})
Wants=newsletter-send-${PROFILE_ID}.timer

[Service]
Type=oneshot
WorkingDirectory=$PROFILE_WS
ExecStart=$SCRIPT_DIR/run-sender.sh --profile $PROFILE_ID
EOF

  SENDER_CALENDAR=""
  for st in $SLOT_TIMES_RAW; do
    MIN_HH="$(time_to_cron "$st")"
    M="${MIN_HH% *}"
    H="${MIN_HH#* }"
    [ -n "$SENDER_CALENDAR" ] && SENDER_CALENDAR="${SENDER_CALENDAR} "
    SENDER_CALENDAR="${SENDER_CALENDAR}*-*-* ${H}:${M}:00"
  done

  cat > "$SYSTEMD_DIR/newsletter-send-${PROFILE_ID}.timer" <<EOF
[Unit]
Description=Newsletter Sender Delivery (${PROFILE_ID})

[Timer]
OnCalendar=$SENDER_CALENDAR
Persistent=true
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now "newsletter-batch-${PROFILE_ID}.timer"
  systemctl --user enable --now "newsletter-send-${PROFILE_ID}.timer"
  echo "Systemd timers installed and enabled."
  echo "  Batch:  $(systemctl --user list-timers "newsletter-batch-${PROFILE_ID}.timer" --no-pager 2>/dev/null)"
  echo "  Sender: $(systemctl --user list-timers "newsletter-send-${PROFILE_ID}.timer" --no-pager 2>/dev/null)"
  echo ""
  echo "Timezone: $TIMEZONE (set with: timedatectl set-timezone $TIMEZONE)"
  exit 0
fi

# crontab install path
if ! command -v crontab &>/dev/null; then
  echo "ERROR: crontab not available. Use --systemd for Linux systemd timer support." >&2
  exit 1
fi

(
  crontab -l 2>/dev/null | grep -v "$CRON_TAG_PREFIX" || true

  TZ_LINE="CRON_TZ=$TIMEZONE"
  if ! crontab -l 2>/dev/null | grep -q "^CRON_TZ="; then
    echo "$TZ_LINE"
  fi

  echo "$BATCH_CRON $BATCH_CMD  # $CRON_TAG_PREFIX-batch"

  if [ -n "$SENDER_CRON_CONSOLIDATED" ]; then
    echo "$SENDER_CRON_CONSOLIDATED $SENDER_CMD  # $CRON_TAG_PREFIX-send"
  else
    idx=0
    for entry in "${SENDER_CRON_LIST[@]}"; do
      SLOT_TIME="$(echo "$SLOT_TIMES_RAW" | awk "{print \$$((idx + 1))}")"
      echo "$entry $SENDER_CMD  # $CRON_TAG_PREFIX-send-${SLOT_TIME}"
      idx=$((idx + 1))
    done
  fi

  if ! crontab -l 2>/dev/null | grep -q "newsletter-skill:vault-all"; then
    echo "$VAULT_CRON $VAULT_CMD  # newsletter-skill:vault-all"
  fi
  if ! crontab -l 2>/dev/null | grep -q "newsletter-skill:purge-all"; then
    echo "$PURGE_CRON $PURGE_CMD  # newsletter-skill:purge-all"
  fi
) | crontab -

echo "Cron entries installed/updated for profile '$PROFILE_ID'."
echo ""
echo "Installed entries (this profile):"
crontab -l 2>/dev/null | grep "$CRON_TAG_PREFIX"
echo ""
echo "Verify: crontab -l | grep newsletter-skill"
