#!/usr/bin/env python3
"""
Miluim Calendar Sync v2 — gws CLI direct approach.
Reads prod tab, parses shifts, creates missing calendar events.
Color-coded by person. Never deletes events.
Normalizes all apostrophe/geresh variants to U+0027.
"""
import json
import subprocess
import re
from datetime import datetime, timedelta, timezone

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
PROD_TAB = "משמרות הערכה ועיבוד"
CALENDAR_ID = "c_3f7146c58ca8377fbfb00e3dad5d0f9dc229ec0babb155335f36c2a9e1302868@group.calendar.google.com"

# Normalize all apostrophe-like characters to regular apostrophe U+0027
APOSTROPHE_CHARS = '\u05f3\u2019\u2018\u02bc'
APO_TABLE = str.maketrans(APOSTROPHE_CHARS, "'" * len(APOSTROPHE_CHARS))

def norm(s):
    """Normalize name: strip, collapse whitespace, fix apostrophe variants"""
    s = s.strip()
    s = s.translate(APO_TABLE)
    s = re.sub(r'\s+', ' ', s)
    return s

PERSON_COLORS = {
    norm("נדב הכץ"): "1",
    norm("נדב רבינוביץ'"): "2",
    norm("רוני טפר"): "3",
    norm("אריה וינטר"): "4",
    norm("ניתאי יפה"): "5",
    norm("ינון סגרון"): "6",
    norm("עומר כהן"): "7",
    norm("אלעד סבן"): "8",
    norm("עומר נשר"): "9",
    norm("אריה קלמן"): "10",
    norm("יאיר ברימן"): "11",
    norm("שני בוזגלו"): "11",
}
DEFAULT_COLOR = "1"

# Also store raw key->color for direct match first
RAW_PERSON_COLORS = {}
for k, v in PERSON_COLORS.items():
    RAW_PERSON_COLORS[k] = v

def run_gws(args, timeout=60):
    """Run gws CLI and return parsed JSON"""
    cmd = ['gws'] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"GWS ERROR (exit {r.returncode}): {r.stderr[:500]}")
        return None
    raw = r.stdout
    s, e = raw.find('{'), raw.rfind('}')
    if s >= 0 and e >= 0:
        return json.loads(raw[s:e+1])
    print(f"Could not find JSON in output: {raw[:200]}")
    return None

def extract_dates_and_shifts(data_rows, header_row_idx, morning_row_idx, night_row_idx, team_name):
    shifts = []
    if not data_rows or header_row_idx >= len(data_rows):
        return shifts

    headers = data_rows[header_row_idx]
    morning = data_rows[morning_row_idx] if morning_row_idx < len(data_rows) else []
    night = data_rows[night_row_idx] if night_row_idx < len(data_rows) else []

    for col_idx in range(1, len(headers)):
        date_raw = str(headers[col_idx]).strip() if col_idx < len(headers) and headers[col_idx] else ""
        if not date_raw:
            continue

        m = re.search(r'(\d{2})/(\d{2})/(\d{2})', date_raw)
        if not m:
            continue
        day, month, year_short = m.group(1), m.group(2), m.group(3)
        date_str = f"{day}/{month}/20{year_short}"

        if col_idx < len(morning):
            person = str(morning[col_idx]).strip() if morning[col_idx] else ""
            if person and person.lower() not in ('none', '0', '') and person != 'nan':
                shifts.append((date_str, "בוקר", norm(person), team_name))

        if col_idx < len(night):
            person = str(night[col_idx]).strip() if night[col_idx] else ""
            if person and person.lower() not in ('none', '0', '') and person != 'nan':
                shifts.append((date_str, "לילה", norm(person), team_name))

    return shifts

def get_color_id(name):
    return RAW_PERSON_COLORS.get(norm(name), DEFAULT_COLOR)

def create_event(date_str, shift_type, person, team_name):
    day, month, year = date_str.split('/')

    if shift_type == "בוקר":
        start_dt = f"{year}-{month}-{day}T06:00:00"
        end_dt = f"{year}-{month}-{day}T18:00:00"
        hours_str = "06:00-18:00"
    else:
        start_dt = f"{year}-{month}-{day}T18:00:00"
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        next_day = dt + timedelta(days=1)
        end_dt = f"{next_day.year:04d}-{next_day.month:02d}-{next_day.day:02d}T06:00:00"
        hours_str = "18:00-06:00"

    title = f"{person} - משמרת {shift_type} - {team_name}"
    desc = f"משמרת {shift_type} ({day}/{month}/{year})\nתפקיד: {team_name}\nשעות: {hours_str}"

    body = {
        "summary": title,
        "description": desc,
        "start": {"dateTime": start_dt, "timeZone": "Asia/Jerusalem"},
        "end": {"dateTime": end_dt, "timeZone": "Asia/Jerusalem"},
        "colorId": get_color_id(person),
        "reminders": {"useDefault": True},
    }

    json_str = json.dumps(body, ensure_ascii=False)
    params = json.dumps({"calendarId": CALENDAR_ID, "sendUpdates": "none"})

    r = subprocess.run([
        'gws', 'calendar', 'events', 'insert',
        '--params', params,
        '--json', json_str,
        '--format', 'json'
    ], capture_output=True, text=True, timeout=30)

    if r.returncode != 0:
        print(f"  ERROR creating event for {person} on {date_str}: {r.stderr[:200]}")
        return False

    raw = r.stdout
    s, e = raw.find('{'), raw.rfind('}')
    if s >= 0 and e >= 0:
        result = json.loads(raw[s:e+1])
        event_id = result.get('id', 'unknown')
        print(f"  Created: {title} (ID: {event_id})")
        return True

    print(f"  Created (no JSON): {title}")
    return True

def main():
    print(f"=== Miluim Calendar Sync v2 ===")
    print(f"Sheet: {SHEET_ID}, Tab: {PROD_TAB}")
    print(f"Calendar: {CALENDAR_ID}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    print("Reading prod tab...")
    result = run_gws([
        'sheets', '+read',
        '--spreadsheet', SHEET_ID,
        '--range', f"{PROD_TAB}!A1:Z15",
        '--format', 'json'
    ])

    if not result or 'values' not in result:
        print("ERROR: Could not read prod tab")
        return

    rows = result['values']
    print(f"Read {len(rows)} rows")

    # v1 layout:
    # idx 2: team 1 date headers
    # idx 3: team 1 morning
    # idx 4: team 1 night
    # idx 7: team 2 date headers
    # idx 8: team 2 morning
    # idx 9: team 2 night

    all_shifts = []
    t1 = extract_dates_and_shifts(rows, 2, 3, 4, "הערכה")
    all_shifts.extend(t1)
    print(f"Team הערכה: {len(t1)} shifts")

    t2 = extract_dates_and_shifts(rows, 7, 8, 9, "עיבוד")
    all_shifts.extend(t2)
    print(f"Team עיבוד: {len(t2)} shifts")

    print(f"\nTotal parsed shifts: {len(all_shifts)}")

    if not all_shifts:
        print("No shifts to sync!")
        return
    print()

    def fetch_all_events(calendar_id, time_min, time_max):
        params = {"calendarId": calendar_id, "timeMin": time_min, "timeMax": time_max, "singleEvents": True}
        all_items = []
        page_token = None
        while True:
            p = {**params, "pageToken": page_token} if page_token else params
            result = run_gws(['calendar', 'events', 'list', '--params', json.dumps(p), '--format', 'json'])
            if result and 'items' in result:
                all_items.extend(result['items'])
            page_token = result.get('nextPageToken') if result else None
            if not page_token:
                break
        return all_items

    print("Reading existing calendar events...")
    dates = sorted(set(s[0] for s in all_shifts))
    first_date = datetime.strptime(dates[0], "%d/%m/%Y")
    last_date = datetime.strptime(dates[-1], "%d/%m/%Y")
    last_date_end = last_date + timedelta(days=2)

    time_min = first_date.strftime("%Y-%m-%dT00:00:00Z")
    time_max = last_date_end.strftime("%Y-%m-%dT23:59:59Z")

    all_events = fetch_all_events(CALENDAR_ID, time_min, time_max)

    # lookup: "date|shift_type|team" -> (person, event_id)
    existing_lookup = {}
    if all_events:
        for ev in all_events:
            summary = ev.get('summary', '')
            m = re.match(r'(.+) - משמרת (בוקר|לילה) - (.+)', summary)
            if m:
                person = norm(m.group(1))
                shift_type = m.group(2)
                team = norm(m.group(3))
                start_str = ev.get('start', {}).get('dateTime', '')
                if start_str:
                    dt = datetime.fromisoformat(start_str)
                    date_key = dt.strftime("%d/%m/%Y")
                    key = f"{date_key}|{shift_type}|{team}"
                    existing_lookup[key] = (person, ev['id'])

        print(f"Found {len(all_events)} events, {len(existing_lookup)} matched")
    else:
        print("No existing events found")

    print()

    def delete_event(event_id):
        params = json.dumps({"calendarId": CALENDAR_ID, "eventId": event_id})
        r = subprocess.run([
            'gws', 'calendar', 'events', 'delete',
            '--params', params,
        ], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"  ERROR deleting event {event_id}: {r.stderr[:200]}")
            return False
        return True

    created = 0
    skipped = 0
    updated = 0
    errors = 0

    for date_str, shift_type, person, team_name in all_shifts:
        key = f"{date_str}|{shift_type}|{team_name}"
        if key in existing_lookup:
            existing_person, existing_id = existing_lookup[key]
            if existing_person == person:
                skipped += 1
            else:
                print(f"  Person changed for {date_str} {shift_type} {team_name}: {existing_person} -> {person}")
                if delete_event(existing_id):
                    if create_event(date_str, shift_type, person, team_name):
                        updated += 1
                    else:
                        errors += 1
                else:
                    errors += 1
        else:
            if create_event(date_str, shift_type, person, team_name):
                created += 1
            else:
                errors += 1

    print(f"\n=== Summary ===")
    print(f"Total shifts in sheet: {len(all_shifts)}")
    print(f"Already in calendar: {skipped}")
    print(f"Created: {created}")
    print(f"Updated (person changed): {updated}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
