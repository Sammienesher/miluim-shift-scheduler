#!/usr/bin/env python3
"""Thursday publish: clear shifts beyond 14 days, re-solve 2 weeks, copy to prod."""
import subprocess, json, re, sys
from datetime import datetime, timedelta

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
DRAFT_TAB = "משמרות הערכה ועיבוד - טיוטא"
PROD_TAB = "משמרות הערכה ועיבוד"
MAX_DAYS = 14
SHIFT_ROWS = [4, 5, 9, 10]

def col_letter(ci):
    if ci < 26: return chr(65 + ci)
    return chr(64 + ci // 26) + chr(65 + ci % 26)

def gws(*args):
    r = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=60)
    if r.returncode != 0: return None
    t = r.stdout.strip()
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e+1]) if s >= 0 else None

# 1. Find cutoff column
today = datetime.now()
cutoff_str = (today + timedelta(days=MAX_DAYS)).strftime("%d/%m/%y")
cutoff_key = cutoff_str[6:8] + cutoff_str[3:5] + cutoff_str[0:2]

data = gws("sheets", "+read", "--spreadsheet", SHEET_ID,
           "--range", f"'{DRAFT_TAB}'!A3:BV3", "--format", "json")
if not data: print("FAILED"); sys.exit(1)

headers = data.get("values", [[]])[0]
cutoff_col = None
for ci, cell in enumerate(headers):
    m = re.search(r"(\d{2})/(\d{2})/(\d{2})", str(cell))
    if m:
        d_key = m.group(3) + m.group(2) + m.group(1)
        if d_key >= cutoff_key:
            cutoff_col = ci
            break

if cutoff_col is None: print("Cutoff not found"); sys.exit(1)
print(f"Cutoff {cutoff_str} at col {col_letter(cutoff_col)} (idx {cutoff_col})")

# 2. Clear beyond cutoff in draft
empty = [""] * (74 - cutoff_col)
for row in SHIFT_ROWS:
    cl = col_letter(cutoff_col)
    subprocess.run(["gws","sheets","spreadsheets","values","update",
        "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{DRAFT_TAB}'!{cl}{row}:BV{row}","valueInputOption":"USER_ENTERED"}),
        "--json",json.dumps({"values":[empty]}),"--format","json"],
        capture_output=True)
print("Cleared beyond cutoff")

# 3. Refresh 48h buffer from prod (preserve manual edits)
data = gws("sheets","+read","--spreadsheet",SHEET_ID,
           "--range",f"'{PROD_TAB}'!A3:BV10","--format","json")
if data:
    vals = data.get("values",[])
    max_c = max(len(r) for r in vals) if vals else 74
    norm = [[r[i] if i < len(r) else "" for i in range(max_c)] for r in vals]
    subprocess.run(["gws","sheets","spreadsheets","values","update",
        "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{DRAFT_TAB}'!A3:BV10","valueInputOption":"USER_ENTERED"}),
        "--json",json.dumps({"values":norm}),"--format","json"],
        capture_output=True)
print("Refreshed draft from prod (48h buffer preserved)")

# 4. Run solver with 14-day limit
r = subprocess.run(["python3","/home/omer/.hermes/scripts/miluim_auto_fill.py","--max-days","14"],
    capture_output=True, text=True, timeout=120)
print(r.stdout)
if r.returncode != 0: print(f"ERROR: {r.stderr[:300]}"); sys.exit(1)

# 5. Copy draft to prod
data = gws("sheets","+read","--spreadsheet",SHEET_ID,
           "--range",f"'{DRAFT_TAB}'!A3:BV10","--format","json")
if data:
    vals = data.get("values",[])
    max_c = max(len(r) for r in vals) if vals else 74
    norm = [[r[i] if i < len(r) else "" for i in range(max_c)] for r in vals]
    subprocess.run(["gws","sheets","spreadsheets","values","update",
        "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{PROD_TAB}'!A3:BV10","valueInputOption":"USER_ENTERED"}),
        "--json",json.dumps({"values":norm}),"--format","json"],
        capture_output=True)
print("Copied to prod")
print("\n✅ Thursday publish complete")
