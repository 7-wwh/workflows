# Hermes Cron Setup & Autonomous Maintenance Guide (v5)

This document defines how the newsletter skill autonomously installs, dynamically updates, and nightly maintains its **Hermes Agent Scheduled Tasks (Cron)** — with zero required manual configuration by the user.

Reference: [Hermes Agent Scheduled Tasks (Cron) Guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron/)

---

## Overview of Automatable Processes

| Process | Role / Job Name | Trigger Time | Target / Mechanism | Frequency Source |
|---------|-----------------|--------------|-------------------|-----------------|
| **Nightly Maintain Mode** | `newsletter-skill:maintain-all` | Daily `02:30` | `cron/maintain-cron.sh` → `manage_cron.py maintain` (drift check, auto-repair, stale lock sweep, structured log) | Built-in nightly schedule |
| **Intermediate Agent Batch Production** | `newsletter-skill:<profile>-batch` | Nightly `batch_time` (e.g. `03:00`) | Hermes Agent session via `run-batch.sh` (Steps 4–6: parallel research, draft, eval, export outbox) | `settings.md → batch_time` |
| **Sender Agent Instant Delivery** | `newsletter-skill:<profile>-send` | Each delivery slot (e.g. `08:00, 13:00, 18:00`) | Hermes Agent session via `run-sender.sh` (Step 7: `run-sender.sh` resolves nearest slot at fire time, injects slot label into agent prompt, retrieve outbox, deliver) | `settings.md → slot_times` |
| **Vault Manager Maintenance** | `newsletter-skill:vault-all` | Weekly Sunday `02:00` | `cron/run-vault-maintenance.sh` (recompute knowledge map & correlations) | Weekly schedule |
| **HTML Expiry Purge** | `newsletter-skill:purge-all` | Daily `03:00` + pre-flight | `cron/purge-expired.sh` (clean transient artifacts past retention window) | `settings.md → artifact_retention_days` |

> [!IMPORTANT]
> **System crontab is the single source of truth.** All newsletter scheduling lives in the system
> crontab (`crontab -l`). Hermes native cron (`~/.hermes/cron/jobs.json`) is NOT used for newsletter
> scheduling. The 02:30 maintain job reconciles the live crontab against `settings.md` nightly,
> rewriting only when drift is detected.

---

## The Three Autonomous Scenarios

### 1. First-Time Setup (Autonomous Self-Registration)
**Trigger**: Immediately during onboarding (`references/startup-procedure.md`), when the agent gathers the delivery slots (`slot_times`) and background writing start time (`batch_time`, default `03:00`).
**Action**:
- The agent does NOT merely suggest `/cron-setup`.
- The agent directly registers the jobs in Hermes Cron:
  - In interactive Hermes chat: calls `cronjob(action="create", name="newsletter:<profile>-batch", schedule="<batch_cron>", workdir="<profile_dir>", skills=["newsletter"], prompt="...")`, and similarly for `newsletter:<profile>-send` and `newsletter:maintain-all`.
  - Or executes: `bash newsletter-workspace/cron/sync-cron.sh --profile <profile-id>`.
- Updates `vault/state.json`: `"cron_installed": true`, `"cron_provider": "hermes"`, `"cron_synced_at": "<ISO8601>"`.
- Reports active background schedule confirmation to the user.

### 2. Settings Changes via Agent (Dynamic Editing)
**Trigger**: User changes delivery slots, frequency, or batch time (`/settings`, `/frequency`, `/rules update`).
**Action**:
- Agent writes changes to `settings.md` (and `config.json` mirror).
- Agent **immediately and automatically edits the Hermes cron job**:
  - In interactive Hermes chat: calls `cronjob(action="update", job_id="newsletter:<profile>-send", schedule="<new_cron>")` (and batch job if `batch_time` changed).
  - Or executes: `bash newsletter-workspace/cron/sync-cron.sh --profile <profile-id>`.
- Logs update to `vault/state.json → rule_change_log`.
- Confirms new schedule to user in conversational response.

### 3. Nightly Maintain Mode (Integrity & Drift Auto-Repair)
**Trigger**: Daily at `02:30` (system crontab entry tagged `# newsletter-skill:maintain-all`).
**Action**:
- System cron fires `newsletter-workspace/cron/maintain-cron.sh` → `manage_cron.py maintain`.
- **Checks performed**:
  1. For each enabled profile in `profiles/registry.json`, reads `settings.md` (batch_time, slot_times, delivery_days).
  2. Logs a structured profile summary: `email`, `batch_time`, `slots`, `delivery_days`.
  3. Compares expected cron expressions against the **live system crontab** (`crontab -l`).
  4. Logs per-entry result: `OK` (in sync) or `DRIFT` with expected vs actual expressions.
  5. **Auto-Repairs Drift**: rewrites only the `# newsletter-skill:<profile>-*` lines for affected profiles — never touches unrelated crontab entries.
  6. Verifies the `# newsletter-skill:maintain-all` entry itself; recreates if missing.
  7. Cleans up stale `.lock` files in `cron/locks/`.
  8. Ensures all `.sh` scripts in `cron/` have execute permissions.
  9. Records a health audit to `cron/logs/maintain.log`.
- **Slot resolution (run-sender.sh)**: when the combined send crontab entry fires (e.g. `0 8,23 * * *`),
  `run-sender.sh` runs a Python snippet to find the nearest slot_time from `settings.md`, then injects
  that slot label directly into the Hermes agent prompt — the Sender Agent knows exactly which
  outbox file to retrieve without any guessing.

---

## Architecture & Tools

### Hermes Cron Components
1. **Interactive Tool (`cronjob`)** (for batch/research jobs if desired in future):
   Hermes exposes unified `cronjob` tool — NOT used for newsletter scheduling.
   Newsletter scheduling is managed exclusively via the system crontab.
2. **Standalone CLI (`hermes cron`)**: may be used for ad-hoc agent session management.
3. **System Crontab** (primary scheduler for newsletter):
   - `crontab -l` — view all newsletter entries
   - `python3 cron/manage_cron.py sync [--profile <id>] [--dry-run]` — sync crontab from settings
   - `python3 cron/schedule-status.py [--profile <id>]` — on-demand status comparison
4. **Jobs Tags**: all newsletter crontab entries are tagged `# newsletter-skill:<name>` for
   easy grep and selective rewriting without touching unrelated jobs.

> [!NOTE]
> **Hermes Cron Recursion Guard**: Hermes disables the `cronjob` tool inside cron-run executions to prevent runaway loops. Interactive turns use `cronjob`, while unattended background runs (such as maintain mode) use `cron/manage_cron.py` / CLI.

---

## Directory Layout

```
newsletter-workspace/
├── profiles/
│   ├── registry.json                 ← registered profiles
│   └── <profile-id>/
│       ├── settings.md               ← authoritative schedule source (batch_time, slot_times)
│       └── vault/
│           └── state.json            ← records cron_installed, cron_provider, cron_synced_at
└── cron/
    ├── manage_cron.py                ← core Python engine (sync, check, maintain, summary, uninstall)
    ├── cron-summary.py               ← Real-time Cron & Delivery Queue Summary Tool
    ├── cron-summary.json             ← Real-time summary list (next recipient, previous sent, status, errors)
    ├── schedule-status.py            ← on-demand visibility: crontab vs settings comparison
    ├── sync-cron.sh                  ← bash wrapper for manage_cron.py sync
    ├── maintain-cron.sh              ← nightly maintain runner (02:30)
    ├── run-batch.sh                  ← Intermediate Agent batch runner
    ├── run-sender.sh                 ← Sender Agent delivery runner (slot auto-resolution)
    ├── run-vault-maintenance.sh      ← weekly vault cleanup runner
    ├── purge-expired.sh              ← artifact retention cleanup
    ├── run-newsletter.sh             ← unified CLI (--batch, --send, --summary, --sync-cron, --maintain)
    ├── locks/                        ← per-profile execution locks
    └── logs/
        ├── maintain.log              ← nightly maintain audit trail
        └── <profile>-*.log           ← execution logs
```

---

## Management & Verification Commands

```bash
# Real-time: show immediate next recipient in queue, previous sent, status, and errors
python3 newsletter-workspace/cron/cron-summary.py
bash newsletter-workspace/cron/run-newsletter.sh --summary

# Same but raw JSON output (or read cron/cron-summary.json directly)
python3 newsletter-workspace/cron/cron-summary.py --json
cat newsletter-workspace/cron/cron-summary.json

# On-demand: compare live crontab vs settings.md for all profiles
python3 newsletter-workspace/cron/schedule-status.py

# Same but JSON output (for scripting)
python3 newsletter-workspace/cron/schedule-status.py --json

# Check schedule alignment (exit 0=ok, 1=drift) — scriptable
python3 newsletter-workspace/cron/manage_cron.py check

# Dry-run sync preview (see what would change without writing)
python3 newsletter-workspace/cron/manage_cron.py sync --dry-run
bash newsletter-workspace/cron/sync-cron.sh --dry-run

# Apply sync (write updated crontab entries)
python3 newsletter-workspace/cron/manage_cron.py sync
bash newsletter-workspace/cron/sync-cron.sh

# Run nightly maintain mode manually (verify + auto-repair + refresh cron-summary.json)
bash newsletter-workspace/cron/maintain-cron.sh

# View current crontab (source of truth)
crontab -l | grep newsletter-skill

# View last nightly maintain run summary
tail -20 newsletter-workspace/cron/logs/maintain.log
```

