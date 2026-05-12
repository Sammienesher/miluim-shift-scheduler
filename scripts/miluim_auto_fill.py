#!/usr/bin/env python3
"""
Auto-fill all missing shift assignments in the draft sheet.
Reads constraints, generates fair schedules, writes results.
"""
import subprocess, json, re, sys, math
from datetime import datetime
from collections import defaultdict, Counter

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
TAB = "משמרות הערכה ועיבוד - טיוטא"

def gws(*args):
    r = subprocess.run(["gws"]+list(args), capture_output=True, text=True, timeout=60)
    if r.returncode != 0: return None
    t = r.stdout.strip(); s = t.find("{"); e = t.rfind("}")
    return json.loads(t[s:e+1]) if s>=0 else None

def norm(s):
    s = s.strip().replace("\u2019","'").replace("\u2018","'")
    return re.sub(r'\s+',' ',s)

def extract_date(cell):
    m = re.search(r'(\d{2})/(\d{2})/(\d{2})', str(cell))
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else None

# Read full sheet
data = gws("sheets","+read","--spreadsheet",SHEET_ID,"--range",f"'{TAB}'!A1:BV75","--format","json")
if not data: print("FAILED to read sheet"); sys.exit(1)
vals = data.get("values",[])

# === PARSE COLUMN STRUCTURE ===
# Use analysis header (row 8 = vals[7]) to map columns to dates
anal_header = vals[7] if len(vals)>7 else []
eval_header = vals[2] if len(vals)>2 else []

col_to_date = {}  # col_idx -> "DD/MM/YY"
for ci, cell in enumerate(anal_header):
    d = extract_date(cell)
    if d: col_to_date[ci] = d

# Group columns into weeks
# Structure: partial week (Wed-Sat, 4 cols), then full weeks (Sun-Sat, 7 cols each)
date_cols = sorted(col_to_date.keys())

# Filter out past dates — only schedule from today forward
TODAY = datetime.now().strftime("%d/%m/%y")
def is_past(col):
    d = col_to_date.get(col, "")
    if not d: return True
    # Compare DD/MM/YY strings lexicographically works if MM and DD are zero-padded
    return d < TODAY

past_count = sum(1 for c in date_cols if is_past(c))
date_cols = [c for c in date_cols if not is_past(c)]
print(f"Skipped {past_count} past columns, {len(date_cols)} future columns remain")

# Helper to get day of week for a date
def get_dow_for_date(date_str):
    parts = date_str.split("/")
    dt = datetime(2000+int(parts[2]), int(parts[1]), int(parts[0]))
    return dt.weekday()  # Mon=0, Sun=6

# Find first Sunday (start of first full week)
weeks = []
i = 0
while i < len(date_cols):
    col = date_cols[i]
    date_str = col_to_date[col]
    dow = get_dow_for_date(date_str)
    
    if dow == 6:  # Sunday found (Python weekday 6)
        week = date_cols[i:i+7]
        if len(week) < 7: break
        weeks.append({
            "days": week,
            "start_date": col_to_date[week[0]],
            "end_date": col_to_date[week[-1]]
        })
        i += 7
    else:
        i += 1  # skip partial week and gaps

print(f"Found {len(weeks)} full week blocks from {weeks[0]['start_date']} to {weeks[-1]['end_date']}")

print(f"Found {len(weeks)} week blocks from {weeks[0]['start_date']} to {weeks[-1]['end_date'] if weeks else 'N/A'}")

# === PARSE CONSTRAINTS ===
# Evaluation: rows 16-19 (vals[15]-vals[18])
# Analysis: rows 21-26 (vals[20]-vals[25])

def parse_constraints(start_idx, end_idx, name="section"):
    """Parse person constraints from sheet rows. Returns {name: {col: constraint}}"""
    people = {}
    for idx in range(start_idx, min(end_idx+1, len(vals))):
        row = vals[idx]
        if not row or not row[0]: continue
        nm = norm(row[0])
        if not nm or nm in ("הערכה","עיבוד","","אילוצים"): continue
        cons = {}
        for ci in date_cols:
            if ci < len(row):
                v = norm(row[ci])
                if v: cons[ci] = v
        people[nm] = cons
    return people

eval_people = parse_constraints(15, 18, "evaluation")  # vals[15]-vals[18]
anal_people = parse_constraints(20, 25, "analysis")     # vals[20]-vals[25]

print(f"\nEvaluation team: {list(eval_people.keys())}")
print(f"Analysis team: {list(anal_people.keys())}")

# === READ EXISTING SHIFT DATA ===
# Eval: morning=vals[3], night=vals[4]
# Anal: morning=vals[8], night=vals[9]

existing_morning = vals[3] if len(vals)>3 else []  # eval morning
existing_night = vals[4] if len(vals)>4 else []     # eval night
existing_anal_m = vals[8] if len(vals)>8 else []
existing_anal_n = vals[9] if len(vals)>9 else []

def get_existing(row_data, col):
    """Get existing assignment at a column, or None if empty"""
    if col < len(row_data):
        v = norm(row_data[col])
        return v if v else None
    return None

# === CONSTRAINT SOLVER ===
def check_constraint(person, col, shift_type, constraints):
    """Check if a person can work a shift on a given day.
    shift_type: 'morning' or 'night'"""
    c = constraints.get(person, {})
    val = c.get(col, "לא יכול")
    if val == "לא יכול": return False
    if val == "יכול": return True
    if val == "יכול רק בוקר": return shift_type == "morning"
    if val == "יכול רק לילה": return shift_type == "night"
    if val == "לא ידוע": return True  # treat unknown as available
    return True

def get_day(col):
    """Get day of week from a date column"""
    d = col_to_date.get(col)
    if not d: return None
    parts = d.split("/")
    dt = datetime(2000+int(parts[2]), int(parts[1]), int(parts[0]))
    return dt.weekday()  # Mon=0, Sun=6

def is_weekend(col):
    """Check if column corresponds to Friday(4) or Saturday(5)"""
    day = get_day(col)
    return day in (4, 5)  # Fri=4, Sat=5

def solve_week(week, people_data, running_counts, team_name="eval"):
    """Solve a single week's assignments. Returns (mornings, nights) dicts."""
    days = week["days"]
    mornings = {}
    nights = {}
    
    # Build availability matrix
    avail_m = {}  # {col: [list of available people]}
    avail_n = {}
    
    for col in days:
        avail_m[col] = [p for p in people_data if check_constraint(p, col, "morning", people_data)]
        avail_n[col] = [p for p in people_data if check_constraint(p, col, "night", people_data)]
    
    # For evaluation team, strip existing counts for fairness calculation
    # Running counts are from previous weeks
    
    # Strategy: sort days, try hardest days first (fewest options)
    # Then use greedy assignment
    
    # Night assignment first (since it affects next morning)
    # Sort nights by availability (fewest options first)
    night_order = sorted(days, key=lambda c: len(avail_n[c]))
    
    for col in night_order:
        candidates = [p for p in avail_n[col] 
                      if p not in nights.values()]  # can't do double same night
        if not candidates:
            candidates = avail_n[col]
        
        # Prefer people with lower running counts, but also consider:
        # If someone did this morning, they CAN do this night (Rule 2 is night→next MORNING)
        # If someone is doing night, they can't do next morning
        
        # Score candidates
        def score(p):
            base = running_counts.get(p, 0)
            # Penalize slightly if already assigned this night
            night_penalty = 5 if p in nights.values() else 0
            # Bonus for night-only people on night shifts
            is_night_only = all(check_constraint(p, c, "morning", people_data) == False 
                              for c in days)
            night_bonus = -3 if is_night_only else 0
            return base + night_penalty + night_bonus
        
        candidates.sort(key=score)
        best = candidates[0]
        nights[col] = best
        running_counts[best] = running_counts.get(best, 0) + 1
    
    # Morning assignment
    # Can't assign someone who did PREVIOUS night
    morning_order = sorted(days, key=lambda c: len(avail_m[c]))
    
    for col in morning_order:
        # Check Rule 2: can't assign if person did previous night
        prev_day_idx = days.index(col) - 1 if col in days else -1
        prev_night_person = None
        if prev_day_idx >= 0:
            prev_col = days[prev_day_idx]
            prev_night_person = nights.get(prev_col)
        
        candidates = [p for p in avail_m[col] 
                      if p != prev_night_person  # Rule 2
                      and p not in mornings.values()  # can't double same morning
                      and p != nights.get(col)]  # BUG FIX: can't double same-day night
        
        if not candidates:
            candidates = [p for p in avail_m[col] if p != prev_night_person and p != nights.get(col)]
        if not candidates:
            candidates = avail_m[col]
        
        def score_m(p):
            base = running_counts.get(p, 0)
            dup = 5 if p in mornings.values() else 0
            # Weekend rule: prefer people who haven't done weekend shifts
            weekend_penalty = 0
            if is_weekend(col):
                # If they already have a Fri or Sat shift
                for c in days:
                    if is_weekend(c) and (mornings.get(c) == p or nights.get(c) == p):
                        weekend_penalty += 3
            return base + dup + weekend_penalty
        
        candidates.sort(key=score_m)
        best = candidates[0]
        mornings[col] = best
        running_counts[best] = running_counts.get(best, 0) + 1
    
    return mornings, nights

# === SOLVE ALL WEEKS ===
def fill_section(people_data, existing_m_row, existing_n_row, row_morning, row_night, team_name):
    """Fill all weeks for a section (evaluation or analysis)."""
    running = defaultdict(int)
    
    # Count existing shifts from already-filled weeks
    all_updates = {}  # {(row, col): value}
    
    for w_idx, week in enumerate(weeks):
        existing_m = {}
        existing_n = {}
        has_existing = False
        
        for col in week["days"]:
            em = get_existing(existing_m_row, col)
            en = get_existing(existing_n_row, col)
            if em or en:
                has_existing = True
            if em: existing_m[col] = em
            if en: existing_n[col] = en
        
        # Check if week is FULLY filled (every day has both shifts)
        all_filled = all(
            col in existing_m and col in existing_n 
            for col in week["days"]
        )
        
        if all_filled:
            # Week fully filled - just count existing
            for p in existing_m.values():
                running[p] += 1
            for p in existing_n.values():
                running[p] += 1
            print(f"  {team_name} week {w_idx+1} ({week['start_date']}-{week['end_date']}): already filled, skipped")
        elif has_existing:
            # BUG FIX: Partially filled week - preserve existing, fill gaps
            for p in existing_m.values():
                running[p] += 1
            for p in existing_n.values():
                running[p] += 1
            m, n = solve_week(week, people_data, running, team_name)
            
            for col in week["days"]:
                if col not in existing_m and col in m:
                    all_updates[(row_morning, col)] = m[col]
                if col not in existing_n and col in n:
                    all_updates[(row_night, col)] = n[col]
            
            existing_count = len(existing_m) + len(existing_n)
            filled_now = len([c for c in week["days"] if c not in existing_m and c in m]) + \
                         len([c for c in week["days"] if c not in existing_n and c in n])
            print(f"  {team_name} week {w_idx+1} ({week['start_date']}-{week['end_date']}): {existing_count} existing + {filled_now} new = {len(week['days'])*2} total")
        else:
            # Solve this week
            m, n = solve_week(week, people_data, running, team_name)
            
            for col in week["days"]:
                if col not in existing_m and col in m:
                    all_updates[(row_morning, col)] = m[col]
                if col not in existing_n and col in n:
                    all_updates[(row_night, col)] = n[col]
            
            print(f"  {team_name} week {w_idx+1} ({week['start_date']}-{week['end_date']}): assigned")
    
    return all_updates

eval_updates = fill_section(eval_people, existing_morning, existing_night, 4, 5, "eval")
print(f"\nEvaluation: {len(eval_updates)} cells to update")
anal_updates = fill_section(anal_people, existing_anal_m, existing_anal_n, 9, 10, "anal")
print(f"Analysis: {len(anal_updates)} cells to update")

# === QA VERIFICATION ===
def verify_schedule(updates, people_data, existing_m_row, existing_n_row, team_name, row_m, row_n):
    """Check for violations in the solved schedule."""
    issues = []
    
    # Build full picture: existing + new updates
    m_by_col = {}
    n_by_col = {}
    for col in date_cols:
        em = get_existing(existing_m_row, col)
        if em: m_by_col[col] = em
        en = get_existing(existing_n_row, col)
        if en: n_by_col[col] = en
    
    for (row, col), val in updates.items():
        if row == row_m:
            m_by_col[col] = val
        elif row == row_n:
            n_by_col[col] = val
    
    for col in date_cols:
        if col in m_by_col and col in n_by_col:
            # Bug 1 check: same-day double booking
            m_person = m_by_col[col]
            n_person = n_by_col[col]
            if norm(m_person) == norm(n_person):
                date_str = col_to_date.get(col, f"col {col}")
                issues.append(f"  ⚠ {date_str}: {m_person} assigned BOTH morning AND night")
        
        # Rule 2 check: night[d-1] -> morning[d]
        prev_idx = date_cols.index(col) - 1 if col in date_cols else -1
        if prev_idx >= 0:
            prev_col = date_cols[prev_idx]
            if prev_col in n_by_col and col in m_by_col:
                prev_n = n_by_col[prev_col]
                curr_m = m_by_col[col]
                if norm(prev_n) == norm(curr_m):
                    date_str = col_to_date.get(col, f"col {col}")
                    issues.append(f"  ⚠ {date_str}: {prev_n} on night[{prev_col}] -> morning[{col}] (Rule 2)")
    
    if not issues:
        print(f"  ✅ {team_name} QA: clean ({len(updates)} cells)")
    else:
        print(f"  ❌ {team_name} QA: {len(issues)} issue(s):")
        for issue in issues:
            print(issue)
    return issues

eval_issues = verify_schedule(eval_updates, eval_people, existing_morning, existing_night, "Evaluation", 4, 5)
anal_issues = verify_schedule(anal_updates, anal_people, existing_anal_m, existing_anal_n, "Analysis", 9, 10)

total_issues = len(eval_issues) + len(anal_issues)
if total_issues > 0:
    print(f"\n⚠️  TOTAL QA ISSUES: {total_issues}")
else:
    print(f"\n✅ QA: ALL CLEAR (0 issues)")

# === WRITE TO SHEET ===
# Group updates by row for batch writing
def write_updates(updates, section_name):
    if not updates:
        print(f"{section_name}: No updates needed")
        return
    
    # Group by row
    by_row = defaultdict(dict)
    for (row, col), val in updates.items():
        by_row[row][col] = val
    
    for row, cols in sorted(by_row.items()):
        sorted_cols = sorted(cols.keys())
        print(f"  Row {row}: writing {len(sorted_cols)} cells at cols {sorted_cols[0]}-{sorted_cols[-1]}")
        # Find contiguous ranges
        ranges = []
        start = sorted_cols[0]
        end = start
        for c in sorted_cols[1:]:
            if c == end + 1:
                end = c
            else:
                ranges.append((start, end))
                start = c
                end = c
        ranges.append((start, end))
        
        for start_col, end_col in ranges:
            # Build A1 range
            def col_letter(ci):
                if ci < 26: return chr(65 + ci)
                a = ci // 26 - 1
                b = ci % 26
                return chr(65 + a) + chr(65 + b)
            
            rng = f"{col_letter(start_col)}{row}:{col_letter(end_col)}{row}"
            values = [[cols[c] for c in range(start_col, end_col+1) if c in cols]]
            
            full_range = f"'{TAB}'!{rng}"
            result = gws("sheets","spreadsheets","values","update",
                "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": full_range, "valueInputOption": "USER_ENTERED"}),
                "--json", json.dumps({"values": values}),
                "--format","json")
            if result:
                print(f"  ✓ {rng} ({len(values[0])} cells)")
            else:
                # Try without the tab quotes
                result2 = subprocess.run(
                    ["gws","sheets","spreadsheets.values","update",
                     "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{TAB}'!{rng}", "valueInputOption": "USER_ENTERED"}),
                     "--json", json.dumps({"values": values}),
                     "--format","json"],
                    capture_output=True, text=True, timeout=30
                )
                stderr = result2.stderr[:200]
                print(f"  ✗ {rng} | {stderr}")

write_updates(eval_updates, "Evaluation")
write_updates(anal_updates, "Analysis")

print("\nDone!")
