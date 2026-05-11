#!/usr/bin/env python3
"""Generate daily miluim attendance report in Hebrew."""

import subprocess
import json
import re
import sys
from datetime import datetime, timedelta

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
SHEET_RANGE = "משמרות הערכה ועיבוד"

def gws(*args):
    result = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=30)
    text = result.stdout.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0:
        return None
    try:
        return json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return None

def norm(s):
    s = s.strip()
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r'\s+', ' ', s)

def extract_date(date_cell):
    m = re.search(r'(\d{2})/(\d{2})/(\d{2})', date_cell)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return None

HB_DAYS = {0: "יום שני", 1: "יום שלישי", 2: "יום רביעי",
           3: "יום חמישי", 4: "יום שישי", 5: "שבת", 6: "יום ראשון"}

def build(target_date):
    date_key = target_date.strftime("%Y-%m-%d")
    date_heb = f"{HB_DAYS[target_date.weekday()]}, {target_date.strftime('%d/%m/%y')}"

    data = gws("sheets", "+read", "--spreadsheet", SHEET_ID, "--range", SHEET_RANGE, "--format", "json")
    if not data:
        return None

    values = data.get("values", [])
    
    # === SHIFTS ===
    # values[2] = eval header, [3] = eval morning, [4] = eval night
    # values[7] = anal header, [8] = anal morning, [9] = anal night
    
    def find_shift(header, row, date_key):
        for col_idx in range(1, min(len(header), len(row))):
            cell = header[col_idx]
            name = row[col_idx]
            if not name or not cell:
                continue
            d = extract_date(cell)
            if d:
                try:
                    dt = datetime.strptime(d, "%d/%m/%y")
                    if dt.strftime("%Y-%m-%d") == date_key:
                        return norm(name)
                except ValueError:
                    continue
        return "—"

    morning_intel = find_shift(values[2], values[3], date_key)
    night_intel   = find_shift(values[2], values[4], date_key)
    morning_anal  = find_shift(values[7], values[8], date_key)
    night_anal    = find_shift(values[7], values[9], date_key)

    # === CONSTRAINTS ===
    # values[12] = ["אילוצים", ...]
    # values[13] = ["יום", dates...] (constraint date header)
    # values[14] = ["הערכה"]  ← section header, skip
    # values[15-18] = eval people
    # values[19] = ["עיבוד", ...] ← section header, skip
    # values[20-27] = anal people
    
    constraint_header = values[13] if len(values) > 13 else []
    
    # Find target column in constraint header
    target_col = None
    for col_idx in range(1, len(constraint_header)):
        d = extract_date(constraint_header[col_idx])
        if d:
            try:
                dt = datetime.strptime(d, "%d/%m/%y")
                if dt.strftime("%Y-%m-%d") == date_key:
                    target_col = col_idx
                    break
            except ValueError:
                continue
    
    persons = []
    
    if target_col is not None:
        # Person rows: skip header row (13) and section header rows (14="הערכה", 19="עיבוד")
        for idx in range(15, min(28, len(values))):
            row = values[idx]
            if not row or not row[0]:
                continue
            name = norm(row[0])
            if name in ("", "הערכה", "עיבוד"):
                continue
            val = row[target_col] if target_col < len(row) else ""
            constraint = norm(val) if val else "לא ידוע"
            persons.append((name, constraint))
    
    # Order: intel people first, then anal people
    intel_order = ["עומר נשר", "נדב רבינוביץ'", "רוני טפר", "ינון סגרון"]
    anal_order  = ["עומר כהן", "ניתאי יפה", "אריה קלמן", "נדב הכץ", "אריה וינטר"]
    
    def sort_key(p):
        name = p[0]
        if name in intel_order:
            return (0, intel_order.index(name))
        if name in anal_order:
            return (1, anal_order.index(name))
        return (2, 0)
    
    persons.sort(key=sort_key)
    
    # === BUILD REPORT ===
    lines = []
    lines.append(f"📋 **דוח נוכחות יומי - {date_heb}**")
    lines.append("")
    lines.append(f"**☀️ משמרת בוקר (06:00-18:00)**")
    lines.append(f"הערכה: {morning_intel}")
    lines.append(f"עיבוד: {morning_anal}")
    lines.append("")
    lines.append(f"**🌙 משמרת לילה (18:00-06:00)**")
    lines.append(f"הערכה: {night_intel}")
    lines.append(f"עיבוד: {night_anal}")
    lines.append("")
    lines.append(f"**📌 אילוצים להיום:**")
    
    for name, constraint in persons:
        emoji = "✅" if constraint == "יכול" else \
                "❌" if constraint == "לא יכול" else \
                "☀️" if constraint == "יכול רק בוקר" else \
                "🌙" if constraint == "יכול רק לילה" else "❓"
        lines.append(f"{emoji} {name}: {constraint}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date to report (DD/MM/YY), default: today")
    parser.add_argument("--cron", action="store_true", help="Also send email (cron mode)")
    args = parser.parse_args()
    
    if args.date:
        target = datetime.strptime(args.date, "%d/%m/%y")
    else:
        target = datetime.now()
    
    # Self-destruct: if running as cron after July 12, stop
    if args.cron and datetime.now() >= datetime(2026, 7, 12):
        print("Past July 12 — no more reports needed.")
        subprocess.run(["hermes", "cron", "remove", "c252bb25216b"],
                       capture_output=True, timeout=10)
        sys.exit(0)
    
    report = build(target)
    if not report:
        print("❌ Failed to generate report", file=sys.stderr)
        sys.exit(1)
    
    # Always print to stdout (captured by cron delivery)
    print(report)
    
    # In cron mode, also email it
    if args.cron:
        date_fmt = target.strftime("%d/%m/%y")
        subprocess.run([
            "gws", "gmail", "+send",
            "--to", "omernesher@gmail.com, ndv2222@gmail.com",
            "--subject", f"דוח נוכחות מילואים - {date_fmt}",
            "--body", report
        ], capture_output=True, timeout=30)
        print(f"\n(Email sent to omernesher@gmail.com & ndv2222@gmail.com)")
