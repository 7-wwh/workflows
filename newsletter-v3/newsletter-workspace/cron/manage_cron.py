#!/usr/bin/env python3
"""
manage_cron.py — Hermes Cron & System Crontab Manager for Newsletter Skill (v5)

Provides unified scheduling management for both Hermes Agent native cron
(~/.hermes/cron/jobs.json via `hermes cron` CLI) and OS crontab:
  - sync [--profile <id>] [--dry-run] [--system-only]
  - check [--profile <id>]
  - maintain [--profile <id>] [--auto-repair]
  - uninstall [--profile <id>] [--dry-run]
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
WS_ROOT = SCRIPT_DIR.parent
PROFILES_ROOT = WS_ROOT / "profiles"
REGISTRY_FILE = PROFILES_ROOT / "registry.json"
LOG_DIR = SCRIPT_DIR / "logs"
LOCKS_DIR = SCRIPT_DIR / "locks"
MAINTAIN_LOG = LOG_DIR / "maintain.log"
HERMES_CRON_JOBS = Path.home() / ".hermes" / "cron" / "jobs.json"


def log_maintain(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    line = f"[{timestamp}] {msg}\n"
    sys.stdout.write(line)
    try:
        with open(MAINTAIN_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        sys.stderr.write(f"Failed writing to maintain log: {e}\n")


def get_hermes_bin() -> Optional[str]:
    """Locate hermes CLI binary."""
    h = shutil.which("hermes")
    if h:
        return h
    candidates = [
        Path.home() / ".local" / "bin" / "hermes",
        Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes",
        Path("/usr/local/bin/hermes"),
        Path("/usr/bin/hermes"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def run_hermes_cmd(args: List[str]) -> Tuple[int, str, str]:
    """Execute a hermes CLI command."""
    h = get_hermes_bin()
    if not h:
        return 1, "", "hermes CLI binary not found"
    cmd = [h] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def parse_settings_schedule(profile_dir: Path) -> Dict[str, Any]:
    """Parse delivery schedule fields from a profile's settings.md."""
    settings_file = profile_dir / "settings.md"
    if not settings_file.is_file():
        raise FileNotFoundError(f"Settings file not found: {settings_file}")

    content = settings_file.read_text(encoding="utf-8")

    batch_time = "03:00"
    m_batch = re.search(r'^[ \t]*batch_time:[ \t]*["\']?([0-9]{1,2}:[0-9]{2})["\']?', content, re.M)
    if m_batch:
        batch_time = m_batch.group(1).strip()

    slot_times = ["08:00", "13:00", "18:00"]
    m_slots = re.search(r'^[ \t]*slot_times:[ \t]*\[(.*?)\]', content, re.M)
    if m_slots:
        raw_items = m_slots.group(1).split(",")
        parsed = [item.strip().strip("\"' ") for item in raw_items if item.strip().strip("\"' ")]
        if parsed:
            slot_times = parsed

    delivery_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    m_days = re.search(r'^[ \t]*delivery_days:[ \t]*\[(.*?)\]', content, re.M)
    if m_days:
        raw_items = m_days.group(1).split(",")
        parsed = [item.strip().strip("\"' ").lower() for item in raw_items if item.strip().strip("\"' ")]
        if parsed:
            delivery_days = parsed

    email = None
    m_email = re.search(r'^[ \t]*email:[ \t]*["\']?([^#\n\r]+)["\']?', content, re.M)
    if m_email:
        raw_val = m_email.group(1).strip()
        if raw_val.lower() not in ("null", "none", ""):
            email = raw_val

    timezone = "Etc/UTC"
    m_tz = re.search(r'^[ \t]*timezone:[ \t]*["\']?([^#\n\r]+)["\']?', content, re.M)
    if m_tz:
        timezone = m_tz.group(1).strip()

    return {
        "batch_time": batch_time,
        "slot_times": slot_times,
        "delivery_days": delivery_days,
        "email": email,
        "timezone": timezone,
    }


def days_to_cron_dow(days: List[str]) -> str:
    """Convert delivery_days array to cron day-of-week string."""
    day_map = {
        "sun": 0, "mon": 1, "tue": 2, "wed": 3,
        "thu": 4, "fri": 5, "sat": 6,
    }
    nums = sorted(set(day_map[d] for d in days if d in day_map))
    if len(nums) == 7 or not nums:
        return "*"
    return ",".join(str(n) for n in nums)


def time_to_cron(time_str: str, dow: str = "*") -> str:
    """Convert HH:MM to cron expression (min hour * * dow)."""
    parts = time_str.split(":")
    minute = int(parts[1]) if len(parts) > 1 else 0
    hour = int(parts[0])
    return f"{minute} {hour} * * {dow}"


def slot_times_to_cron(slot_times: List[str], dow: str = "*") -> str:
    """
    Convert slot_times list to cron expression.
    Groups into a single line if minutes are uniform, else returns primary minute or first slot.
    """
    if not slot_times:
        return f"0 8,13,18 * * {dow}"

    parsed = []
    for s in slot_times:
        p = s.split(":")
        h = int(p[0])
        m = int(p[1]) if len(p) > 1 else 0
        parsed.append((h, m))

    minutes = sorted(set(p[1] for p in parsed))
    hours = sorted(set(p[0] for p in parsed))

    if len(minutes) == 1:
        minute = minutes[0]
        hours_str = ",".join(str(h) for h in hours)
        return f"{minute} {hours_str} * * {dow}"

    minute = parsed[0][1]
    hours_str = ",".join(str(p[0]) for p in parsed)
    return f"{minute} {hours_str} * * {dow}"


def get_registered_profiles() -> List[Dict[str, Any]]:
    """Return list of enabled profiles from registry.json."""
    if not REGISTRY_FILE.is_file():
        profiles = []
        if PROFILES_ROOT.is_dir():
            for p in PROFILES_ROOT.iterdir():
                if p.is_dir() and (p / "settings.md").is_file():
                    profiles.append({"id": p.name, "enabled": True})
        return profiles

    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return [p for p in data.get("profiles", []) if p.get("enabled", True)]
    except Exception as e:
        sys.stderr.write(f"Warning: error reading registry.json: {e}\n")
        return []


def read_hermes_jobs() -> List[Dict[str, Any]]:
    """Read jobs directly from ~/.hermes/cron/jobs.json."""
    if not HERMES_CRON_JOBS.is_file():
        return []
    try:
        data = json.loads(HERMES_CRON_JOBS.read_text(encoding="utf-8"))
        return data.get("jobs", [])
    except Exception as e:
        sys.stderr.write(f"Warning: could not read {HERMES_CRON_JOBS}: {e}\n")
        return []


def get_hermes_job_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Lookup a job in Hermes by exact name."""
    jobs = read_hermes_jobs()
    for j in jobs:
        if j.get("name") == name:
            return j
    return None


def hermes_cron_available() -> bool:
    return (get_hermes_bin() is not None) or HERMES_CRON_JOBS.exists()


# ─── Crontab (OS-Level) Support ───────────────────────────────────────────────

def get_system_crontab() -> str:
    """Read existing crontab."""
    res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if res.returncode == 0:
        return res.stdout
    return ""


def set_system_crontab(content: str) -> bool:
    """Install new crontab atomically."""
    bak_file = LOG_DIR / "crontab.bak"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    current = get_system_crontab()
    if current:
        bak_file.write_text(current, encoding="utf-8")

    res = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True)
    if res.returncode != 0:
        sys.stderr.write(f"Failed to install crontab: {res.stderr}\n")
        return False
    return True


def build_system_cron_lines_for_profile(profile_id: str, sched: Dict[str, Any]) -> List[str]:
    """Generate system crontab lines for a given profile."""
    dow = days_to_cron_dow(sched["delivery_days"])
    batch_cron = time_to_cron(sched["batch_time"], dow)
    send_cron = slot_times_to_cron(sched["slot_times"], dow)

    batch_cmd = f"{WS_ROOT}/cron/run-batch.sh --profile {profile_id} >> {WS_ROOT}/cron/logs/{profile_id}-batch.log 2>&1"
    send_cmd = f"{WS_ROOT}/cron/run-sender.sh --profile {profile_id} >> {WS_ROOT}/cron/logs/{profile_id}-sender.log 2>&1"

    return [
        f"{batch_cron} {batch_cmd}  # newsletter-skill:{profile_id}-batch",
        f"{send_cron} {send_cmd}  # newsletter-skill:{profile_id}-send",
    ]


def build_system_shared_cron_lines() -> List[str]:
    """Generate shared/global maintenance crontab lines."""
    maintain_cmd = f"{WS_ROOT}/cron/maintain-cron.sh >> {WS_ROOT}/cron/logs/maintain.log 2>&1"
    purge_cmd = f"{WS_ROOT}/cron/purge-expired.sh >> {WS_ROOT}/cron/logs/purge.log 2>&1"
    vault_cmd = f"{WS_ROOT}/cron/run-vault-maintenance.sh >> {WS_ROOT}/cron/logs/vault.log 2>&1"

    return [
        f"30 2 * * * {maintain_cmd}  # newsletter-skill:maintain-all",
        f"0 3 * * * {purge_cmd}  # newsletter-skill:purge-all",
        f"0 2 * * 0 {vault_cmd}  # newsletter-skill:vault-all",
    ]


def sync_system_crontab(target_profile_id: Optional[str] = None, dry_run: bool = False) -> bool:
    """Sync newsletter entries in system crontab preserving non-newsletter jobs."""
    current_lines = get_system_crontab().splitlines()

    all_profiles = get_registered_profiles()
    profiles_to_sync = [p for p in all_profiles if not target_profile_id or p["id"] == target_profile_id]

    if target_profile_id:
        prefix = f"# newsletter-skill:{target_profile_id}-"
        preserved = [line for line in current_lines if prefix not in line]
    else:
        preserved = [line for line in current_lines if "# newsletter-skill:" not in line]

    new_lines = list(preserved)
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()

    for p in profiles_to_sync:
        p_id = p["id"]
        p_dir = PROFILES_ROOT / p_id
        if not p_dir.is_dir():
            continue
        try:
            sched = parse_settings_schedule(p_dir)
            p_lines = build_system_cron_lines_for_profile(p_id, sched)
            new_lines.extend(p_lines)
        except Exception as e:
            sys.stderr.write(f"Error parsing schedule for {p_id}: {e}\n")

    shared_lines = build_system_shared_cron_lines()
    for s_line in shared_lines:
        tag = s_line.split("#")[-1].strip()
        if not any(tag in line for line in new_lines):
            new_lines.append(s_line)

    final_content = "\n".join(new_lines) + "\n"

    if dry_run:
        print("=== [DRY-RUN] Proposed System Crontab ===")
        print(final_content)
        return True

    return set_system_crontab(final_content)


# ─── Hermes Native Cron Support ───────────────────────────────────────────────

def hermes_create_job(name: str, schedule: str, prompt: str, workdir: Path, skills: List[str], deliver: str = "local") -> Tuple[bool, str]:
    """Create a job using Hermes CLI."""
    args = [
        "cron", "create", schedule, prompt,
        "--name", name,
        "--workdir", str(workdir),
        "--deliver", deliver,
    ]
    for s in skills:
        args.extend(["--skill", s])
    code, out, err = run_hermes_cmd(args)
    if code == 0:
        return True, out.strip()
    return False, err or out


def hermes_update_job(job_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
    """Update an existing job schedule."""
    args = ["cron", "edit", job_id]
    if "schedule" in updates:
        args.extend(["--schedule", updates["schedule"]])
    code, out, err = run_hermes_cmd(args)
    if code == 0:
        return True, out.strip()
    return False, err or out


def hermes_remove_job(job_id: str) -> Tuple[bool, str]:
    """Remove a job by ID or name."""
    code, out, err = run_hermes_cmd(["cron", "remove", job_id])
    if code == 0:
        return True, out.strip()
    return False, err or out


def sync_hermes_cron_for_profile(profile_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Ensure Hermes native scheduled jobs exist and match settings.md:
      1. newsletter:<profile>-batch  (Intermediate Agent batch writing at batch_time)
      2. newsletter:<profile>-send   (Sender Agent delivery at slot_times)
    """
    profile_ws = (PROFILES_ROOT / profile_id).resolve()
    sched = parse_settings_schedule(profile_ws)
    dow = days_to_cron_dow(sched["delivery_days"])
    batch_cron = time_to_cron(sched["batch_time"], dow)
    send_cron = slot_times_to_cron(sched["slot_times"], dow)

    batch_job_name = f"newsletter:{profile_id}-batch"
    send_job_name = f"newsletter:{profile_id}-send"

    batch_prompt = (
        f"Workspace boundary: your working directory is the profile workspace '{profile_ws}'. "
        f"Execute the INTERMEDIATE AGENT batch production workflow (Steps 4–6) for all slots scheduled for today in content_plan.md. "
        f"Step 4: Dispatch parallel research dumps to research/. "
        f"Steps 5–6: Draft structured content JSON (content/), assemble HTML draft via shared/scripts/assemble_edition.py, "
        f"evaluate with direct edits (eval/), export final HTML to outbox/, flip slot to READY in content_plan.md, "
        f"and record batch details in runs/batch.json. NEVER send. Pass --auto: skip interactive confirmation."
    )

    recipient = sched.get("email") or "recipient"
    send_prompt = (
        f"Workspace boundary: your working directory is the profile workspace '{profile_ws}'. "
        f"Role: SENDER AGENT (Step 7). Match current time to slot_times in settings.md. "
        f"If the slot is READY, retrieve outbox edition, send via Hermes google-workspace skill to {recipient}, "
        f"re-stamp HTML expiry, run cron/purge-expired.sh --profile {profile_id}, flip slot to DELIVERED in content_plan.md, "
        f"and append delivery record to vault/editions.json. Zero production work allowed. Pass --auto: skip interactive confirmation."
    )

    results = {"batch": None, "send": None}

    # 1. Batch Job
    existing_batch = get_hermes_job_by_name(batch_job_name)
    if not existing_batch:
        if dry_run:
            print(f"[DRY-RUN] Would CREATE Hermes cron job '{batch_job_name}' at '{batch_cron}'")
            results["batch"] = "would_create"
        else:
            ok, out = hermes_create_job(batch_job_name, batch_cron, batch_prompt, profile_ws, ["newsletter"], "local")
            if ok:
                log_maintain(f"Created Hermes cron job '{batch_job_name}' ({batch_cron})")
                results["batch"] = "created"
            else:
                log_maintain(f"ERROR creating Hermes cron job '{batch_job_name}': {out}")
                results["batch"] = f"error: {out}"
    else:
        current_sched = existing_batch.get("schedule_display") or (existing_batch.get("schedule") or {}).get("display") or ""
        if current_sched != batch_cron:
            if dry_run:
                print(f"[DRY-RUN] Would EDIT Hermes cron job '{batch_job_name}' from '{current_sched}' to '{batch_cron}'")
                results["batch"] = "would_update"
            else:
                ok, out = hermes_update_job(existing_batch["id"], {"schedule": batch_cron})
                if ok:
                    log_maintain(f"Updated Hermes cron job '{batch_job_name}' schedule from '{current_sched}' to '{batch_cron}'")
                    results["batch"] = "updated"
                else:
                    log_maintain(f"ERROR updating Hermes cron job '{batch_job_name}': {out}")
                    results["batch"] = f"error: {out}"
        else:
            results["batch"] = "in_sync"

    # 2. Sender Job
    existing_send = get_hermes_job_by_name(send_job_name)
    if not existing_send:
        if dry_run:
            print(f"[DRY-RUN] Would CREATE Hermes cron job '{send_job_name}' at '{send_cron}'")
            results["send"] = "would_create"
        else:
            ok, out = hermes_create_job(send_job_name, send_cron, send_prompt, profile_ws, ["newsletter"], "local")
            if ok:
                log_maintain(f"Created Hermes cron job '{send_job_name}' ({send_cron})")
                results["send"] = "created"
            else:
                log_maintain(f"ERROR creating Hermes cron job '{send_job_name}': {out}")
                results["send"] = f"error: {out}"
    else:
        current_sched = existing_send.get("schedule_display") or (existing_send.get("schedule") or {}).get("display") or ""
        if current_sched != send_cron:
            if dry_run:
                print(f"[DRY-RUN] Would EDIT Hermes cron job '{send_job_name}' from '{current_sched}' to '{send_cron}'")
                results["send"] = "would_update"
            else:
                ok, out = hermes_update_job(existing_send["id"], {"schedule": send_cron})
                if ok:
                    log_maintain(f"Updated Hermes cron job '{send_job_name}' schedule from '{current_sched}' to '{send_cron}'")
                    results["send"] = "updated"
                else:
                    log_maintain(f"ERROR updating Hermes cron job '{send_job_name}': {out}")
                    results["send"] = f"error: {out}"
        else:
            results["send"] = "in_sync"

    return results


def sync_hermes_shared_jobs(dry_run: bool = False) -> Dict[str, Any]:
    """Ensure shared Hermes scheduled tasks exist (e.g. newsletter:maintain-all at 02:30)."""
    maintain_name = "newsletter:maintain-all"
    maintain_cron = "30 2 * * *"
    maintain_prompt = (
        f"Workspace boundary: your working directory is the newsletter skill root '{WS_ROOT}'. "
        f"Run Nightly Maintain Mode: inspect settings.md for all profiles in profiles/registry.json, "
        f"verify that Hermes cron jobs are scheduled accurately, auto-repair any drift, sweep stale locks, "
        f"and append a health summary to cron/logs/maintain.log. Execute: bash cron/maintain-cron.sh"
    )

    existing = get_hermes_job_by_name(maintain_name)
    if not existing:
        if dry_run:
            print(f"[DRY-RUN] Would CREATE Hermes cron job '{maintain_name}' at '{maintain_cron}'")
            return {"maintain": "would_create"}
        else:
            ok, out = hermes_create_job(maintain_name, maintain_cron, maintain_prompt, WS_ROOT, ["newsletter"], "local")
            if ok:
                log_maintain(f"Created Hermes cron job '{maintain_name}' ({maintain_cron})")
                return {"maintain": "created"}
            else:
                log_maintain(f"ERROR creating Hermes cron job '{maintain_name}': {out}")
                return {"maintain": f"error: {out}"}
    return {"maintain": "in_sync"}


# ─── Stale Lock & Script Permissions Maintenance ──────────────────────────────

def clean_stale_locks(max_age_seconds: int = 7200) -> int:
    """Remove lock files older than threshold."""
    if not LOCKS_DIR.is_dir():
        return 0
    now = datetime.datetime.now().timestamp()
    removed = 0
    for lock in LOCKS_DIR.glob("*.lock"):
        try:
            mtime = lock.stat().st_mtime
            if (now - mtime) > max_age_seconds:
                lock.unlink()
                removed += 1
                log_maintain(f"Removed stale lock: {lock.name} (age: {int(now - mtime)}s)")
        except Exception as e:
            sys.stderr.write(f"Error checking lock {lock}: {e}\n")
    return removed


def ensure_scripts_executable() -> None:
    """Ensure all .sh files in cron/ have execute permissions."""
    for sh in SCRIPT_DIR.glob("*.sh"):
        try:
            current_mode = sh.stat().st_mode
            sh.chmod(current_mode | 0o755)
        except Exception as e:
            sys.stderr.write(f"Error setting executable on {sh}: {e}\n")


# ─── Verification & Drift Detection ───────────────────────────────────────────

def get_crontab_entry_for_tag(tag: str) -> Optional[str]:
    """Parse the live system crontab and return the cron expression for a tagged line."""
    crontab_content = get_system_crontab()
    for line in crontab_content.splitlines():
        if f"# {tag}" in line and not line.strip().startswith("#"):
            parts = line.strip().split()
            if len(parts) >= 5:
                return " ".join(parts[:5])
    return None


def check_profile_schedule(profile_id: str) -> Dict[str, Any]:
    """Check if system crontab entries for a profile match settings.md."""
    profile_ws = PROFILES_ROOT / profile_id
    sched = parse_settings_schedule(profile_ws)
    dow = days_to_cron_dow(sched["delivery_days"])
    expected_batch = time_to_cron(sched["batch_time"], dow)
    expected_send = slot_times_to_cron(sched["slot_times"], dow)

    actual_batch = get_crontab_entry_for_tag(f"newsletter-skill:{profile_id}-batch")
    actual_send = get_crontab_entry_for_tag(f"newsletter-skill:{profile_id}-send")

    batch_status = "missing"
    if actual_batch is not None:
        batch_status = "ok" if actual_batch == expected_batch else f"drift (expected '{expected_batch}', got '{actual_batch}')"

    send_status = "missing"
    if actual_send is not None:
        send_status = "ok" if actual_send == expected_send else f"drift (expected '{expected_send}', got '{actual_send}')"

    has_drift = (batch_status != "ok") or (send_status != "ok")
    return {
        "profile": profile_id,
        "batch": {"expected": expected_batch, "actual": actual_batch, "status": batch_status},
        "send": {"expected": expected_send, "actual": actual_send, "status": send_status},
        "in_sync": not has_drift,
    }


# ─── Nightly Maintain Routine ─────────────────────────────────────────────────

def run_maintain_mode(profile_id: Optional[str] = None, auto_repair: bool = True) -> bool:
    """
    Execute Nightly Maintain Mode (system-crontab-first, drift-only repair):
      1. Ensure script permissions & sweep stale locks.
      2. For each enabled profile, read settings.md and compare against live
         system crontab. Log a structured summary of each profile's schedule.
      3. If drift detected and auto_repair=True, rewrite only the affected
         newsletter-skill crontab lines (never the full crontab).
      4. Log health audit to cron/logs/maintain.log.

    NOTE: Hermes native cron is no longer used for newsletter scheduling.
    All schedule management is via system crontab. The cronjob tool is not
    called from this function.
    """
    log_maintain("=== Nightly Maintain Mode Started ===")
    all_ok = True

    # 1. Script permissions & stale locks
    ensure_scripts_executable()
    cleaned = clean_stale_locks()
    if cleaned > 0:
        log_maintain(f"Stale locks sweep: cleaned {cleaned} lock file(s).")

    # 2. Check and reconcile profiles against live system crontab
    profiles = get_registered_profiles()
    if profile_id:
        profiles = [p for p in profiles if p["id"] == profile_id]

    for p in profiles:
        pid = p["id"]
        p_dir = PROFILES_ROOT / pid
        if not p_dir.is_dir():
            log_maintain(f"WARNING: Profile '{pid}' directory not found, skipping.")
            continue
        try:
            sched = parse_settings_schedule(p_dir)
        except Exception as e:
            log_maintain(f"ERROR: Could not read settings for profile '{pid}': {e}")
            continue

        slots_str = ", ".join(sched["slot_times"])
        email_str = sched.get("email") or "(not set)"
        log_maintain(
            f"Profile '{pid}': email={email_str}  batch={sched['batch_time']}  "
            f"slots=[{slots_str}]  days={','.join(sched['delivery_days'])}"
        )

        status = check_profile_schedule(pid)
        batch_ok = status["batch"]["status"] == "ok"
        send_ok = status["send"]["status"] == "ok"

        if batch_ok:
            log_maintain(f"Profile '{pid}': crontab batch entry → OK ({status['batch']['expected']})")
        else:
            all_ok = False
            log_maintain(
                f"Profile '{pid}': crontab batch entry → DRIFT — {status['batch']['status']}"
            )

        if send_ok:
            log_maintain(f"Profile '{pid}': crontab send entry  → OK ({status['send']['expected']})")
        else:
            all_ok = False
            log_maintain(
                f"Profile '{pid}': crontab send entry  → DRIFT — {status['send']['status']}"
            )

        if not (batch_ok and send_ok) and auto_repair:
            log_maintain(f"Auto-repairing system crontab for profile '{pid}'...")
            ok = sync_system_crontab(target_profile_id=pid, dry_run=False)
            if ok:
                log_maintain(f"Auto-repair for '{pid}': system crontab updated successfully.")
            else:
                log_maintain(f"Auto-repair for '{pid}': FAILED to update system crontab.")

    # 3. Verify maintain-all entry in system crontab
    maintain_tag = "newsletter-skill:maintain-all"
    actual_maintain = get_crontab_entry_for_tag(maintain_tag)
    if actual_maintain is not None:
        log_maintain(f"Maintain job (02:30): crontab entry → OK ({actual_maintain})")
    else:
        all_ok = False
        log_maintain("DRIFT DETECTED: maintain crontab entry (newsletter-skill:maintain-all) missing.")
        if auto_repair:
            # Re-sync shared lines which includes the maintain entry
            sync_system_crontab(target_profile_id=None, dry_run=False)
            log_maintain("Auto-repair: system crontab (shared entries) rewritten.")

    # 4. Refresh cron/cron-summary.json
    summary_script = SCRIPT_DIR / "cron-summary.py"
    if summary_script.is_file():
        try:
            subprocess.run([sys.executable, str(summary_script)], capture_output=True)
            log_maintain("Refreshed cron/cron-summary.json.")
        except Exception as e:
            log_maintain(f"Warning: could not refresh cron summary: {e}")

    log_maintain(f"=== Nightly Maintain Mode Completed (Status: {'HEALTHY' if all_ok else 'REPAIRED'}) ===")
    return all_ok




# ─── CLI Entrypoint ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Newsletter Cron & Maintain Manager (v5)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync system crontab from settings.md (system cron is primary)")
    p_sync.add_argument("--profile", "-p", help="Target profile ID (default: all registered)")
    p_sync.add_argument("--dry-run", action="store_true", help="Preview changes without modifying")
    p_sync.add_argument("--system-only", action="store_true", help="[deprecated, now default] Only sync system crontab")
    p_sync.add_argument("--hermes", action="store_true", help="Also sync Hermes native cron jobs (optional, not required)")

    # check
    p_check = subparsers.add_parser("check", help="Check schedule alignment between settings.md and cron")
    p_check.add_argument("--profile", "-p", help="Target profile ID")

    # maintain
    p_maintain = subparsers.add_parser("maintain", help="Run nightly maintain mode and self-heal")
    p_maintain.add_argument("--profile", "-p", help="Target profile ID")
    p_maintain.add_argument("--no-repair", action="store_true", help="Report drift without repairing")

    # summary
    p_summary = subparsers.add_parser("summary", help="Show cron & delivery queue summary (.json and table)")
    p_summary.add_argument("--profile", "-p", help="Target profile ID")
    p_summary.add_argument("--json", action="store_true", help="Output raw JSON to stdout")
    p_summary.add_argument("--no-save", action="store_true", help="Do not write to cron/cron-summary.json")

    # uninstall
    p_un = subparsers.add_parser("uninstall", help="Remove newsletter cron jobs")
    p_un.add_argument("--profile", "-p", help="Target profile ID")
    p_un.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    ensure_scripts_executable()

    if args.command == "summary":
        cmd = [sys.executable, str(SCRIPT_DIR / "cron-summary.py")]
        if args.profile:
            cmd.extend(["--profile", args.profile])
        if args.json:
            cmd.append("--json")
        if getattr(args, "no_save", False):
            cmd.append("--no-save")
        res = subprocess.run(cmd)
        sys.exit(res.returncode)

    elif args.command == "sync":
        profiles = get_registered_profiles()
        if args.profile:
            profiles = [p for p in profiles if p["id"] == args.profile]
            if not profiles:
                profiles = [{"id": args.profile, "enabled": True}]

        print(f"Syncing system crontab for {len(profiles)} profile(s)...")

        # 1. System Crontab (primary — always run)
        ok = sync_system_crontab(target_profile_id=args.profile, dry_run=args.dry_run)
        print(f"System crontab sync: {'OK' if ok else 'FAILED'}")

        # 2. Hermes Native Cron (optional — only if --hermes flag passed)
        if getattr(args, 'hermes', False) and hermes_cron_available():
            for p in profiles:
                res = sync_hermes_cron_for_profile(p["id"], dry_run=args.dry_run)
                print(f"Profile '{p['id']}' Hermes cron sync: {res}")
            shared_res = sync_hermes_shared_jobs(dry_run=args.dry_run)
            print(f"Shared Hermes cron sync: {shared_res}")

    elif args.command == "check":
        profiles = get_registered_profiles()
        if args.profile:
            profiles = [p for p in profiles if p["id"] == args.profile]

        all_synced = True
        for p in profiles:
            st = check_profile_schedule(p["id"])
            print(f"Profile '{p['id']}':")
            print(f"  Batch Job: {st['batch']['status']}  (expected: {st['batch']['expected']}, actual: {st['batch']['actual'] or 'missing'})")
            print(f"  Send Job:  {st['send']['status']}  (expected: {st['send']['expected']}, actual: {st['send']['actual'] or 'missing'})")
            if not st["in_sync"]:
                all_synced = False

        sys.exit(0 if all_synced else 1)

    elif args.command == "maintain":
        auto_repair = not getattr(args, "no_repair", False)
        ok = run_maintain_mode(profile_id=args.profile, auto_repair=auto_repair)
        sys.exit(0 if ok else 0)

    elif args.command == "uninstall":
        # Remove Hermes jobs
        if hermes_cron_available():
            jobs = read_hermes_jobs()
            for j in jobs:
                j_name = j.get("name", "")
                if j_name.startswith("newsletter:"):
                    if args.profile and not j_name.startswith(f"newsletter:{args.profile}-"):
                        continue
                    if args.dry_run:
                        print(f"[DRY-RUN] Would remove Hermes job '{j_name}' ({j['id']})")
                    else:
                        ok, out = hermes_remove_job(j["id"])
                        print(f"Removed Hermes job '{j_name}' ({j['id']}): {out}")

        # Remove system crontab entries
        current_lines = get_system_crontab().splitlines()
        if args.profile:
            tag = f"# newsletter-skill:{args.profile}-"
            kept = [l for l in current_lines if tag not in l]
        else:
            kept = [l for l in current_lines if "# newsletter-skill:" not in l]
        if not args.dry_run:
            set_system_crontab("\n".join(kept) + "\n")
            print("Cleaned system crontab entries.")
        else:
            print("[DRY-RUN] Would clean system crontab entries.")


if __name__ == "__main__":
    main()

