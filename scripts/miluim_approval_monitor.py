#!/usr/bin/env python3
"""Monitor for admin approval replies and publish when approved."""
import json, subprocess, re, os, sys
from datetime import datetime

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
DRAFT_TAB = "משמרות הערכה ועיבוד - טיוטא"
PROD_TAB = "משמרות הערכה ועיבוד"
PENDING_FILE = os.path.expanduser("~/.hermes/.miluim_pending_approval.json")

def gws(*args):
    r = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=60)
    if r.returncode != 0: return None
    t = r.stdout.strip()
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e+1]) if s >= 0 else None

# Check if there's a pending approval
if not os.path.exists(PENDING_FILE):
    print("No pending approval")
    sys.exit(0)

with open(PENDING_FILE) as f:
    pending = json.load(f)

tracking_id = pending.get("tracking_id", "")
admins = pending.get("admins", [])
recipients = pending.get("recipients", [])
print(f"Checking approval for tracking ID: {tracking_id}")

# Search inbox for replies matching the tracking ID with "approved"
# Search for recent emails with the tracking ID in the subject
result = subprocess.run(
    ["gws", "gmail", "+list", "--params",
     json.dumps({"q": f"subject:{tracking_id} approved", "maxResults": 5}),
     "--format", "json"],
    capture_output=True, text=True, timeout=30
)
raw = result.stdout
s, e = raw.find("["), raw.rfind("]")
if s < 0:
    print("No matching emails found")
    sys.exit(0)

try:
    messages = json.loads(raw[s:e+1])
except:
    print("Could not parse email list")
    sys.exit(0)

if not messages:
    print("No approval found yet")
    sys.exit(0)

print(f"Found {len(messages)} matching email(s)")

# Read the most recent message to confirm it says "approved"
msg = messages[0]
msg_id = msg.get("id", "")
if not msg_id:
    print("No message ID")
    sys.exit(0)

result = subprocess.run(
    ["gws", "gmail", "+read", "--params",
     json.dumps({"id": msg_id, "format": "full"}),
     "--format", "json"],
    capture_output=True, text=True, timeout=30
)
raw = result.stdout
s_body = raw.find("Subject:") 
body_lower = raw.lower()

if "approved" not in body_lower:
    print("Reply found but doesn't contain 'approved'")
    sys.exit(0)

print("✅ Approval detected! Publishing to prod...")

# Copy draft → prod
data = gws("sheets","+read","--spreadsheet",SHEET_ID,"--range",f"'{DRAFT_TAB}'!A3:BV10","--format","json")
if data:
    vals = data.get("values",[])
    max_c = max(len(r) for r in vals) if vals else 74
    norm = [[r[i] if i < len(r) else "" for i in range(max_c)] for r in vals]
    subprocess.run(["gws","sheets","spreadsheets","values","update",
        "--params",json.dumps({"spreadsheetId":SHEET_ID,"range":f"'{PROD_TAB}'!A3:BV10","valueInputOption":"USER_ENTERED"}),
        "--json",json.dumps({"values":norm}),"--format","json"], capture_output=True)
print("✅ Published to prod")

# Sync calendar
subprocess.run(["python3","/home/omer/.hermes/scripts/miluim_calendar_sync_v2.py"], capture_output=True, timeout=120)
print("✅ Calendar synced")

# Notify everyone
all_to = list(set(admins + recipients))
subprocess.run(
    ["gws", "gmail", "+send", "--to", ",".join(all_to),
     "--subject", "Miluim Schedule Published (Approved)",
     "--body", f"The new 2-week schedule has been approved and published.\n"
               f"Approved: {datetime.now().strftime('%d/%m/%y %H:%M')}\n"
               f"Google Calendar has been synced.\n\n"
               f"View the schedule:\n"
               f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=1166224611"],
    capture_output=True, timeout=30)
print("✅ Notification emails sent")

# Clean up
os.remove(PENDING_FILE)
print("✅ Pending approval cleared")

print("\n✅ All done!")
