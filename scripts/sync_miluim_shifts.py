#!/usr/bin/env python3
"""
Daily sync: read miluim shift sheet → update calendar events.
Adds new shifts, updates changed assignments. Never deletes.
"""

import subprocess
import json
import re
import sys
from datetime import datetime, timedelta

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
SHEET_RANGE = "משמרות הערכה ועיבוד"
CALENDAR_ID = "c_3f7146c58ca8377fbfb00e3dad5d0f9dc229ec0babb155335f36c2a9e1302868@group.calendar.google.com"
TZ = "+03:00"  # Israel DST

# Color map per person (include both straight' and curly’ apostrophe variants)
def _colors():
    base = {
        "עומר נשר": "9", "ינון סגרון": "6", "רוני טפר": "3",
        "עומר כהן": "7", "ניתאי יפה": "5", "אריה קלמן": "10",
        "נדב הכץ": "1", "אריה וינטר": "4",
        "שני בוזגלו": "11", "יאיר ברימן": "8", "אלעד סבן": "8",
    }
    # Handle both apostrophe variants
    result = {}
    for k, v in base.items():
        result[k] = v
        if "'" in k:
            result[k.replace("'", "\u2019")] = v
    result["נדב רבינוביץ'"] = "2"
    result["נדב רבינוביץ\u2019"] = "2"
    return result

COLORS = _colors()

def norm(s):
    """Normalize name: strip, collapse whitespace, normalize apostrophe."""
    s = s.strip()
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r'\s+', ' ', s)


def gws(*args):
    """Run gws command, return parsed JSON."""
    result = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"GWS ERROR: {' '.join(args[:3])} | {result.stderr[:200]}", file=sys.stderr)
        return None
    # Strip the "Using keyring..." preamble, find the JSON object
    text = result.stdout.strip()
    # Find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end+1])
    except json.JSONDecodeError as e:
        print(f"JSON PARSE ERROR: {e}", file=sys.stderr)
        return None


def parse_date(d):
    """Parse '06/05/26' to date object."""
    return datetime.strptime(d.strip(), "%d/%m/%y")


def read_sheet():
    """Parse all shifts from the sheet. Returns dict:
    {(date_str, shift_type, role): officer_name}
    shift_type: 'morning' | 'night'
    role: 'הערכה' | 'עיבוד'
    """
    data = gws("sheets", "+read", "--spreadsheet", SHEET_ID, "--range", SHEET_RANGE, "--format", "json")
    if not data:
        return {}

    values = data.get("values", [])
    
    # Row indices (0-based)
    # Row 2 (idx 2): header dates for both sections
    # Row 3 (idx 3): evaluation morning
    # Row 4 (idx 4): evaluation night
    # Row 7 (idx 7): analysis morning
    # Row 8 (idx 8): analysis night
    
    if len(values) < 10:
        print(f"Sheet has {len(values)} rows, expected at least 10", file=sys.stderr)
        return {}
    
    header = values[2]  # Dates row
    eval_morning = values[3]
    eval_night = values[4]
    anal_morning = values[8]
    anal_night = values[9]
    
    shifts = {}
    
    def add_shifts(row, role, shift_type):
        """Parse a row of assignments."""
        for col_idx in range(1, len(row)):
            name = norm(row[col_idx] if col_idx < len(row) else "")
            date_cell = header[col_idx] if col_idx < len(header) else ""
            
            # Skip blank separators and empty cells
            if not name or not date_cell or not date_cell.strip():
                continue
            name = name.strip()
            date_cell = date_cell.strip()
            
            # Extract date from "Wednesday,  06/05/26" format
            # Find pattern DD/MM/YY anywhere in the cell
            m = re.search(r'(\d{2})/(\d{2})/(\d{2})', date_cell)
            if not m:
                continue
            date_str = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
            
            try:
                dt = parse_date(date_str)
            except ValueError:
                continue
            
            date_key = dt.strftime("%Y-%m-%d")
            shifts[(date_key, shift_type, role)] = name
    
    add_shifts(eval_morning, "הערכה", "morning")
    add_shifts(eval_night, "הערכה", "night")
    add_shifts(anal_morning, "עיבוד", "morning")
    add_shifts(anal_night, "עיבוד", "night")
    
    return shifts


def read_calendar():
    """Parse all events from the calendar. Returns dict:
    {(date_str, shift_type, role): {officer_name, event_id, summary}}
    """
    data = gws("calendar", "events", "list",
               "--params", json.dumps({"calendarId": CALENDAR_ID, "maxResults": 250}),
               "--format", "json")
    if not data:
        return {}
    
    items = data.get("items", [])
    events = {}
    
    for item in items:
        summary = item.get("summary", "")
        event_id = item.get("id", "")
        start = item.get("start", {})
        
        # Parse summary: "שם - משמרת בוקר/לילה - הערכה/עיבוד"
        m = re.match(r'^(.+?) - משמרת (בוקר|לילה) - (הערכה|עיבוד)$', summary)
        if not m:
            continue
        
        officer = norm(m.group(1).strip())
        shift_hebrew = m.group(2)  # בוקר or לילה
        role = m.group(3)  # הערכה or עיבוד
        shift_type = "morning" if shift_hebrew == "בוקר" else "night"
        
        # Get date from start time
        dt_str = start.get("dateTime", "")
        if not dt_str:
            continue
        dt = datetime.fromisoformat(dt_str)
        date_key = dt.strftime("%Y-%m-%d")
        
        key = (date_key, shift_type, role)
        events[key] = {"officer": officer, "event_id": event_id, "summary": summary}
    
    return events


def create_event(date_key, shift_type, role, officer):
    """Create a single calendar event."""
    dt = datetime.strptime(date_key, "%Y-%m-%d")
    date_str = dt.strftime("%d/%m")
    shift_hebrew = "בוקר" if shift_type == "morning" else "לילה"
    
    if shift_type == "morning":
        start_iso = f"{date_key}T06:00:00{TZ}"
        end_iso = f"{date_key}T18:00:00{TZ}"
        paired_role = "עיבוד" if role == "הערכה" else "הערכה"
    else:
        start_iso = f"{date_key}T18:00:00{TZ}"
        next_day = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        end_iso = f"{next_day}T06:00:00{TZ}"
        paired_role = "עיבוד" if role == "הערכה" else "הערכה"
    
    # Check if there's a paired officer in the calendar (to show in description)
    # We'll leave it generic since we don't know the pair at creation time
    
    summary = f"{officer} - משמרת {shift_hebrew} - {role}"
    desc = f"משמרת {shift_hebrew} ({date_str})\nתפקיד: {role}\nשעות: {'06:00-18:00' if shift_type == 'morning' else '18:00-06:00'}"
    color_id = COLORS.get(officer, "")
    
    event_body = {
        "summary": summary,
        "description": desc,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Jerusalem"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Jerusalem"},
    }
    if color_id:
        event_body["colorId"] = color_id
    
    result = subprocess.run(
        ["gws", "calendar", "events", "insert",
         "--params", json.dumps({"calendarId": CALENDAR_ID}),
         "--json", json.dumps(event_body),
         "--format", "json"],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode == 0:
        print(f"  ✓ CREATED: {summary}")
        return True
    else:
        print(f"  ✗ FAILED: {summary} | {result.stderr[:100]}", file=sys.stderr)
        return False


def update_event(event_id, old_summary, new_officer, role, shift_type):
    """Update an event's officer name (and description if needed)."""
    shift_hebrew = "בוקר" if shift_type == "morning" else "לילה"
    new_summary = f"{new_officer} - משמרת {shift_hebrew} - {role}"
    color_id = COLORS.get(new_officer, "")
    
    event_body = {"summary": new_summary}
    if color_id:
        event_body["colorId"] = color_id
    
    result = subprocess.run(
        ["gws", "calendar", "events", "patch",
         "--params", json.dumps({"calendarId": CALENDAR_ID, "eventId": event_id}),
         "--json", json.dumps(event_body),
         "--format", "json"],
        capture_output=True, text=True, timeout=15
    )
    
    if result.returncode == 0:
        print(f"  ✓ UPDATED: {old_summary[:30]}… → {new_summary}")
        return True
    else:
        print(f"  ✗ FAIL UPDATE: {old_summary[:30]}… | {result.stderr[:100]}", file=sys.stderr)
        return False


def sync():
    # Self-destruct: if running as cron after July 12, auto-remove
    today = datetime.now()
    if today >= datetime(2026, 7, 12):
        print("Past July 12 — self-destructing this cron job.")
        print("Calendar remains as-is for reference.")
        # Find and remove this cron job by name
        list_result = subprocess.run(
            ["hermes", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=10
        )
        for line in list_result.stdout.strip().split("\n"):
            if "sync-miluim-shifts" in line or "sync_miluim_shifts" in line:
                # Try to extract job_id from the line
                import shlex
                parts = line.strip().split()
                if parts:
                    jid = parts[0]
                    subprocess.run(
                        ["hermes", "cron", "remove", jid],
                        capture_output=True, timeout=10
                    )
                    break
        return 0

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reading sheet...")
    sheet_shifts = read_sheet()
    print(f"  Sheet: {len(sheet_shifts)} shifts found")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reading calendar...")
    cal_events = read_calendar()
    print(f"  Calendar: {len(cal_events)} events found")
    
    added = 0
    updated = 0
    
    # Compare: what's in the sheet that needs to be in the calendar
    for key, officer in sorted(sheet_shifts.items()):
        date_key, shift_type, role = key
        
        if key in cal_events:
            existing = cal_events[key]
            if existing["officer"] != officer:
                print(f"  CHANGE: {date_key} {shift_type} {role}: {existing['officer']} → {officer}")
                if update_event(existing["event_id"], existing["summary"], officer, role, shift_type):
                    updated += 1
            # else: no change, skip
        else:
            print(f"  NEW: {date_key} {shift_type} {role}: {officer}")
            if create_event(date_key, shift_type, role, officer):
                added += 1
    
    # Check for events in calendar not in sheet (potential stale/deleted)
    orphans = set(cal_events.keys()) - set(sheet_shifts.keys())
    if orphans:
        print(f"  NOTE: {len(orphans)} events in calendar not in sheet (not deleted):")
        for key in sorted(orphans):
            print(f"    - {key[0]} {key[1]} {key[2]}: {cal_events[key]['officer']}")
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Sync complete: {added} added, {updated} updated")
    return added + updated


if __name__ == "__main__":
    changes = sync()
    if changes > 0:
        print(f"\n{changes} changes applied.")
    else:
        print("\nNo changes needed — calendar is up to date.")
