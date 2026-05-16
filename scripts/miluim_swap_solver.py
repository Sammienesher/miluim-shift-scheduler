#!/usr/bin/env python3
"""
Miluim Swap Solver — finds the best shift swap between two people.

Usage:
  python3 miluim_swap_solver.py <person_name> <date> <shift_type> <team>
  python3 miluim_swap_solver.py --sheet    # Read request from Swaps staging tab
  python3 miluim_swap_solver.py --apply    # Apply the top proposal from results

Example:
  python3 miluim_swap_solver.py 'עומר נשר' '15/05/2026' 'בוקר' 'הערכה'
"""
import json, re, subprocess, sys, os
from datetime import datetime, timedelta
from collections import defaultdict

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
PROD_TAB = "משמרות הערכה ועיבוד"
SWAPS_TAB = "Swaps"
APOSTROPHE_CHARS = "\u05f3\u2019\u2018\u02bc"
APO_TABLE = str.maketrans(APOSTROPHE_CHARS, "'" * len(APOSTROPHE_CHARS))

def norm(s):
    s = str(s).strip(); s = s.translate(APO_TABLE); s = re.sub(r"\s+", " ", s); return s

def run_gws(args, timeout=30):
    cmd = ["gws"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0: return None
    raw = r.stdout
    s, e = raw.find("{"), raw.rfind("}")
    return json.loads(raw[s:e+1]) if s >= 0 else None

def read_sheet_full():
    """Read all data including constraints."""
    r = subprocess.run(["gws", "sheets", "+read", "--spreadsheet", SHEET_ID,
        "--range", f"{PROD_TAB}!A1:BC30", "--format", "json"], capture_output=True, text=True, timeout=30)
    s, e = r.stdout.find("{"), r.stdout.rfind("}")
    return json.loads(r.stdout[s:e+1])["values"] if s >= 0 else []

def get_dates_from_headers(headers_row):
    """Extract dates from a header row. Returns list of (col_idx, date_str) for non-empty date cells."""
    dates = []
    for col in range(1, len(headers_row)):
        raw = str(headers_row[col]).strip() if headers_row[col] else ""
        if not raw: continue
        m = re.search(r"(\d{2})/(\d{2})/(\d{2})", raw)
        if m:
            dates.append((col, f"{m.group(1)}/{m.group(2)}/20{m.group(3)}"))
    return dates

def parse_constraints(rows):
    """
    Parse constraint rows.
    Returns: dict of person -> {date -> constraint}
    where constraint is: 'יכול', 'לא יכול', 'יכול רק בוקר', 'יכול רק לילה'
    """
    constraints = {}
    
    # Team headers are at row 2 (הערכה) and row 7 (עיבוד)
    team_configs = [
        (2, 15, 19, "הערכה"),   # schedule_header_row, con_start_row, con_end_row, team
        (7, 21, 28, "עיבוד"),
    ]
    
    for header_row_idx, con_start, con_end, team_name in team_configs:
        if header_row_idx >= len(rows):
            continue
        headers = rows[header_row_idx]
        date_map = get_dates_from_headers(headers)
        
        for row_idx in range(con_start, min(con_end + 1, len(rows))):
            row = rows[row_idx]
            if not row or not str(row[0]).strip():
                continue
            person = norm(str(row[0]))
            if person not in constraints:
                constraints[person] = {}
            for col, date_str in date_map:
                if col < len(row) and row[col] and str(row[col]).strip():
                    val = str(row[col]).strip()
                    # Keep only meaningful constraint values
                    if val not in ("", "0", "nan", "None"):
                        constraints[person][(date_str, team_name)] = val
    
    return constraints

def parse_schedule(rows):
    """Parse shifts from the sheet."""
    shifts = []
    all_people = set()
    
    for team_name, row_h, row_m, row_n in [("הערכה", 2, 3, 4), ("עיבוד", 7, 8, 9)]:
        headers = rows[row_h] if row_h < len(rows) else []
        morning = rows[row_m] if row_m < len(rows) else []
        night = rows[row_n] if row_n < len(rows) else []
        
        for col in range(1, min(len(headers), len(morning), len(night))):
            date_raw = str(headers[col]).strip() if headers[col] else ""
            if not date_raw: continue
            m = re.search(r"(\d{2})/(\d{2})/(\d{2})", date_raw)
            if not m: continue
            day, month, yr = m.group(1), m.group(2), m.group(3)
            date_str = f"{day}/{month}/20{yr}"
            
            if col < len(morning) and morning[col] and str(morning[col]).strip():
                p = norm(str(morning[col]))
                all_people.add(p)
                shifts.append({"date": date_str, "type": "בוקר", "team": team_name, "person": p})
            if col < len(night) and night[col] and str(night[col]).strip():
                p = norm(str(night[col]))
                all_people.add(p)
                shifts.append({"date": date_str, "type": "לילה", "team": team_name, "person": p})
    
    return shifts, sorted(all_people)

def can_do_shift(constraint_val, shift_type):
    """Check if a constraint allows a specific shift type."""
    if not constraint_val:
        return False
    val = str(constraint_val).strip()
    if val in ("לא ידוע", "0", "None", "nan") or not val:
        return False
    if val == "לא יכול":
        return False
    if val == "יכול":
        return True
    if val == "יכול רק בוקר" and shift_type == "בוקר":
        return True
    if val == "יכול רק לילה" and shift_type == "לילה":
        return True
    return False

def eval_swap(shifts, person_a, person_b, a_shift, b_shift):
    """
    Evaluate proposed swap: a takes b_shift, b takes a_shift.
    Returns score (lower=better) or None if invalid.
    """
    new_a = [s for s in shifts if s["person"] == person_a and not (
        s["date"] == a_shift["date"] and s["type"] == a_shift["type"])]
    new_a.append({"date": b_shift["date"], "type": b_shift["type"],
                  "team": b_shift["team"], "person": person_a})
    
    new_b = [s for s in shifts if s["person"] == person_b and not (
        s["date"] == b_shift["date"] and s["type"] == b_shift["type"])]
    new_b.append({"date": a_shift["date"], "type": a_shift["type"],
                  "team": a_shift["team"], "person": person_b})
    
    # Check: no two shifts on same day
    if len([s for s in new_a if s["date"] == b_shift["date"]]) > 1: return None
    if len([s for s in new_b if s["date"] == a_shift["date"]]) > 1: return None
    
    # Check: night → same-next-day morning
    if b_shift["type"] == "בוקר":
        prev = (datetime.strptime(b_shift["date"], "%d/%m/%Y") - timedelta(days=1)).strftime("%d/%m/%Y")
        if any(s["date"] == prev and s["type"] == "לילה" for s in new_a): return None
    if a_shift["type"] == "בוקר":
        prev = (datetime.strptime(a_shift["date"], "%d/%m/%Y") - timedelta(days=1)).strftime("%d/%m/%Y")
        if any(s["date"] == prev and s["type"] == "לילה" for s in new_b): return None
    
    # Score
    score = 1  # base
    if a_shift["team"] != b_shift["team"]: score += 5  # cross-team penalty
    return score

def find_swaps(shifts, constraints, person_a, target_date, target_type, target_team):
    """Find all valid swap candidates respecting constraints."""
    a_shift = None
    for s in shifts:
        if (s["person"] == person_a and s["date"] == target_date
            and s["type"] == target_type and s["team"] == target_team):
            a_shift = s
            break
    if not a_shift:
        return []
    
    all_people = sorted(set(s["person"] for s in shifts))
    proposals = []
    
    for person_b in all_people:
        if person_b == person_a: continue
        
        # Check: person_b must be available for target_shift per constraints
        con_key = (target_date, target_team)
        b_con = constraints.get(person_b, {}).get(con_key, "לא ידוע")
        if not can_do_shift(b_con, target_type):
            continue
        
        # Check: person_a must be available for each of person_b's potential swap shifts
        b_shifts = [s for s in shifts if s["person"] == person_b]
        for b_shift in b_shifts:
            # Don't swap identical slots
            if b_shift["date"] == target_date and b_shift["type"] == target_type:
                continue
            
            # Check: person_a can do b_shift
            a_con_key = (b_shift["date"], b_shift["team"])
            a_con = constraints.get(person_a, {}).get(a_con_key, "לא ידוע")
            if not can_do_shift(a_con, b_shift["type"]):
                continue
            
            score = eval_swap(shifts, person_a, person_b, a_shift, b_shift)
            if score is not None:
                proposals.append({
                    "person_b": person_b,
                    "b_date": b_shift["date"],
                    "b_type": b_shift["type"],
                    "b_team": b_shift["team"],
                    "score": score,
                    "summary": (f"{person_b} ← {target_date} {target_type} ({target_team}), "
                                f"{person_a} ← {b_shift['date']} {b_shift['type']} ({b_shift['team']})"
                                if b_shift["date"] != target_date
                                else f"{person_b} ← {target_date} {target_type} ({target_team}), {person_a} free")
                })
    
    proposals.sort(key=lambda p: (p["score"],
        abs((datetime.strptime(p["b_date"], "%d/%m/%Y") - datetime.strptime(target_date, "%d/%m/%Y")).days)))
    return proposals


def apply_swap(shifts, propsal, person_a):
    """Apply a swap directly to the sheet."""
    # This writes the changes to the sheet cells
    pass  # TODO in next iteration


def main():
    rows = read_sheet_full()
    if not rows:
        print("ERROR: Could not read sheet")
        return
    
    shifts, all_people = parse_schedule(rows)
    constraints = parse_constraints(rows)
    print(f"Parsed {len(shifts)} shifts, {len(all_people)} people, {len(constraints)} with constraints")
    
    # CLI mode
    if len(sys.argv) >= 5:
        person_a = norm(sys.argv[1])
        target_date = sys.argv[2]
        target_type = sys.argv[3]
        target_team = sys.argv[4]
    else:
        print("Usage: miluim_swap_solver.py <person> <date> <shift_type> <team>")
        print(f"People: {', '.join(all_people)}")
        return
    
    proposals = find_swaps(shifts, constraints, person_a, target_date, target_type, target_team)
    
    if not proposals:
        print(f"No valid swaps found for {person_a}'s {target_date} {target_type} ({target_team})")
        print("Possible reasons: no one available, constraint conflicts, or rule violations")
        return
    
    print(f"\nFound {len(proposals)} valid swaps for {person_a}'s {target_date} {target_type} ({target_team}):")
    print(f"{'#':<4} {'Person B':<14} {'Takes from A':<32} {'Gives to A':<32} {'Score':<6}")
    print("─" * 88)
    for i, p in enumerate(proposals[:10], 1):
        takes = f"{target_date} {target_type} ({target_team})"
        gives = f"{p['b_date']} {p['b_type']} ({p['b_team']})"
        print(f"{i:<4} {p['person_b']:<14} {takes:<32} {gives:<32} {p['score']:<6}")
    
    # Save top 5 to JSON
    top5 = [{"person_b": p["person_b"], "b_date": p["b_date"],
             "b_type": p["b_type"], "b_team": p["b_team"],
             "score": p["score"], "summary": p["summary"]}
            for p in proposals[:5]]
    
    result = {
        "status": "found", "person_a": person_a,
        "target_date": target_date, "target_type": target_type, "target_team": target_team,
        "num_options": len(proposals), "options": top5
    }
    
    try:
        with open("/tmp/miluim_swap_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        print(f"\nResults saved to /tmp/miluim_swap_result.json")
    except Exception as e:
        print(f"Could not save result: {e}")


if __name__ == "__main__":
    main()
