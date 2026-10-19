from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .collectors import collect_all

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "data" / "snapshots"
LATEST = ROOT / "data" / "latest.json"
ACTIVITY = ROOT / "data" / "activity-log.json"
STATE = ROOT / "data" / "state.json"
IST = ZoneInfo("Asia/Kolkata")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def stable_source(data: dict) -> dict:
    """Remove collection timestamp so unchanged profiles don't look like new activity."""
    return {name: value for name, value in data.get("sources", {}).items()}


def signature(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_events(previous: dict, current: dict, date: str) -> list[dict]:
    events = []
    old_sources = previous.get("sources", {})
    for source, current_wrap in current.get("sources", {}).items():
        if current_wrap.get("status") != "ok":
            continue
        current_data = current_wrap.get("data", {})
        old_wrap = old_sources.get(source, {})
        old_data = old_wrap.get("data", {}) if old_wrap.get("status") == "ok" else {}
        if source == "leetcode":
            old_ids = {str(x.get("id")) for x in old_data.get("recent_accepted_submissions", []) if x.get("id")}
            for item in current_data.get("recent_accepted_submissions", []):
                item_id = str(item.get("id", ""))
                if item_id and item_id not in old_ids:
                    events.append({"date_observed": date, "source": source, "type": "new_accepted_submission_observed", "details": item})
        elif source == "google_skills":
            old_badges = set(old_data.get("earned_badges", []))
            for badge in current_data.get("earned_badges", []):
                if badge not in old_badges:
                    events.append({"date_observed": date, "source": source, "type": "new_badge_observed", "details": {"badge": badge}})
        elif source == "geeksforgeeks":
            old_total = old_data.get("total_problems_solved")
            new_total = current_data.get("total_problems_solved")
            if isinstance(old_total, int) and isinstance(new_total, int) and new_total > old_total:
                events.append({"date_observed": date, "source": source, "type": "solved_count_increased", "details": {"previous_total": old_total, "current_total": new_total, "increase": new_total - old_total}})
        # Generic metric changes are recorded as observations, not claimed as exact activity dates.
        if source == "leetcode" and old_data.get("accepted_problem_counts") != current_data.get("accepted_problem_counts") and old_data:
            old_counts = old_data.get("accepted_problem_counts", {})
            new_counts = current_data.get("accepted_problem_counts", {})
            if new_counts != old_counts and not any(e["source"] == source and e["type"] == "new_accepted_submission_observed" for e in events):
                events.append({"date_observed": date, "source": source, "type": "aggregate_stats_changed", "details": {"previous": old_counts, "current": new_counts}})
    return events


def main() -> int:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    date = datetime.now(IST).date().isoformat()
    current = collect_all()
    previous = read_json(LATEST, {})
    successful = sum(1 for item in current["sources"].values() if item.get("status") == "ok")
    print(f"Collected {successful}/3 sources successfully.")
    for name, source in current["sources"].items():
        print(f"- {name}: {source.get('status')}")
        if source.get("status") == "error":
            print(f"  {source.get('error')}")

    if successful == 0:
        print("No source succeeded; keeping prior snapshots unchanged.", file=sys.stderr)
        return 1

    # Snapshot is a date-stamped view. Do not overwrite a successful source with a failed fetch.
    merged = {"schema_version": 1, "collected_at_utc": current["collected_at_utc"], "sources": {}}
    old_sources = previous.get("sources", {})
    for name, item in current["sources"].items():
        if item.get("status") == "ok":
            merged["sources"][name] = item
        elif name in old_sources:
            merged["sources"][name] = old_sources[name]
        else:
            merged["sources"][name] = item

    events = build_events(previous, merged, date) if previous else []
    snapshot_path = SNAPSHOTS / f"{date}.json"
    snapshot_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LATEST.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    log = read_json(ACTIVITY, [])
    known = {signature(event) for event in log}
    added = 0
    for event in events:
        if signature(event) not in known:
            log.append(event)
            known.add(signature(event))
            added += 1
    log.sort(key=lambda e: (e.get("date_observed", ""), e.get("source", ""), e.get("type", "")))
    ACTIVITY.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    state = read_json(STATE, {})
    state.update({"last_checked_ist_date": date, "successful_sources": successful, "new_events_this_run": added})
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {snapshot_path.relative_to(ROOT)}; new observed events: {added}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
