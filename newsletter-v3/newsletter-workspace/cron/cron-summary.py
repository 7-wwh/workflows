#!/usr/bin/env python3
"""
cron-summary.py — Real-time Cron & Delivery Queue Summary Tool (v5)

Aggregates all profile schedules, live crontab status, previous sent history,
and runtime execution logs into a structured JSON summary (cron/cron-summary.json)
and a human-readable CLI table.

Key capabilities:
  - Immediate Next Recipient: calculates exact upcoming send queue sorted by time.
  - Previous Sent: retrieves latest delivery timestamp from vault/editions.json.
  - Status & Error Extraction: parses logs for runtime issues, lock contention,
    or GWS token failures.
  - Dual Output: writes cron/cron-summary.json and renders ASCII queue table.

Usage:
    python3 cron/cron-summary.py [--json] [--save] [--profile <id>]
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo

SCRIPT_DIR = Path(__file__).resolve().parent
WS_ROOT = SCRIPT_DIR.parent
PROFILES_ROOT = WS_ROOT / "profiles"
REGISTRY_FILE = PROFILES_ROOT / "registry.json"
LOG_DIR = SCRIPT_DIR / "logs"
LOCKS_DIR = SCRIPT_DIR / "locks"
SUMMARY_FILE = SCRIPT_DIR / "cron-summary.json"


# ── Time & Schedule Calculations ───────────────────────────────────────────────

DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
INV_DAY_MAP = {v: k for k, v in DAY_MAP.items()}


def get_profile_timezone(tz_name: Optional[str]) -> datetime.tzinfo:
    """Safely resolve IANA timezone with fallback to UTC."""
    if not tz_name or tz_name.strip() in ("auto", "null", "none", ""):
        return datetime.timezone.utc
    try:
        return zoneinfo.ZoneInfo(tz_name.strip())
    except Exception:
        return datetime.timezone.utc


def calculate_next_run(
    target_time_str: str,
    delivery_days: List[str],
    tz: datetime.tzinfo,
    now_utc: datetime.datetime,
) -> Tuple[datetime.datetime, str]:
    """
    Calculate the next occurrence of a given HH:MM time restricted to delivery_days.
    Returns (next_datetime_aware, slot_time_str).
    """
    now_local = now_utc.astimezone(tz)
    allowed_weekdays = set(DAY_MAP[d.lower()] for d in delivery_days if d.lower() in DAY_MAP)
    if not allowed_weekdays:
        allowed_weekdays = set(range(7))

    h, m = 0, 0
    parts = target_time_str.split(":")
    if len(parts) >= 2:
        h, m = int(parts[0]), int(parts[1])

    # Check up to 14 days into the future
    for day_offset in range(14):
        candidate_date = (now_local + datetime.timedelta(days=day_offset)).date()
        if candidate_date.weekday() in allowed_weekdays:
            candidate_dt = datetime.datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                h,
                m,
                0,
                tzinfo=tz,
            )
            if candidate_dt > now_local:
                return candidate_dt, f"{h:02d}:{m:02d}"

    # Fallback to tomorrow if no future date found
    fallback = (now_local + datetime.timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)
    return fallback, f"{h:02d}:{m:02d}"


def calculate_next_send_slot(
    slot_times: List[str],
    delivery_days: List[str],
    tz: datetime.tzinfo,
    now_utc: datetime.datetime,
) -> Tuple[datetime.datetime, str]:
    """Find the earliest upcoming slot time among all configured slot_times."""
    candidates = []
    for slot in slot_times:
        try:
            dt, slot_str = calculate_next_run(slot, delivery_days, tz, now_utc)
            candidates.append((dt, slot_str))
        except Exception:
            continue

    if not candidates:
        fallback_dt, fallback_slot = calculate_next_run("08:00", delivery_days, tz, now_utc)
        return fallback_dt, fallback_slot

    candidates.sort(key=lambda x: x[0])
    return candidates[0]


def format_time_delta(td: datetime.timedelta) -> str:
    """Format timedelta into human-readable countdown string (e.g. '4h 15m' or '1d 3h')."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "due now"
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# ── Profile Parsing & Vault Inspection ─────────────────────────────────────────

def parse_settings_md(profile_dir: Path) -> Dict[str, Any]:
    """Extract settings from profile settings.md."""
    settings_file = profile_dir / "settings.md"
    if not settings_file.is_file():
        raise FileNotFoundError(f"Missing settings.md in {profile_dir}")

    content = settings_file.read_text(encoding="utf-8")

    def _first(pattern: str, default: str) -> str:
        m = re.search(pattern, content, re.M)
        return m.group(1).strip() if m else default

    batch_time = _first(r'^[ \t]*batch_time:[ \t]*["\']?([0-9]{1,2}:[0-9]{2})["\']?', "03:00")
    timezone = _first(r'^[ \t]*timezone:[ \t]*["\']?([^#\n\r]+)["\']?', "Etc/UTC")
    email = _first(r'^[ \t]*email:[ \t]*["\']?([^#\n\r]+)["\']?', "")
    if email.lower() in ("null", "none", ""):
        email = None

    slot_times = ["08:00", "13:00", "18:00"]
    m_slots = re.search(r'^[ \t]*slot_times:[ \t]*\[(.*?)\]', content, re.M)
    if m_slots:
        parsed = [s.strip().strip("\"' ") for s in m_slots.group(1).split(",") if s.strip().strip("\"' ")]
        if parsed:
            slot_times = parsed

    delivery_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    m_days = re.search(r'^[ \t]*delivery_days:[ \t]*\[(.*?)\]', content, re.M)
    if m_days:
        parsed = [s.strip().strip("\"' ").lower() for s in m_days.group(1).split(",") if s.strip().strip("\"' ")]
        if parsed:
            delivery_days = parsed

    return {
        "batch_time": batch_time,
        "slot_times": slot_times,
        "delivery_days": delivery_days,
        "timezone": timezone.strip(),
        "email": email,
    }


def get_previous_sent_info(profile_dir: Path) -> Tuple[Optional[str], Optional[str], int]:
    """
    Read last delivered edition info from vault/editions.json and vault/state.json.
    Returns (delivered_at_iso, edition_id, total_delivered).
    """
    editions_file = profile_dir / "vault" / "editions.json"
    state_file = profile_dir / "vault" / "state.json"

    delivered_at = None
    edition_id = None
    total_delivered = 0

    if editions_file.is_file():
        try:
            editions = json.loads(editions_file.read_text(encoding="utf-8"))
            if isinstance(editions, list) and editions:
                total_delivered = len(editions)
                last_edition = editions[-1]
                delivered_at = last_edition.get("delivered_at") or last_edition.get("date")
                edition_id = last_edition.get("edition_id")
        except Exception:
            pass

    if not delivered_at and state_file.is_file():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            delivered_at = state.get("last_run")
            edition_id = state.get("last_edition_id")
            total_delivered = state.get("total_editions_delivered", total_delivered)
        except Exception:
            pass

    return delivered_at, edition_id, total_delivered


def check_outbox_readiness(profile_dir: Path, today_str: str) -> bool:
    """Check if an edition is currently compiled in outbox/ for today."""
    outbox_dir = profile_dir / "outbox" / today_str
    if not outbox_dir.is_dir():
        return False
    for f in outbox_dir.glob("slot-*-final.html"):
        if f.is_file() and f.stat().st_size > 0:
            return True
    return False


def inspect_profile_logs(profile_id: str) -> Tuple[str, str, Optional[str]]:
    """
    Scan profile logs for status and errors.
    Returns (status, error_encountered, last_run_timestamp).
    """
    sender_log = LOG_DIR / f"{profile_id}-sender.log"
    main_log = LOG_DIR / f"{profile_id}.log"
    batch_log = LOG_DIR / f"{profile_id}-batch.log"

    log_files = [f for f in [sender_log, main_log, batch_log] if f.is_file()]
    if not log_files:
        return "idle", "N/A", None

    entries = []
    ts_pattern = re.compile(r'\[([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[^\]]*)\]')

    for lf in log_files:
        try:
            mtime = lf.stat().st_mtime
            lines = lf.read_text(encoding="utf-8", errors="ignore").splitlines()
            current_ts = None
            for line in lines[-100:]:
                if not line.strip():
                    continue
                m = ts_pattern.search(line)
                if m:
                    current_ts = m.group(1)
                entries.append({
                    "file": lf.name,
                    "mtime": mtime,
                    "timestamp": current_ts,
                    "line": line.strip(),
                })
        except Exception:
            continue

    if not entries:
        return "idle", "N/A", None

    error_patterns = [
        r'(ERROR:.*)',
        r'(Error:.*)',
        r'(.*unbound variable.*)',
        r'(.*command not found.*)',
        r'(.*Traceback \(most recent call last\):.*)',
        r'(.*failed with exit code [1-9].*)',
        r'(.*Google Workspace token not found.*)',
        r'(.*refusing to send.*)',
    ]

    latest_run_ts = None
    for entry in reversed(entries):
        if entry["timestamp"]:
            latest_run_ts = entry["timestamp"]
            break

    last_error = None
    for entry in reversed(entries[-20:]):
        line = entry["line"]
        # Skip dry-run prompt content containing instructions or examples
        if "[DRY-RUN]" in line or "If the GWS script returns an error" in line or "prompt:" in line:
            continue
        for pat in error_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                matched_err = m.group(1).strip()
                clean_err = re.sub(r'^\[[^\]]+\]\s*', '', matched_err)
                last_error = clean_err
                break
        if last_error:
            break

    # Check lock file status
    sender_lock = LOCKS_DIR / f"{profile_id}-sender.lock"
    batch_lock = LOCKS_DIR / f"{profile_id}-batch.lock"
    for lock in [sender_lock, batch_lock]:
        if lock.is_file():
            age = int(datetime.datetime.now().timestamp() - lock.stat().st_mtime)
            if age > 7200:
                last_error = f"Stale lock detected ({lock.name}, age {age}s)"

    if last_error:
        return "fail", last_error, latest_run_ts

    return "success", "N/A", latest_run_ts



def get_crontab_status(profile_id: str, sched: Dict[str, Any]) -> str:
    """Check if profile crontab entries match live crontab."""
    res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if res.returncode != 0:
        return "missing"

    crontab = res.stdout
    batch_tag = f"newsletter-skill:{profile_id}-batch"
    send_tag = f"newsletter-skill:{profile_id}-send"

    has_batch = any(batch_tag in line and not line.strip().startswith("#") for line in crontab.splitlines())
    has_send = any(send_tag in line and not line.strip().startswith("#") for line in crontab.splitlines())

    if has_batch and has_send:
        return "in_sync"
    if has_batch or has_send:
        return "drift"
    return "missing"


# ── Aggregator Engine ──────────────────────────────────────────────────────────

def build_cron_summary(target_profile_id: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate full cron status summary across all profiles."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_utc.isoformat()
    today_str = now_utc.strftime("%Y-%m-%d")

    # Load registered profiles
    profiles_meta = []
    if REGISTRY_FILE.is_file():
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            profiles_meta = data.get("profiles", [])
        except Exception as e:
            sys.stderr.write(f"Warning: error reading registry.json: {e}\n")

    if not profiles_meta and PROFILES_ROOT.is_dir():
        for p in PROFILES_ROOT.iterdir():
            if p.is_dir() and (p / "settings.md").is_file():
                profiles_meta.append({"id": p.name, "enabled": True})

    if target_profile_id:
        profiles_meta = [p for p in profiles_meta if p["id"] == target_profile_id]

    items = []
    active_items = []
    failing_count = 0

    for meta in profiles_meta:
        pid = meta["id"]
        is_enabled = meta.get("enabled", True)
        p_dir = PROFILES_ROOT / pid

        if not p_dir.is_dir() or not (p_dir / "settings.md").is_file():
            items.append({
                "profile_id": pid,
                "user_email": "N/A",
                "is_active": False,
                "next_sending_schedule": "N/A",
                "next_sending_slot": "N/A",
                "next_batch_schedule": "N/A",
                "previous_sent": "Never",
                "status": "fail",
                "error_encountered": f"Profile directory or settings.md missing at {p_dir}",
                "delivery_days": [],
                "slot_times": [],
                "timezone": "Etc/UTC",
                "crontab_status": "missing",
                "details": {},
            })
            failing_count += 1
            continue

        try:
            sched = parse_settings_md(p_dir)
        except Exception as e:
            items.append({
                "profile_id": pid,
                "user_email": "N/A",
                "is_active": is_enabled,
                "next_sending_schedule": "N/A",
                "next_sending_slot": "N/A",
                "next_batch_schedule": "N/A",
                "previous_sent": "Never",
                "status": "fail",
                "error_encountered": f"Settings parse error: {e}",
                "delivery_days": [],
                "slot_times": [],
                "timezone": "Etc/UTC",
                "crontab_status": "missing",
                "details": {},
            })
            failing_count += 1
            continue

        tz = get_profile_timezone(sched["timezone"])
        user_email = sched["email"] or "N/A (present-file mode)"

        # Calculate next schedules
        next_send_dt, next_slot = calculate_next_send_slot(
            sched["slot_times"], sched["delivery_days"], tz, now_utc
        )
        next_batch_dt, _ = calculate_next_run(
            sched["batch_time"], sched["delivery_days"], tz, now_utc
        )

        prev_sent_iso, last_eid, total_delivered = get_previous_sent_info(p_dir)
        has_outbox = check_outbox_readiness(p_dir, today_str)
        log_status, log_error, last_log_ts = inspect_profile_logs(pid)
        crontab_stat = get_crontab_status(pid, sched)

        # Determine overall status
        status = log_status
        error_enc = log_error

        if not is_enabled:
            status = "paused"
            next_send_iso = "N/A (disabled)"
            next_batch_iso = "N/A (disabled)"
            time_until = "N/A"
        else:
            next_send_iso = next_send_dt.isoformat()
            next_batch_iso = next_batch_dt.isoformat()
            time_until = format_time_delta(next_send_dt - now_utc)

            if crontab_stat == "missing" and status == "success":
                # Mark as warning drift if crontab not installed
                error_enc = "Crontab entries missing (run manage_cron.py sync)"
                status = "fail"
            elif has_outbox and status == "success":
                status = "ready"

        if status == "fail":
            failing_count += 1

        profile_summary = {
            "profile_id": pid,
            "user_email": user_email,
            "is_active": is_enabled,
            "next_sending_schedule": next_send_iso,
            "next_sending_slot": next_slot,
            "time_until_next_send": time_until,
            "next_batch_schedule": next_batch_iso,
            "previous_sent": prev_sent_iso or "Never",
            "status": status,
            "error_encountered": error_enc,
            "delivery_days": sched["delivery_days"],
            "slot_times": sched["slot_times"],
            "timezone": sched["timezone"],
            "crontab_status": crontab_stat,
            "details": {
                "outbox_ready": has_outbox,
                "latest_edition_id": last_eid,
                "total_editions_delivered": total_delivered,
                "last_run_timestamp": last_log_ts,
            },
            "_sort_dt": next_send_dt if is_enabled else datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
        }

        items.append(profile_summary)
        if is_enabled:
            active_items.append(profile_summary)

    # Sort active items to find immediate next recipient
    active_items.sort(key=lambda x: x["_sort_dt"])
    next_recipient = None
    if active_items:
        first = active_items[0]
        next_recipient = {
            "profile_id": first["profile_id"],
            "user_email": first["user_email"],
            "next_sending_schedule": first["next_sending_schedule"],
            "next_sending_slot": first["next_sending_slot"],
            "time_until_send": first["time_until_next_send"],
        }

    # Clean up internal sort keys
    for item in items:
        item.pop("_sort_dt", None)

    summary_doc = {
        "generated_at": now_iso,
        "summary": {
            "total_profiles": len(items),
            "active_profiles": len(active_items),
            "disabled_profiles": len(items) - len(active_items),
            "next_recipient_profile": next_recipient["profile_id"] if next_recipient else None,
            "next_recipient_email": next_recipient["user_email"] if next_recipient else None,
            "next_sending_schedule": next_recipient["next_sending_schedule"] if next_recipient else None,
            "time_until_next_send": next_recipient["time_until_send"] if next_recipient else None,
            "failing_profiles_count": failing_count,
        },
        "cron_summary": items,
    }

    return summary_doc


def save_summary_file(data: Dict[str, Any]) -> None:
    """Save summary data to cron/cron-summary.json."""
    try:
        SUMMARY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Failed to write summary to {SUMMARY_FILE}: {e}\n")


# ── CLI Visual Rendering ───────────────────────────────────────────────────────

def render_summary_table(data: Dict[str, Any]) -> None:
    """Render a clean, formatted ASCII queue overview table to terminal."""
    sm = data["summary"]
    items = data["cron_summary"]
    width = 76

    print()
    print("╔" + "═" * (width - 2) + "╗")
    print(f"║{'Newsletter Cron & Delivery Queue Summary':^{width-2}}║")
    print(f"║{data['generated_at']:^{width-2}}║")
    print("╚" + "═" * (width - 2) + "╝")

    if sm["next_recipient_profile"]:
        print()
        print(f"  🎯 NEXT RECIPIENT IN QUEUE:")
        print(f"     Email:    {sm['next_recipient_email']} (Profile: {sm['next_recipient_profile']})")
        print(f"     Schedule: {sm['next_sending_schedule']} (in {sm['time_until_next_send']})")
    else:
        print("\n  🎯 NEXT RECIPIENT: None scheduled (no active profiles)")

    print()
    print("─" * width)
    print(f"  {'Profile / Email':<30}  {'Next Send':<16}  {'Prev Sent':<14}  {'Status'}")
    print(f"  {'-'*30}  {'-'*16}  {'-'*14}  {'-'*10}")

    for it in items:
        disp_email = it["user_email"]
        if len(disp_email) > 28:
            disp_email = disp_email[:25] + "..."
        profile_line = f"{it['profile_id']} ({disp_email})"
        if len(profile_line) > 30:
            profile_line = profile_line[:27] + "..."

        # Next send display
        if not it["is_active"]:
            next_disp = "PAUSED"
        else:
            next_disp = f"{it['next_sending_slot']} ({it['time_until_next_send']})"

        # Prev sent display
        prev_raw = it["previous_sent"]
        if prev_raw and prev_raw != "Never":
            prev_disp = prev_raw[:10]
        else:
            prev_disp = "Never"

        # Status icon
        st = it["status"].upper()
        if st == "SUCCESS":
            status_disp = "✅ SUCCESS"
        elif st == "READY":
            status_disp = "📬 READY"
        elif st == "PAUSED":
            status_disp = "⏸️  PAUSED"
        elif st == "FAIL":
            status_disp = "❌ FAIL"
        else:
            status_disp = f"⚪ {st}"

        print(f"  {profile_line:<30}  {next_disp:<16}  {prev_disp:<14}  {status_disp}")

        if it["error_encountered"] != "N/A":
            print(f"     ⚠️  Error: {it['error_encountered']}")

    print("─" * width)
    print(f"  Total Profiles: {sm['total_profiles']} | Active: {sm['active_profiles']} | Failing: {sm['failing_profiles_count']}")
    print(f"  JSON Summary:   {SUMMARY_FILE}")
    print()


# ── Main Entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Newsletter Cron & Delivery Summary Tool")
    parser.add_argument("--profile", "-p", help="Filter summary for a specific profile ID")
    parser.add_argument("--json", action="store_true", help="Output raw JSON to stdout")
    parser.add_argument("--no-save", action="store_true", help="Do not write to cron/cron-summary.json")
    args = parser.parse_args()

    summary_data = build_cron_summary(target_profile_id=args.profile)

    if not args.no_save:
        save_summary_file(summary_data)

    if args.json:
        print(json.dumps(summary_data, indent=2))
    else:
        render_summary_table(summary_data)

    sys.exit(0 if summary_data["summary"]["failing_profiles_count"] == 0 else 1)


if __name__ == "__main__":
    main()
