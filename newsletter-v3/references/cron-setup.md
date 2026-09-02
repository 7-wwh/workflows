# Cron Setup Agent (v4 — Dual-Cron: Nightly Batch + Instant Delivery)

This document defines how the newsletter skill installs, verifies, and maintains
**cron jobs** (or equivalent OS-level schedulers) for every process that should fire
automatically — without the user having to manually invoke `/newsletter` each session.

Read this file whenever the user says any of:
- "set up cron", "install cron", "automate my newsletter"
- "schedule the newsletter automatically"
- `/cron-setup` or `/install-cron`
- "make it run on its own", "run in the background"

---

## Overview of Automatable Processes

| Process | Role / Script | Trigger Time | Frequency Source |
|---------|---------------|--------------|-----------------|
| **Intermediate Agent Batch Production** | `cron/run-batch.sh` (or `run-newsletter.sh --batch`) | Nightly / early morning (e.g. `03:00`) | `settings.md → batch_time` |
| **Sender Agent Instant Delivery** | `cron/run-sender.sh` (or `run-newsletter.sh --send`) | At each delivery slot (e.g. `08:00, 13:00, 18:00`) | `settings.md → slot_times` |
| **Vault Manager Maintenance** | `cron/run-vault-maintenance.sh` | Weekly Sunday `02:00` | Weekly schedule |
| **HTML Expiry Purge** | `cron/purge-expired.sh` | Daily `03:00` + pre-flight of all runs | `settings.md → html_expiry_days` |

---

## Portability Rules (mandatory — this skill is shared publicly)

Every `.sh` script shipped with this skill **must** be runnable unchanged on any device,
by any agent, from any working directory:

1. **Self-relative paths only.** Derive the script and workspace locations from the
   script's own path:
   ```bash
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   WORKSPACE="$(dirname "$SCRIPT_DIR")"   # newsletter-workspace/
   ```
   Never hard-code `/home/...`, `$HOME`, or `/Users/...` inside a script.
2. **`cd "$WORKSPACE"` before invoking the agent**, so every relative path the agent
   touches (`content_plan.md`, `settings.md`, `cron/purge-expired.sh`) resolves correctly
   regardless of where cron fired from.
3. **Absolute paths appear only in generated cron entries.** Cron itself has no cwd, so
   `cron-setup` expands `$WS` at install time — but the installed entry points at the
   *user's actual* skill location, computed on their machine, never a template default.
4. **No environment assumptions.** Scripts must not assume a specific shell beyond
   `#!/usr/bin/env bash`, a specific OS package, or pre-set env vars. Optional
   dependencies (e.g. the `claude` CLI) are invoked by name with a clear log line if
   missing, never a silent failure.
5. **Agent-facing paths in prompts are relative** to the workspace (`settings.md`,
   `cron/purge-expired.sh`), because the agent is always launched with
   `cd "$WORKSPACE"` applied.

Before shipping or regenerating any script, verify with:
```bash
cd / && bash /path/to/skill/newsletter-workspace/cron/run-batch.sh --dry-run
cd / && bash /path/to/skill/newsletter-workspace/cron/run-sender.sh --dry-run
```

---

## Step 1 — Detect the Runtime Environment

Before installing any cron job, check which scheduler is available:

```bash
# Check for standard cron
which crontab && crontab -l

# Check for systemd timers (Linux)
systemctl list-timers --no-pager 2>/dev/null

# Check for launchd (macOS)
ls ~/Library/LaunchAgents/ 2>/dev/null

# Check for Task Scheduler (Windows — WSL only)
which schtasks 2>/dev/null
```

| Result | Action |
|--------|--------|
| `crontab` available | Use crontab (preferred) |
| systemd available, crontab absent | Generate `.timer` + `.service` unit files |
| macOS launchd | Generate `com.newsletter.plist` LaunchAgent |
| None detected | Advise user; generate a shell script they can call manually or wire to n8n/Zapier |

---

## Step 2 — Read `settings.md` (authoritative)

Load `newsletter-workspace/settings.md` to derive the schedule. **`settings.md` is the
authoritative source; `config.json` is only a legacy mirror.** Key fields:

```markdown
sends_per_day: 3
slot_times: ["08:00", "13:00", "18:00"]
batch_time: "03:00"
delivery_days: ["mon","tue","wed","thu","fri","sat","sun"]
timezone: auto | IANA location identifier (e.g. "Asia/Kuala_Lumpur")
```

**Timezone rule:** values must be IANA location identifiers (e.g. `Europe/Berlin`),
never UTC offsets. If `timezone` is `auto` (or absent), detect it once and **write the
resolved IANA value back into `settings.md`**:

```bash
timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone || echo "UTC"
```

If `sends_per_day` and `len(slot_times)` disagree, warn the user and use `slot_times`.

---

## Step 3 — Generate Cron Expressions for Both Roles

### 3a. Intermediate Agent Batch Cron (`batch_time`)
Extract the HH:MM from `settings.md → batch_time` (e.g. `03:00` -> minute `0`, hour `3`):
- `0 3 * * *` (runs every night in the background to compile and write all editions of today)

### 3b. Sender Agent Instant Delivery Cron (`slot_times`)
Extract the hours and minutes from `settings.md → slot_times` (e.g. `["08:00","13:00","18:00"]`):
- `0 8,13,18 * * *` (runs at each scheduled slot to retrieve from outbox and send instantly)

If `delivery_days` is restricted (e.g. `["mon","wed","fri"]`), append day-of-week (`1,3,5`).

---

## Step 4 — Verify Runner Scripts Exist

Ensure all runner scripts exist and are executable in `newsletter-workspace/cron/`:
- `cron/run-batch.sh` — Intermediate Agent batch producer
- `cron/run-sender.sh` — Sender Agent instant delivery
- `cron/run-newsletter.sh` — Unified wrapper (`--batch`, `--send`)
- `cron/purge-expired.sh` — HTML expiry cleanup
- `cron/run-vault-maintenance.sh` — Weekly vault maintenance

```bash
chmod +x newsletter-workspace/cron/*.sh
```

---

## Step 5 — Install the Jobs

### 5a. crontab (Linux / macOS fallback)

```bash
# Backup current crontab
crontab -l > /tmp/crontab.bak 2>/dev/null || true

# Resolve workspace path relative to this script
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$SKILL_DIR/newsletter-workspace"

# ─── v5: install PER PROFILE. Repeat this block for every enabled profile in
# profiles/registry.json, substituting <PROFILE_ID> and that profile's
# settings.md values (batch_time, slot_times, delivery_days).
# Tag every entry with the profile id so one profile's reinstall never
# clobbers another's (never do a blanket `grep -v newsletter-skill` wipe).

P="<PROFILE_ID>"

# 1. Nightly batch job (from profiles/$P/settings.md -> batch_time, e.g. 03:00)
BATCH_CMD="$WS/cron/run-batch.sh --profile $P >> $WS/cron/logs/$P-batch.log 2>&1"
BATCH_ENTRY="0 3 * * * $BATCH_CMD  # newsletter-skill:$P-batch"

# 2. Sender delivery jobs (from profiles/$P/settings.md -> slot_times, e.g. 08:00,13:00,18:00)
SENDER_CMD="$WS/cron/run-sender.sh --profile $P >> $WS/cron/logs/$P-sender.log 2>&1"
SENDER_ENTRY="0 8,13,18 * * * $SENDER_CMD  # newsletter-skill:$P-send"

# 3. Weekly vault maintenance (Sunday 02:00) — one entry maintains ALL profiles
VAULT_ENTRY="0 2 * * 0 $WS/cron/run-vault-maintenance.sh >> $WS/cron/logs/vault.log 2>&1  # newsletter-skill:vault-all"

# 4. Daily purge safety net (03:00) — one entry sweeps ALL profiles
PURGE_ENTRY="0 3 * * * $WS/cron/purge-expired.sh >> $WS/cron/logs/purge.log 2>&1  # newsletter-skill:purge-all"

# Install entries (remove only THIS profile's old entries, keep other profiles intact)
(crontab -l 2>/dev/null | grep -v "newsletter-skill:$P"; echo "$BATCH_ENTRY"; echo "$SENDER_ENTRY") | crontab -
# Add the shared sweep entries once (first profile install only):
(crontab -l 2>/dev/null; echo "$VAULT_ENTRY"; echo "$PURGE_ENTRY") | crontab -

echo "Cron jobs installed for profile '$P'. Repeat for each additional profile."
```

### 5b. systemd timers (Linux preferred)

Create `~/.config/systemd/user/newsletter-batch.service` & `newsletter-batch.timer` (for `batch_time` at 03:00).
Create `~/.config/systemd/user/newsletter-send.service` & `newsletter-send.timer` (for `slot_times` at 08:00, 13:00, 18:00).

Enable:
```bash
systemctl --user daemon-reload
systemctl --user enable --now newsletter-batch.timer newsletter-send.timer
systemctl --user list-timers newsletter-*
```

---

## Step 6 — Verify Installation

After installing, verify:

```bash
echo "=== Installed Cron Jobs ===" && crontab -l | grep newsletter
echo "=== Log tail ===" && tail -n 20 "$WS/cron/run.log" 2>/dev/null || echo "(No log yet)"
```

Report to the user:
- Schedule: Nightly batch at `batch_time` (e.g. 03:00) + instant deliveries at `slot_times` (e.g. 08:00, 13:00, 18:00).
- Logs location: `$WS/cron/run.log`.
- Re-run `/cron-setup` if `settings.md` schedule values change.

---

## Cron Directory Layout

```
newsletter-workspace/
└── cron/
    ├── run-batch.sh               ← Intermediate Agent nightly batch runner (batch_time)
    ├── run-sender.sh              ← Sender Agent delivery runner (slot_times)
    ├── run-newsletter.sh          ← Unified wrapper (--batch / --send)
    ├── run-vault-maintenance.sh   ← Weekly vault cleanup (Sunday 02:00)
    ├── purge-expired.sh           ← Deletes HTML past html_expiry_days
    ├── purge.log                  ← Purge audit log (append-only)
    └── run.log                    ← Execution log for batch & sender
```
