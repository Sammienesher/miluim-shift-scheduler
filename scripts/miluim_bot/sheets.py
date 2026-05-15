"""Google Sheets interface for Shiftty miluim shift scheduler."""
import json
import logging
import re
import subprocess
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

from config import SHEET_ID, GROUPS_TAB, SCHEDULE_TAB


def gws(*args):
    """Execute gws CLI command and return parsed JSON output."""
    try:
        r = subprocess.run(
            ["gws"] + list(args),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            logger.error("gws error: %s", r.stderr.strip())
            return None
        t = r.stdout.strip()
        s = t.find("{")
        e = t.rfind("}")
        if s >= 0:
            return json.loads(t[s : e + 1])
        logger.warning("gws output had no JSON: %s", t[:200])
        return None
    except subprocess.TimeoutExpired:
        logger.error("gws timed out after 60s")
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("gws exception: %s", exc)
        return None


def norm(s):
    """Normalize a name string: strip, unify apostrophes, collapse whitespace."""
    s = s.strip().replace("\u2019", "'").replace("\u2018", "'").replace("\u05f3", "'")
    return re.sub(r"\s+", " ", s)


def get_people():
    """
    Return {name: {email, role, team, telegram_id}, ...}
    Reads groups!A1:H30.
    Team 1 (הערכה): cols A-C  (name, email, role)
    Team 2 (עיבוד):  cols D-F  (name, email, role)
    Telegram IDs: col G (team 1), col H (team 2)
    """
    data = gws("sheets", "spreadsheets", "values", "get",
               "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{GROUPS_TAB}'!A1:H30"}))
    if not data or "values" not in data:
        logger.error("No data from groups sheet")
        return {}

    rows = data["values"]
    people = {}
    start_row = 1  # skip header row (team names)

    for row in rows[start_row:]:
        # Row format: [name1, email1, role1, name2, email2, role2, tg1, tg2]
        # Team 1
        name1 = row[0].strip() if len(row) > 0 and row[0].strip() else None
        if name1:
            n_name1 = norm(name1)
            people[n_name1] = {
                "name": name1,
                "email": row[1].strip() if len(row) > 1 else "",
                "role": row[2].strip() if len(row) > 2 else "",
                "team": "הערכה",
                "telegram_id": row[6].strip() if len(row) > 6 and row[6].strip() else None,
                "raw_name": name1,
            }

        # Team 2
        name2 = row[3].strip() if len(row) > 3 and row[3].strip() else None
        if name2:
            n_name2 = norm(name2)
            people[n_name2] = {
                "name": name2,
                "email": row[4].strip() if len(row) > 4 else "",
                "role": row[5].strip() if len(row) > 5 else "",
                "team": "עיבוד",
                "telegram_id": row[7].strip() if len(row) > 7 and row[7].strip() else None,
                "raw_name": name2,
            }

    return people


def set_telegram_id(name, telegram_id):
    """
    Find person in groups sheet (normalized compare), write telegram_id
    to col G (team 1/הערכה) or col H (team 2/עיבוד).
    Returns True on success, False if not found.
    """
    n_name = norm(name)

    data = gws("sheets", "spreadsheets", "values", "get",
               "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{GROUPS_TAB}'!A1:H30"}))
    if not data or "values" not in data:
        return False

    rows = data["values"]
    for r_idx, row in enumerate(rows, start=1):  # sheet row (1-indexed)
        # Team 1 → col G (index 6)
        if len(row) > 0 and norm(row[0]) == n_name:
            col_letter = "G"
            cell_range = f"'{GROUPS_TAB}'!{col_letter}{r_idx}"
            result = gws("sheets", "spreadsheets", "values", "update",
                         "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": cell_range, "valueInputOption": "USER_ENTERED"}),
                         "--json", json.dumps({"values": [[str(telegram_id)]]}))
            return result is not None

        # Team 2 → col H (index 7)
        if len(row) > 3 and norm(row[3]) == n_name:
            col_letter = "H"
            cell_range = f"'{GROUPS_TAB}'!{col_letter}{r_idx}"
            result = gws("sheets", "spreadsheets", "values", "update",
                         "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": cell_range, "valueInputOption": "USER_ENTERED"}),
                         "--json", json.dumps({"values": [[str(telegram_id)]]}))
            return result is not None

    logger.warning("Person '%s' not found in groups sheet for tg_id assignment", name)
    return False


def find_date_column(data, target_date):
    """
    Given parsed sheet data, find which column index has the date matching target_date.
    Date header row is at index 2 (row 3 in sheet, 0-indexed).
    target_date: datetime.date object.
    Returns column index (int) or None.
    """
    if len(data) < 3:
        return None

    header_row = data["values"][2]  # row 3 (0-indexed)
    target_str = target_date.strftime("%d/%m/%y")

    for col_idx, cell in enumerate(header_row):
        cell_clean = cell.strip() if cell else ""
        # Match DD/MM/YY or DD/MM/YYYY — use search, not match (date may follow day name)
        if re.search(r"\d{2}/\d{2}/\d{2,4}", cell_clean):
            # Parse the date from the cell
            try:
                m = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", cell_clean)
                if m:
                    dd, mm, yy = m.group(1), m.group(2), m.group(3)
                    if len(yy) == 4:
                        yyyy = yy
                    else:
                        yyyy = "20" + yy
                    cell_date = datetime.strptime(f"{dd}/{mm}/{yyyy}", "%d/%m/%Y").date()
                    if cell_date == target_date:
                        return col_idx
            except (ValueError, IndexError):
                continue

    return None


def get_shifts_for_date(target_date_str):
    """
    Read schedule tab and return shifts for the given date.
    target_date_str: string in "DD/MM/YY" format (e.g., "01/06/26").

    Schedule tab layout ("משמרות הערכה ועיבוד"):
      Row 3 (idx 2): date headers for section 1 (analysis/הערכה)
      Row 4 (idx 3): Shift 1 (בוקר) assignments, first team
      Row 5 (idx 4): Shift 2 (לילה) assignments, first team
      Row 8 (idx 7): Shift 1 (בוקר) assignments, second team
      Row 9 (idx 8): Shift 2 (לילה) assignments, second team
    """
    data = gws("sheets", "spreadsheets", "values", "get",
               "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{SCHEDULE_TAB}'!A1:Z30"}))
    if not data or "values" not in data:
        logger.error("No schedule data")
        return None

    try:
        target_date = datetime.strptime(target_date_str, "%d/%m/%y").date()
    except ValueError:
        logger.error("Invalid date format: %s", target_date_str)
        return None

    col_idx = find_date_column(data, target_date)
    if col_idx is None:
        logger.info("Date %s not found in schedule", target_date_str)
        return {"date": target_date_str, "בוקר": [], "לילה": []}

    values = data["values"]

    def parse_cell(row_idx):
        """Parse names from a cell (newline or comma separated)."""
        if row_idx >= len(values):
            return []
        cell = values[row_idx][col_idx].strip() if col_idx < len(values[row_idx]) else ""
        if not cell:
            return []
        # Split by newline or comma
        names = re.split(r"[\n,]+", cell)
        return [norm(n) for n in names if n.strip()]

    morning_team1 = parse_cell(3)   # row 4 — team 1 shift 1 (בוקר)
    night_team1 = parse_cell(4)     # row 5 — team 1 shift 2 (לילה)
    morning_team2 = parse_cell(8)   # row 9 — team 2 shift 1 (בוקר)
    night_team2 = parse_cell(9)     # row 10 — team 2 shift 2 (לילה)

    morning = morning_team1 + morning_team2
    night = night_team1 + night_team2

    return {
        "date": target_date_str,
        "בוקר": morning,
        "לילה": night,
    }


def get_today_shifts():
    """Get shifts for today."""
    return get_shifts_for_date(datetime.now().strftime("%d/%m/%y"))


def get_shifts_for_tomorrow():
    """Get shifts for tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    return get_shifts_for_date(tomorrow.strftime("%d/%m/%y"))


def get_person_shifts(name, num_weeks=2):
    """
    Scan the schedule for the next num_weeks and find all shifts
    where the person is assigned.

    Returns list of {date, day_name, shift_type}.
    """
    n_name = norm(name)

    data = gws("sheets", "spreadsheets", "values", "get",
               "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{SCHEDULE_TAB}'!A1:Z30"}))
    if not data or "values" not in data:
        logger.error("No schedule data for person lookup")
        return []

    values = data["values"]
    if len(values) < 9:
        return []

    header_row = values[2]
    today = date.today()
    results = []

    # Scan all date columns
    for col_idx, cell in enumerate(header_row):
        cell_clean = cell.strip() if cell else ""
        m = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", cell_clean)
        if not m:
            continue

        try:
            dd, mm, yy = m.group(1), m.group(2), m.group(3)
            yyyy = "20" + yy if len(yy) == 2 else yy
            cell_date = datetime.strptime(f"{dd}/{mm}/{yyyy}", "%d/%m/%Y").date()
        except (ValueError, IndexError):
            continue

        # Only look at dates from today up to num_weeks ahead
        if cell_date < today:
            continue
        if cell_date > today + timedelta(weeks=num_weeks):
            continue

        def cell_has_name(row_idx):
            if row_idx >= len(values):
                return False
            row_cell = values[row_idx][col_idx].strip() if col_idx < len(values[row_idx]) else ""
            if not row_cell:
                return False
            names = [norm(x) for x in re.split(r"[\n,]+", row_cell) if x.strip()]
            return n_name in names

        date_str = cell_date.strftime("%d/%m/%y")
        day_name = cell_date.strftime("%A")

        # Hebrew day names
        day_map = {
            "Sunday": "ראשון",
            "Monday": "שני",
            "Tuesday": "שלישי",
            "Wednesday": "רביעי",
            "Thursday": "חמישי",
            "Friday": "שישי",
            "Saturday": "שבת",
        }
        day_name_he = day_map.get(day_name, day_name)

        if cell_has_name(3) or cell_has_name(8):
            results.append({
                "date": date_str,
                "day_name": day_name_he,
                "shift_type": "בוקר",
            })
        if cell_has_name(4) or cell_has_name(9):
            results.append({
                "date": date_str,
                "day_name": day_name_he,
                "shift_type": "לילה",
            })

    return results
