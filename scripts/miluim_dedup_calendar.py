#!/usr/bin/env python3
"""Remove duplicate events from the miluim calendar."""

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

CALENDAR_ID = "c_3f7146c58ca8377fbfb00e3dad5d0f9dc229ec0babb155335f36c2a9e1302868@group.calendar.google.com"
TIME_MIN = "2024-01-01T00:00:00Z"
TIME_MAX = "2027-01-01T00:00:00Z"


def extract_json(stdout: str) -> dict | list:
    start = stdout.find("{")
    if start == -1:
        start = stdout.find("[")
        end = stdout.rfind("]") + 1
    else:
        end = stdout.rfind("}") + 1
    return json.loads(stdout[start:end])


def normalize_name(name: str) -> str:
    # Normalize Hebrew apostrophe variants to U+0027
    return name.replace("\u05f3", "'").replace("\u2019", "'")


def fetch_all_events() -> list:
    events = []
    page_token = None
    page = 0

    while True:
        page += 1
        params = {
            "calendarId": CALENDAR_ID,
            "timeMin": TIME_MIN,
            "timeMax": TIME_MAX,
            "maxResults": 250,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if page_token:
            params["pageToken"] = page_token

        cmd = [
            "gws", "calendar", "events", "list",
            "--params", json.dumps(params),
            "--format", "json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"ERROR fetching page {page}: {result.stderr}", file=sys.stderr)
            break

        data = extract_json(result.stdout)
        batch = data.get("items", [])
        events.extend(batch)
        print(f"  Page {page}: fetched {len(batch)} events (total so far: {len(events)})")

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return events


def parse_summary(summary: str):
    """Parse '{person} - משמרת {shift_type} - {team_name}' → (person, shift_type, team)."""
    # Match pattern with Hebrew text
    match = re.match(r"^(.+?)\s*-\s*משמרת\s+(.+?)\s*-\s*(.+)$", summary.strip())
    if not match:
        return None
    person = normalize_name(match.group(1).strip())
    shift_type = match.group(2).strip()
    team = match.group(3).strip()
    return person, shift_type, team


def event_date(event: dict) -> str:
    start = event.get("start", {})
    dt = start.get("dateTime") or start.get("date", "")
    # Take just the date portion
    return dt[:10]


def delete_event(event_id: str) -> bool:
    params = {"calendarId": CALENDAR_ID, "eventId": event_id}
    cmd = [
        "gws", "calendar", "events", "delete",
        "--params", json.dumps(params),
        "--format", "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0


def main():
    print("Fetching all events...")
    events = fetch_all_events()
    print(f"\nTotal events fetched: {len(events)}")

    # Group by dedup key
    groups: dict[str, list] = defaultdict(list)
    unparseable = 0

    for event in events:
        summary = event.get("summary", "")
        parsed = parse_summary(summary)
        if not parsed:
            unparseable += 1
            continue
        person, shift_type, team = parsed
        date = event_date(event)
        key = f"{date}|{shift_type}|{person}|{team}"
        groups[key].append(event)

    print(f"Unparseable events (skipped): {unparseable}")

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    total_to_delete = sum(len(v) - 1 for v in duplicates.values())
    print(f"Duplicate groups found: {len(duplicates)}")
    print(f"Events to delete: {total_to_delete}\n")

    if not duplicates:
        print("No duplicates found. Nothing to do.")
        return

    deleted = 0
    errors = 0

    for key, group in sorted(duplicates.items()):
        # Sort by creation time to keep the first created
        group_sorted = sorted(group, key=lambda e: e.get("created", ""))
        keep = group_sorted[0]
        to_delete = group_sorted[1:]

        print(f"Key: {key}")
        print(f"  Keeping : {keep['id']} (created {keep.get('created', '?')})")

        for event in to_delete:
            eid = event["id"]
            print(f"  Deleting: {eid} (created {event.get('created', '?')}) ... ", end="", flush=True)
            if delete_event(eid):
                print("OK")
                deleted += 1
            else:
                print("ERROR")
                errors += 1

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Duplicate groups : {len(duplicates)}")
    print(f"  Deleted          : {deleted}")
    print(f"  Errors           : {errors}")


if __name__ == "__main__":
    main()
