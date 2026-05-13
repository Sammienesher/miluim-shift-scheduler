#!/usr/bin/env python3
"""Gray out past-date cells in the miluim shift sheet."""
import json, subprocess, re
from datetime import datetime

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
TABS = {
    "Prod": ("משמרות הערכה ועיבוד", 1166224611),
    "Draft": ("משמרות הערכה ועיבוד - טיוטא", 1653764399),
}
ROWS = [4, 5, 9, 10] + list(range(16, 29))
GRAY = {"red": 0.75, "green": 0.75, "blue": 0.75}
TODAY = datetime.now().strftime("%d/%m/%y")

def gws(*args):
    r = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=30)
    if r.returncode != 0: return None
    t = r.stdout.strip()
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e+1]) if s >= 0 else None

# Read headers from prod tab to find past date columns
data = gws("sheets", "+read", "--spreadsheet", SHEET_ID,
           "--range", "'משמרות הערכה ועיבוד'!A3:BV3", "--format", "json")
if not data:
    print("FAILED to read headers")
    exit(1)

headers = data.get("values", [[]])[0]
past_cols = []
for ci, cell in enumerate(headers):
    m = re.search(r"(\d{2})/(\d{2})/(\d{2})", str(cell))
    if m:
        d = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        # Compare YYMMDD
        d_key = d[6:8] + d[3:5] + d[0:2]
        today_key = TODAY[6:8] + TODAY[3:5] + TODAY[0:2]
        if d_key < today_key:
            past_cols.append(ci)

# Also include the summary columns adjacent to past date columns
# (the empty summary col after each week)
empty_summaries = [c + 1 for c in past_cols if c + 1 in range(len(headers)) and not headers[c + 1]]
past_cols = sorted(set(past_cols + empty_summaries))

if not past_cols:
    print("No past date columns found")
    exit(0)

total = 0
for tab_name, (tab_title, tab_id) in TABS.items():
    requests = []
    for row in ROWS:
        for col in past_cols:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": tab_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1
                    },
                    "cell": {
                        "userEnteredFormat": {"backgroundColor": GRAY}
                    },
                    "fields": "userEnteredFormat.backgroundColor"
                }
            })
    
    for i in range(0, len(requests), 100):
        batch = requests[i:i+100]
        payload = json.dumps({"requests": batch})
        result = subprocess.run(
            ["gws", "sheets", "spreadsheets", "batchUpdate",
             "--params", json.dumps({"spreadsheetId": SHEET_ID}),
             "--json", payload, "--format", "json"],
            capture_output=True, text=True
        )
        raw = result.stdout
        s, e = raw.find("{"), raw.rfind("}")
        if s >= 0:
            replies = json.loads(raw[s:e+1]).get("replies", [])
            total += len(replies)

print(f"Grayed {total} past-date cells across {len(TABS)} tabs")
