import logging
import os

SHEET_ID = "1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI"
TOKEN = os.environ.get("SHIFTTY_BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("SHIFTTY_BOT_TOKEN environment variable not set")
GROUPS_TAB = "groups"
SCHEDULE_TAB = "משמרות הערכה ועיבוד"
SHIFT_1_NAME = "בוקר"
SHIFT_2_NAME = "לילה"
SHIFT_1_HOURS = "06:00-14:00"
SHIFT_2_HOURS = "14:00-22:00"
LOG_LEVEL = "INFO"
