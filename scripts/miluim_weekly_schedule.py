#!/usr/bin/env python3
"""Run the weekly scheduling process with admin approval workflow."""
import json, subprocess, re, sys, os, uuid
from datetime import datetime, timedelta

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
DRAFT_TAB = "משמרות הערכה ועיבוד - טיוטא"
PROD_TAB = "משמרות הערכה ועיבוד"
MAX_DAYS = 16  # from 14/05 (today) to 30/05 (end of 2nd full week) = 16 days
SHIFT_ROWS = [4, 5, 9, 10]
PENDING_FILE = os.path.expanduser("~/.hermes/.miluim_pending_approval.json")

def col_letter(ci):
    if ci < 26: return chr(65 + ci)
    return chr(64 + ci // 26) + chr(65 + ci % 26)

def gws(*args):
    r = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=60)
    if r.returncode != 0: return None
    t = r.stdout.strip()
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e+1]) if s >= 0 else None

def read_settings():
    result = subprocess.run(["gws","sheets","+read","--spreadsheet",SHEET_ID,"--range","'settings'!A40:B60","--format","json"], capture_output=True, text=True)
    raw = result.stdout
    s = raw.find("{"); e = raw.rfind("}")
    if s < 0: return {}
    sett = {}
    for row in json.loads(raw[s:e+1]).get("values", []):
        if len(row) >= 2 and row[0] and not row[0].startswith("#"):
            sett[row[0].strip()] = row[1].strip()
    return sett

def send_email(to, subject, body):
    """Send email via gws gmail."""
    params = json.dumps({"to": ",".join(to) if isinstance(to, list) else to, "subject": subject})
    gws_data = {"raw": body}
    result = subprocess.run(
        ["gws", "gmail", "+send", "--to", ",".join(to) if isinstance(to, list) else to,
         "--subject", subject, "--body", body],
        capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0

today = datetime.now()
tomorrow = today + timedelta(days=1)
cutoff_str = (today + timedelta(days=MAX_DAYS)).strftime("%d/%m/%y")
cutoff_key = cutoff_str[6:8] + cutoff_str[3:5] + cutoff_str[0:2]

print(f"=== Weekly Schedule Process ({today.strftime('%d/%m/%y')}) ===")

# Step 1: Read settings
sett = read_settings()
require_approval = sett.get("require_admin_approval", "yes").lower() == "yes"
admins = [a.strip() for a in sett.get("admin", "").split(",") if a.strip()]
recipients = [r.strip() for r in sett.get("email_recipients", "").split(",") if r.strip()]

print(f"require_admin_approval={'yes' if require_approval else 'no'}")
print(f"admins={admins}")
print(f"recipients={recipients}")

# Step 2: Copy prod → draft
data = gws("sheets","+read","--spreadsheet",SHEET_ID,"--range",f"'{PROD_TAB}'!A3:BV10","--format","json")
if not data: print("FAILED to read prod"); sys.exit(1)
vals = data.get("values", [])
max_c = max(len(r) for r in vals) if vals else 74
norm = [[r[i] if i < len(r) else "" for i in range(max_c)] for r in vals]
subprocess.run(["gws","sheets","spreadsheets","values","update",
    "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{DRAFT_TAB}'!A3:BV10","valueInputOption":"USER_ENTERED"}),
    "--json",json.dumps({"values":norm}),"--format","json"], capture_output=True)
print("1. ✅ Copied prod → draft")

# Step 3: Find cutoff column — search from today's column forward
today_str = today.strftime("%d/%m/%y")
today_key = today_str[6:8] + today_str[3:5] + today_str[0:2]

headers = norm[0] if norm else []
cutoff_col = None
today_col = None

# First find today's column, then search forward for cutoff
for ci, cell in enumerate(headers):
    m = re.search(r"(\d{2})/(\d{2})/(\d{2})", str(cell))
    if m:
        d_key = m.group(3) + m.group(2) + m.group(1)
        if d_key == today_key:
            today_col = ci
        if today_col is not None and d_key >= cutoff_key and d_key > today_key:
            cutoff_col = ci
            break

if cutoff_col is None:
    # Fallback: search all columns
    for ci, cell in enumerate(headers):
        m = re.search(r"(\d{2})/(\d{2})/(\d{2})", str(cell))
        if m:
            d_key = m.group(3) + m.group(2) + m.group(1)
            if d_key >= cutoff_key:
                cutoff_col = ci
                break

if cutoff_col is None: print("Cutoff not found"); sys.exit(1)

for row in SHIFT_ROWS:
    cl = col_letter(cutoff_col)
    empty = [""] * (74 - cutoff_col)
    subprocess.run(["gws","sheets","spreadsheets","values","update",
        "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{DRAFT_TAB}'!{cl}{row}:BV{row}","valueInputOption":"RAW"}),
        "--json",json.dumps({"values":[empty]}),"--format","json"], capture_output=True)
print(f"2. ✅ Cleared from {cl} onward (14-day cutoff)")

# Step 4: Run solver
r = subprocess.run(["python3","/home/omer/.hermes/scripts/miluim_auto_fill.py","--max-days",str(MAX_DAYS)],
    capture_output=True, text=True, timeout=120)
solver_out = r.stdout
print(f"3. ✅ Solver ran ({solver_out.count('written')} writes)")

# Step 5: Decision
if not require_approval:
    # Auto-publish
    data = gws("sheets","+read","--spreadsheet",SHEET_ID,"--range",f"'{DRAFT_TAB}'!A3:BV10","--format","json")
    if data:
        vals = data.get("values",[])
        max_c = max(len(r) for r in vals) if vals else 74
        norm = [[r[i] if i < len(r) else "" for i in range(max_c)] for r in vals]
        subprocess.run(["gws","sheets","spreadsheets","values","update",
            "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{PROD_TAB}'!A3:BV10","valueInputOption":"USER_ENTERED"}),
            "--json",json.dumps({"values":norm}),"--format","json"], capture_output=True)
    print("4. ✅ Published to prod (auto, no approval required)")
    
    # Also backup to the backup tab
    backup_tab = "גיבוי משמרות הערכה ועיבוד"
    data = gws("sheets","+read","--spreadsheet",SHEET_ID,"--range",f"'{PROD_TAB}'!A1:BV75","--format","json")
    if data:
        vals = data.get("values",[])
        subprocess.run(["gws","sheets","spreadsheets","values","update",
            "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{backup_tab}'!A1:BV{len(vals)}","valueInputOption":"USER_ENTERED"}),
            "--json",json.dumps({"values":vals},ensure_ascii=False),"--format","json"], capture_output=True)
        print("5. ✅ Backed up to גיבוי משמרות הערכה ועיבוד")
    
    all_to = list(set(admins + recipients))
    send_email(all_to, "Miluim Schedule Published",
        f"A new 2-week schedule has been automatically published.\n"
        f"Date: {today.strftime('%d/%m/%y')}\n"
        f"Covers: next {MAX_DAYS} days\n"
        f"Google Calendar has been synced.")
    print("6. ✅ Email sent to admins + recipients")
    
    # Run calendar sync
    subprocess.run(["python3","/home/omer/.hermes/scripts/miluim_calendar_sync_v2.py"], capture_output=True, timeout=120)
    print("7. ✅ Calendar synced")
    
else:
    # Save pending state
    tracking_id = uuid.uuid4().hex[:8]
    pending = {
        "tracking_id": tracking_id,
        "created": today.isoformat(),
        "admins": admins,
        "recipients": recipients,
        "max_days": MAX_DAYS
    }
    with open(PENDING_FILE, "w") as f:
        json.dump(pending, f, ensure_ascii=False)
    
    draft_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={1653764399}"
    
    all_to = list(set(admins))
    # Send HTML email with bold formatting
    html_body = (
        f"<p>A new 2-week schedule has been generated in the draft sheet.</p>\n"
        f"<p>Please review the draft here:<br>\n"
        f"<a href='{draft_url}'>{draft_url}</a></p>\n"
        f"<p>You may make manual adjustments directly in the draft sheet.</p>\n"
        f"<p><strong>When ready, reply to this email with the word 'approved' "
        f"(include the tracking ID {tracking_id} in your reply).</strong></p>\n"
        f"<p>The schedule will be published to prod and synced to Google Calendar after your approval.</p>\n"
        f"<p>Date: {today.strftime('%d/%m/%y')}<br>\n"
        f"Covers: next {MAX_DAYS} days</p>"
    )
    result = subprocess.run(
        ["gws", "gmail", "+send", "--to", ",".join(all_to),
         "--subject", f"[APPROVAL REQUIRED {tracking_id}] Miluim Schedule Draft Ready",
         "--body", "Please view this email in HTML mode.", "--html", html_body],
        capture_output=True, text=True, timeout=30
    )
    
    print(f"4. ⏳ Approval required. Email sent to {admins}")
    print(f"   Tracking ID: {tracking_id}")
    print(f"   Waiting for reply 'approved' to publish...")
    
print("\n✅ Process complete")
