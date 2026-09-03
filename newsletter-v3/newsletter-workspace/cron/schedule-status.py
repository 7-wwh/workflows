#!/usr/bin/env python3
"""
schedule-status.py — On-demand newsletter cron schedule visibility tool

Reads profiles/registry.json + each profile's settings.md, compares against
the live system crontab, and prints a human-readable comparison table showing
exactly what SHOULD be scheduled and what IS registered.

Usage:
    python3 cron/schedule-status.py [--profile <id>] [--json]
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WS_ROOT = SCRIPT_DIR.parent
PROFILES_ROOT = WS_ROOT / "profiles"
REGISTRY_FILE = PROFILES_ROOT / "registry.json"
MAINTAIN_LOG = SCRIPT_DIR / "logs" / "maintain.log"


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_system_crontab() -> str:
    res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def get_crontab_entry_for_tag(tag: str, crontab: str) -> str | None:
    for line in crontab.splitlines():
        if f"# {tag}" in line and not line.strip().startswith("#"):
            parts = line.strip().split()
            if len(parts) >= 5:
                return " ".join(parts[:5])
    return None


def get_registered_profiles():
    if not REGISTRY_FILE.is_file():
        profiles = []
        if PROFILES_ROOT.is_dir():
            for p in PROFILES_ROOT.iterdir():
                if p.is_dir() and (p / "settings.md").is_file():
                    profiles.append({"id": p.name, "enabled": True})
        return profiles
    data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return [p for p in data.get("profiles", []) if p.get("enabled", True)]


def parse_settings(profile_dir: Path) -> dict:
    content = (profile_dir / "settings.md").read_text(encoding="utf-8")

    def _first(pattern, default):
        m = re.search(pattern, content, re.M)
        return m.group(1).strip() if m else default

    batch_time = _first(r'^[ \t]*batch_time:[ \t]*["\']?([0-9]{1,2}:[0-9]{2})["\']?', "03:00")
    timezone = _first(r'^[ \t]*timezone:[ \t]*["\']?([^#\n\r]+)["\']?', "UTC")
    email = _first(r'^[ \t]*email:[ \t]*["\']?([^#\n\r]+)["\']?', "")
    if email.lower() in ("null", "none", ""):
        email = None

    m_slots = re.search(r'^[ \t]*slot_times:[ \t]*\[(.*?)\]', content, re.M)
    slot_times = ["08:00", "13:00", "18:00"]
    if m_slots:
        parsed = [s.strip().strip("\"' ") for s in m_slots.group(1).split(",") if s.strip().strip("\"' ")]
        if parsed:
            slot_times = parsed

    m_days = re.search(r'^[ \t]*delivery_days:[ \t]*\[(.*?)\]', content, re.M)
    delivery_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
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


def days_to_cron_dow(days: list[str]) -> str:
    day_map = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
    nums = sorted(set(day_map[d] for d in days if d in day_map))
    if len(nums) == 7 or not nums:
        return "*"
    return ",".join(str(n) for n in nums)


def time_to_cron(time_str: str, dow: str = "*") -> str:
    parts = time_str.split(":")
    return f"{int(parts[1]) if len(parts) > 1 else 0} {int(parts[0])} * * {dow}"


def slot_times_to_cron(slot_times: list[str], dow: str = "*") -> str:
    if not slot_times:
        return f"0 8,13,18 * * {dow}"
    parsed = [(int(s.split(":")[0]), int(s.split(":")[1]) if ":" in s else 0) for s in slot_times]
    minutes = sorted(set(p[1] for p in parsed))
    hours = sorted(set(p[0] for p in parsed))
    minute = minutes[0]
    hours_str = ",".join(str(h) for h in hours)
    return f"{minute} {hours_str} * * {dow}"


def get_last_maintain_run() -> str | None:
    if not MAINTAIN_LOG.is_file():
        return None
    lines = MAINTAIN_LOG.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if "Nightly Maintain Mode Completed" in line:
            return line.strip()
    return None


# ── Rendering ─────────────────────────────────────────────────────────────────

TICK = "✓"
CROSS = "✗"
OK_ICON = "✅"
WARN_ICON = "⚠️ "


def render_text(results: list[dict], maintain_result: dict, now_str: str):
    width = 66
    print()
    print("╔" + "═" * (width - 2) + "╗")
    print(f"║{'Newsletter Cron Schedule Status':^{width-2}}║")
    print(f"║{now_str:^{width-2}}║")
    print("╚" + "═" * (width - 2) + "╝")

    for r in results:
        print()
        pid = r["profile_id"]
        email = r["settings"]["email"] or "(no email set — present-file mode)"
        print(f"Profile: {pid}  ({email})")
        sched = r["settings"]
        slots_str = ", ".join(sched["slot_times"])
        days_str = ", ".join(sched["delivery_days"])
        print(f"  Settings : batch={sched['batch_time']}  slots=[{slots_str}]  tz={sched['timezone']}")
        print(f"             days=[{days_str}]")
        print()
        print(f"  {'Job':<12}  {'Expected cron expr':<22}  {'Live crontab':}")
        print(f"  {'-'*12}  {'-'*22}  {'-'*22}")

        for entry in r["entries"]:
            live_display = entry["actual"] if entry["actual"] else "(missing)"
            icon = TICK if entry["in_sync"] else CROSS
            print(f"  {entry['label']:<12}  {entry['expected']:<22}  {live_display:<22}  {icon}")

        status_icon = OK_ICON if r["in_sync"] else WARN_ICON
        status_text = "IN SYNC" if r["in_sync"] else "DRIFT DETECTED"
        print()
        print(f"  Status: {status_icon} {status_text}")
        if not r["in_sync"]:
            print(f"  Fix:    python3 {WS_ROOT}/cron/manage_cron.py sync --profile {pid}")

    # Maintain entry
    print()
    print("─" * width)
    m = maintain_result
    live_display = m["actual"] if m["actual"] else "(missing)"
    icon = TICK if m["in_sync"] else CROSS
    print(f"  {'maintain':<12}  {m['expected']:<22}  {live_display:<22}  {icon}")
    if not m["in_sync"]:
        print(f"  Fix:    python3 {WS_ROOT}/cron/manage_cron.py sync")

    # Last run
    print()
    last = get_last_maintain_run()
    if last:
        # Extract timestamp and status from log line like "[2026-09-03T02:30:01Z] === ...HEALTHY..."
        status_word = "HEALTHY" if "HEALTHY" in last else ("REPAIRED" if "REPAIRED" in last else "UNKNOWN")
        m_ts = re.search(r'\[([^\]]+)\]', last)
        ts = m_ts.group(1) if m_ts else "?"
        icon = OK_ICON if status_word == "HEALTHY" else WARN_ICON
        print(f"Last maintain run: {ts} — {icon} {status_word}")
        print(f"Log: {MAINTAIN_LOG}")
    else:
        print(f"Last maintain run: (no completed run found in {MAINTAIN_LOG})")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Newsletter Cron Schedule Status Viewer")
    parser.add_argument("--profile", "-p", help="Target profile ID (default: all)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    crontab = get_system_crontab()

    all_profiles = get_registered_profiles()
    if args.profile:
        all_profiles = [p for p in all_profiles if p["id"] == args.profile]
        if not all_profiles:
            all_profiles = [{"id": args.profile, "enabled": True}]

    results = []
    for p in all_profiles:
        pid = p["id"]
        p_dir = PROFILES_ROOT / pid
        if not p_dir.is_dir() or not (p_dir / "settings.md").is_file():
            results.append({
                "profile_id": pid,
                "error": f"Profile directory or settings.md not found at {p_dir}",
                "in_sync": False,
                "entries": [],
                "settings": {},
            })
            continue

        sched = parse_settings(p_dir)
        dow = days_to_cron_dow(sched["delivery_days"])
        expected_batch = time_to_cron(sched["batch_time"], dow)
        expected_send = slot_times_to_cron(sched["slot_times"], dow)

        batch_actual = get_crontab_entry_for_tag(f"newsletter-skill:{pid}-batch", crontab)
        send_actual = get_crontab_entry_for_tag(f"newsletter-skill:{pid}-send", crontab)

        batch_in_sync = batch_actual == expected_batch
        send_in_sync = send_actual == expected_send

        entries = [
            {"label": "batch", "expected": expected_batch, "actual": batch_actual, "in_sync": batch_in_sync},
            {"label": "send", "expected": expected_send, "actual": send_actual, "in_sync": send_in_sync},
        ]

        results.append({
            "profile_id": pid,
            "settings": sched,
            "entries": entries,
            "in_sync": batch_in_sync and send_in_sync,
        })

    # Maintain entry check
    maintain_expected = "30 2 * * *"
    maintain_actual = get_crontab_entry_for_tag("newsletter-skill:maintain-all", crontab)
    maintain_result = {
        "label": "maintain",
        "expected": maintain_expected,
        "actual": maintain_actual,
        "in_sync": maintain_actual == maintain_expected,
    }

    if args.json:
        output = {
            "timestamp": now_str,
            "profiles": results,
            "maintain": maintain_result,
        }
        print(json.dumps(output, indent=2))
        sys.exit(0 if all(r.get("in_sync") for r in results) and maintain_result["in_sync"] else 1)

    render_text(results, maintain_result, now_str)
    all_ok = all(r.get("in_sync") for r in results) and maintain_result["in_sync"]
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
