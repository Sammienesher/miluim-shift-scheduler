#!/usr/bin/env python3
"""Groups watchdog v2 — detect membership changes AND auto-update the test tab.

When a new member is added to a team in the groups sheet:
  1. Insert a row in the test tab's constraints section, within that team's block
  2. Populate all date columns with "לא ידוע"
  3. (Dashboard updates handled by its live formulas)

When a member is removed:
  1. Delete their row from the test tab's constraints section

Uses ranges and dynamic detection — no hardcoded row numbers.
"""

import subprocess, json, os, re
from datetime import datetime

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
TARGET_TAB = "\u05de\u05e9\u05de\u05e8\u05d5\u05ea \u05d4\u05e2\u05e8\u05db\u05d4 \u05d5\u05e2\u05d9\u05d1\u05d5\u05d3"
GROUPS_RANGE = "groups!A1:Z30"
CONSTRAINTS_RANGE = "'\u05de\u05e9\u05de\u05e8\u05d5\u05ea \u05d4\u05e2\u05e8\u05db\u05d4 \u05d5\u05e2\u05d9\u05d1\u05d5\u05d3'!A1:BV30"
SNAPSHOT_FILE = os.path.expanduser("~/.hermes/.groups_snapshot.json")
TARGET_TAB_SHEET_ID = 1166224611


def gws(*args):
    r = subprocess.run(["gws"] + list(args), capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None
    t = r.stdout.strip()
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e+1]) if s >= 0 else None


def norm(s):
    s = s.strip().replace("\u2019", "'").replace("\u2018", "'").replace("\u05f3", "'")
    return re.sub(r'\s+', ' ', s)


def col_letter(n):
    """0-indexed column index to letter(s). col_letter(0) = 'A', col_letter(26) = 'AA'."""
    s = ""
    while True:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            break
    return s


def save_snapshot(data):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_snapshot():
    try:
        with open(SNAPSHOT_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def parse_teams(vals):
    """Parse groups sheet into {team_name: [{name, email, role}, ...]}.
    Each team = 3-column block (name|email|role). Stops on empty."""
    if not vals or len(vals) < 1:
        return {}
    teams = {}
    header = vals[0]
    for ci in range(0, len(header), 3):
        team_name = norm(header[ci]) if ci < len(header) and header[ci] else ""
        if not team_name:
            break
        members = []
        for ri in range(1, len(vals)):
            name = norm(vals[ri][ci]) if ci < len(vals[ri]) and vals[ri][ci] else ""
            if not name:
                break
            email = ""
            role = ""
            if ci+1 < len(vals[ri]) and vals[ri][ci+1]:
                email = norm(vals[ri][ci+1])
            if ci+2 < len(vals[ri]) and vals[ri][ci+2]:
                role = norm(vals[ri][ci+2])
            members.append({"name": name, "email": email, "role": role})
        teams[team_name] = members
    return teams


def compute_diff(old, current):
    """Return {added: [(team, name, role)], removed: [(team, name)], changed: [...]}."""
    changes = {"added": [], "removed": [], "changed": []}
    all_teams = set(list(old.keys()) + list(current.keys()))
    for team in sorted(all_teams):
        old_m = {m["name"]: m for m in old.get(team, [])}
        cur_m = {m["name"]: m for m in current.get(team, [])}
        for name in sorted(set(cur_m.keys()) - set(old_m.keys())):
            changes["added"].append((team, name, cur_m[name]["role"]))
        for name in sorted(set(old_m.keys()) - set(cur_m.keys())):
            changes["removed"].append((team, name))
        for name in sorted(set(old_m.keys()) & set(cur_m.keys())):
            if old_m[name]["role"] != cur_m[name]["role"]:
                changes["changed"].append((team, name, f"role: {old_m[name]['role']}\u2192{cur_m[name]['role']}"))
            if old_m[name]["email"] != cur_m[name]["email"]:
                changes["changed"].append((team, name, "email changed"))
    return changes


def find_constraints_structure(vals):
    """Scan constraints rows (index 11+) and return:
    - team_sections: [(team_name, start_row, end_row_before_next)], all 0-indexed
    - date_header_row: row index of the date header row
    - date_cols: list of column indices that contain dates
    """
    team_sections = []
    date_header_row = None
    date_cols = []
    current_team = None
    current_start = None

    for i in range(11, len(vals)):
        row = vals[i]
        if not row:
            continue
        cell0 = norm(row[0]) if row[0] else ""

        # Detect date header row
        if not cell0:
            continue
        if re.search(r'\d{2}/\d{2}/\d{2}', str(row[1] if len(row) > 1 else "")):
            if date_header_row is None and len(row) > 1 and str(row[1]).strip():
                date_header_row = i
                for j in range(1, len(row)):
                    if re.search(r'\d{2}/\d{2}/\d{2}', str(row[j])):
                        date_cols.append(j)
                continue

        # Detect team section headers: col A has a word, remaining cols are mostly empty
        if cell0 and cell0 not in ("\u05d0\u05d9\u05dc\u05d5\u05e6\u05d9\u05dd", "\u05d9\u05d5\u05dd"):
            # Check if this looks like a team header (no data in cols B-E)
            has_data = False
            for j in range(1, min(5, len(row))):
                if row[j] and str(row[j]).strip():
                    has_data = True
                    break
            if not has_data:
                # Close previous section
                if current_team:
                    team_sections.append((current_team, current_start, i))
                current_team = cell0
                current_start = i
                continue

    # Close last section
    if current_team:
        team_sections.append((current_team, current_start, len(vals)))

    return team_sections, date_header_row, date_cols


def insert_constraint_row(team_sections, team_name, member_name, date_cols, test_vals):
    """Insert a row for member_name in the given team's section.
    Populates with "לא ידוע" + data validation dropdown.
    Returns action string."""
    # Find the team section
    section = None
    for t, start, end in team_sections:
        if t == team_name:
            section = (start, end)
            break
    if section is None:
        return f"\u26a0\ufe0f Team '{team_name}' not found in constraints"

    team_start, section_end = section
    # Find insertion point: after the last member row in this section
    insert_idx = team_start + 1
    for i in range(team_start + 1, section_end):
        name = norm(test_vals[i][0]) if i < len(test_vals) and len(test_vals[i]) > 0 and test_vals[i][0] else ""
        if not name:
            break
        insert_idx = i + 1

    # Insert the row
    insert_body = {
        "requests": [{
            "insertDimension": {
                "range": {
                    "sheetId": TARGET_TAB_SHEET_ID,
                    "dimension": "ROWS",
                    "startIndex": insert_idx,
                    "endIndex": insert_idx + 1
                },
                "inheritFromBefore": False
            }
        }]
    }
    r = subprocess.run(
        ["gws", "sheets", "spreadsheets", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps(insert_body), "--format", "json"],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        return f"Insert row failed: {r.stderr[:200]}"

    # Write member name in col A + apply data validation dropdown with "לא ידוע" to all date cols
    first_date_col = date_cols[0] if date_cols else 1
    last_date_col = date_cols[-1] if date_cols else 74
    
    # Step 2a: Write name to column A
    sheet_row = insert_idx + 1
    r1 = subprocess.run(
        ["gws", "sheets", "spreadsheets", "values", "update",
         "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{TARGET_TAB}'!A{sheet_row}", "valueInputOption": "USER_ENTERED"}),
         "--json", json.dumps({"values": [[member_name]]}), "--format", "json"],
        capture_output=True, text=True, timeout=30
    )
    
    # Step 2b: Apply dropdown validation + "לא ידוע" to all date columns
    dropdown_body = {
        "requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": TARGET_TAB_SHEET_ID,
                    "startRowIndex": insert_idx,
                    "endRowIndex": insert_idx + 1,
                    "startColumnIndex": first_date_col,
                    "endColumnIndex": last_date_col + 1
                },
                "cell": {
                    "dataValidation": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "\u05d9\u05db\u05d5\u05dc"},
                                {"userEnteredValue": "\u05dc\u05d0 \u05d9\u05db\u05d5\u05dc"},
                                {"userEnteredValue": "\u05d9\u05db\u05d5\u05dc \u05e8\u05e7 \u05d1\u05d5\u05e7\u05e8"},
                                {"userEnteredValue": "\u05d9\u05db\u05d5\u05dc \u05e8\u05e7 \u05dc\u05d9\u05dc\u05d4"},
                                {"userEnteredValue": "\u05dc\u05d0 \u05d9\u05d3\u05d5\u05e2"}
                            ]
                        },
                        "strict": True,
                        "showCustomUi": True
                    },
                    "userEnteredValue": {"stringValue": "\u05dc\u05d0 \u05d9\u05d3\u05d5\u05e2"}
                },
                "fields": "userEnteredValue,dataValidation"
            }
        }]
    }
    r2 = subprocess.run(
        ["gws", "sheets", "spreadsheets", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps(dropdown_body), "--format", "json"],
        capture_output=True, text=True, timeout=30
    )
    
    status = "✅" if r2.returncode == 0 else "⚠️"
    return f"{status} Inserted {member_name} → {team_name} (row {sheet_row}, dropdown + לא ידוע)"


def delete_constraint_row(test_vals, member_name):
    """Find and delete a member's row from constraints (row 11+)."""
    # Use reversed search to avoid index issues
    for i in range(len(test_vals) - 1, 10, -1):
        row = test_vals[i]
        if not row or not row[0]:
            continue
        name = norm(row[0])
        if name == member_name:
            delete_body = {
                "requests": [{
                    "deleteDimension": {
                        "range": {
                            "sheetId": TARGET_TAB_SHEET_ID,
                            "dimension": "ROWS",
                            "startIndex": i,
                            "endIndex": i + 1
                        }
                    }
                }]
            }
            r = subprocess.run(
                ["gws", "sheets", "spreadsheets", "batchUpdate",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID}),
                 "--json", json.dumps(delete_body), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return f"Delete row failed: {r.stderr[:200]}"
            return f"Removed {member_name} (was row {i+1})"
    return f"{member_name} not found in constraints"


DASHBOARD_SHEET_ID = 405445626
PROD_TAB = "\u05de\u05e9\u05de\u05e8\u05d5\u05ea \u05d4\u05e2\u05e8\u05db\u05d4 \u05d5\u05e2\u05d9\u05d1\u05d5\u05d3"


def sync_dashboard_rows(current_teams, actions):
    """Ensure dashboard has enough rows for current team sizes.
    Insert rows with proper formulas when teams grow beyond pre-populated slots."""
    
    # Current layout:
    # Leaderboard: team1 at rows 10-14 (5 slots A2-A6), team2 at rows 16-25 (10 slots D2-D11)
    # Team section 1: rows 27-31 (5 slots A2-A6)
    
    team1_size = len(current_teams.get("\u05d4\u05e2\u05e8\u05db\u05d4", []))
    team2_size = len(current_teams.get("\u05e2\u05d9\u05d1\u05d5\u05d3", []))
    
    # Leaderboard pre-populated slots
    LB_T1_SLOTS = 5   # rows 10-14
    LB_T2_SLOTS = 10  # rows 16-25
    SEC_T1_SLOTS = 5  # rows 27-31
    
    # --- Leaderboard team 1: rows 10-14, insert before row 15 (blank separator) ---
    if team1_size > LB_T1_SLOTS:
        rows_needed = team1_size - LB_T1_SLOTS
        # Insert rows at index 14 (0-indexed, before the blank row 15)
        for i in range(rows_needed):
            idx = 14 + i  # grows with each insert
            rn = idx + 1  # sheet row number (0-indexed → 1-indexed)
            gr = LB_T1_SLOTS + 1 + i + 1  # groups A6+1, A6+2... (A2=row10, so A{rowNum-8})
            
            # Insert the row
            insert_body = {
                "requests": [{
                    "insertDimension": {
                        "range": {
                            "sheetId": DASHBOARD_SHEET_ID,
                            "dimension": "ROWS",
                            "startIndex": idx,
                            "endIndex": idx + 1
                        },
                        "inheritFromBefore": False
                    }
                }]
            }
            subprocess.run(
                ["gws","sheets","spreadsheets","batchUpdate",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID}),
                 "--json", json.dumps(insert_body), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            # Write formulas for the new row
            name_f = f'=IF(groups!A{gr}="","",groups!A{gr})'
            team_f = f'=IF(B{rn}="","",groups!A$1)'
            morning_f = f"=IF(B{rn}=\"\",\"\",COUNTIF('{PROD_TAB}'!4:4,B{rn}))"
            night_f = f"=IF(B{rn}=\"\",\"\",COUNTIF('{PROD_TAB}'!5:5,B{rn}))"
            total_f = f"=IF(B{rn}=\"\",\"\",D{rn}+E{rn})"
            chart_f = f'=IF(B{rn}="","",REPT("\u2588",D{rn}+E{rn}))'
            rank_f = f"=IF(B{rn}=\"\",\"\",ROW()-9)"
            
            vals = [[rank_f, name_f, team_f, morning_f, night_f, total_f, chart_f]]
            subprocess.run(
                ["gws","sheets","spreadsheets","values","update",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"dashboard!A{rn}:G{rn}", "valueInputOption": "USER_ENTERED"}),
                 "--json", json.dumps({"values": vals}), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            actions.append(f"  + Dashboard leaderboard row {rn} for team 1 (groups!A{gr})")
    
    # --- Leaderboard team 2: rows 16+, insert at end of team 2 block ---
    if team2_size > LB_T2_SLOTS:
        rows_needed = team2_size - LB_T2_SLOTS
        # Team 2 leaderboard starts at row 16; after team 1 rows (inserted above), find the right offset
        # Current end of team 2 block: row 15 + LB_T2_SLOTS + LB_T1_overflows = 25 + LB_T1_overflows
        # For simplicity, read the actual last row with a formula
        r = subprocess.run(
            ["gws","sheets","spreadsheets","values","get",
             "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": "dashboard!B16:B30", "valueRenderOption": "FORMULA"}),
             "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        raw = r.stdout; s=raw.find("{"); e=raw.rfind("}")
        b_vals = json.loads(raw[s:e+1]).get("values", []) if s >= 0 else []
        
        # Find last non-empty team 2 row
        last_t2_row = 15  # Default start anchor
        for i, row in enumerate(b_vals):
            if row and row[0] and str(row[0]).strip():
                # Check if this is a team 2 row (references groups!D)
                if "groups!D" in str(row[0]):
                    last_t2_row = 16 + i
        
        for i in range(rows_needed):
            idx = last_t2_row  # 0-indexed
            rn = idx + 1
            gr = LB_T2_SLOTS + 1 + i + 1
            
            insert_body = {
                "requests": [{
                    "insertDimension": {
                        "range": {
                            "sheetId": DASHBOARD_SHEET_ID,
                            "dimension": "ROWS",
                            "startIndex": idx,
                            "endIndex": idx + 1
                        },
                        "inheritFromBefore": False
                    }
                }]
            }
            subprocess.run(
                ["gws","sheets","spreadsheets","batchUpdate",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID}),
                 "--json", json.dumps(insert_body), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            name_f = f'=IF(groups!D{gr}="","",groups!D{gr})'
            team_f = f'=IF(B{rn}="","",groups!D$1)'
            morning_f = f"=IF(B{rn}=\"\",\"\",COUNTIF('{PROD_TAB}'!9:9,B{rn}))"
            night_f = f"=IF(B{rn}=\"\",\"\",COUNTIF('{PROD_TAB}'!10:10,B{rn}))"
            total_f = f"=IF(B{rn}=\"\",\"\",D{rn}+E{rn})"
            chart_f = f'=IF(B{rn}="","",REPT("\u2588",D{rn}+E{rn}))'
            rank_f = f"=IF(B{rn}=\"\",\"\",ROW()-9)"
            
            vals = [[rank_f, name_f, team_f, morning_f, night_f, total_f, chart_f]]
            subprocess.run(
                ["gws","sheets","spreadsheets","values","update",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"dashboard!A{rn}:G{rn}", "valueInputOption": "USER_ENTERED"}),
                 "--json", json.dumps({"values": vals}), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            last_t2_row += 1
            actions.append(f"  + Dashboard leaderboard row {rn} for team 2 (groups!D{gr})")
    
    # --- Team section 1: rows 27-31 ---
    if team1_size > SEC_T1_SLOTS:
        rows_needed = team1_size - SEC_T1_SLOTS
        # Insert after the last section 1 row (row 31 = index 30 initially)
        r = subprocess.run(
            ["gws","sheets","spreadsheets","values","get",
             "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": "dashboard!B27:B35", "valueRenderOption": "FORMULA"}),
             "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        raw = r.stdout; s=raw.find("{"); e=raw.rfind("}")
        b_vals = json.loads(raw[s:e+1]).get("values", []) if s >= 0 else []
        
        last_sec1_row = 30
        for i, row in enumerate(b_vals):
            if row and row[0] and str(row[0]).strip() and "groups!A" in str(row[0]):
                last_sec1_row = 27 + i
        
        for i in range(rows_needed):
            idx = last_sec1_row + 1
            rn = idx + 1
            gr = SEC_T1_SLOTS + 1 + i + 1
            
            insert_body = {
                "requests": [{
                    "insertDimension": {
                        "range": {
                            "sheetId": DASHBOARD_SHEET_ID,
                            "dimension": "ROWS",
                            "startIndex": idx,
                            "endIndex": idx + 1
                        },
                        "inheritFromBefore": False
                    }
                }]
            }
            subprocess.run(
                ["gws","sheets","spreadsheets","batchUpdate",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID}),
                 "--json", json.dumps(insert_body), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            rank = str(SEC_T1_SLOTS + 1 + i)
            name_f = f'=IF(groups!A{gr}="","",groups!A{gr})'
            morning_f = f"=IF(B{rn}=\"\",\"\",COUNTIF('{PROD_TAB}'!4:4,B{rn}))"
            night_f = f"=IF(B{rn}=\"\",\"\",COUNTIF('{PROD_TAB}'!5:5,B{rn}))"
            total_f = f"=IF(B{rn}=\"\",\"\",C{rn}+D{rn})"
            chart_f = f'=IF(B{rn}="","",REPT("\u2588",C{rn}+D{rn}))'
            
            vals = [[rank, name_f, morning_f, night_f, total_f, chart_f, ""]]
            subprocess.run(
                ["gws","sheets","spreadsheets","values","update",
                 "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"dashboard!A{rn}:G{rn}", "valueInputOption": "USER_ENTERED"}),
                 "--json", json.dumps({"values": vals}), "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            last_sec1_row += 1
            actions.append(f"  + Dashboard team section row {rn} for team 1 (groups!A{gr})")


# ===== MAIN =====

# 1. Read current groups
groups_data = gws("sheets", "+read", "--spreadsheet", SHEET_ID, "--range", GROUPS_RANGE, "--format", "json")
if not groups_data:
    print("Failed to read groups sheet", file=sys.stderr)
    exit(1)
current = parse_teams(groups_data.get("values", []))

# 2. Load snapshot
old = load_snapshot()
if old is None:
    save_snapshot(current)
    exit(0)  # First run — silent

# 3. Compute diff
changes = compute_diff(old, current)
save_snapshot(current)

if not changes["added"] and not changes["removed"] and not changes["changed"]:
    exit(0)  # Nothing changed — silent

# 4. Read test tab
test_data = gws("sheets", "+read", "--spreadsheet", SHEET_ID, "--range", CONSTRAINTS_RANGE, "--format", "json")
test_vals = test_data.get("values", []) if test_data else []

team_sections, date_header_row, date_cols = find_constraints_structure(test_vals)
if not date_cols:
    print("No date columns found in test tab constraints", file=sys.stderr)
    exit(1)

# 5. Execute actions
actions = []

for team, name, role in changes["added"]:
    result = insert_constraint_row(team_sections, team, name, date_cols, test_vals)
    actions.append(result)
    # Re-read after insert (rows shifted)
    test_data = gws("sheets", "+read", "--spreadsheet", SHEET_ID, "--range", CONSTRAINTS_RANGE, "--format", "json")
    test_vals = test_data.get("values", []) if test_data else []
    team_sections, _, date_cols = find_constraints_structure(test_vals)

for team, name in changes["removed"]:
    result = delete_constraint_row(test_vals, name)
    actions.append(result)
    test_data = gws("sheets", "+read", "--spreadsheet", SHEET_ID, "--range", CONSTRAINTS_RANGE, "--format", "json")
    test_vals = test_data.get("values", []) if test_data else []

# 5b. Sync dashboard rows if teams grew beyond pre-populated slots
sync_dashboard_rows(current, actions)

# 6. Report
today = datetime.now().strftime("%d/%m/%y")
report = [f"Groups changed ({today}):"]
for team, name, role in changes["added"]:
    report.append(f"  + {name} -> {team}")
for team, name in changes["removed"]:
    report.append(f"  - {name} <- {team}")
for team, name, desc in changes["changed"]:
    report.append(f"  ~ {name}: {desc}")

report.append("")
report.append("\u05e4\u05e2\u05d5\u05dc\u05d5\u05ea:")
report.extend(f"  * {a}" for a in actions)

print("\n".join(report))
