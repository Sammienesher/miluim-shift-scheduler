"""Hebrew NLP intent parser for Shiftty bot."""
import re


def parse(text, registered_name=None):
    """
    Parse user text and return dict with 'intent' and optional parameters.

    Args:
        text: Raw user message (Hebrew/English).
        registered_name: Currently registered user name (unused currently, for future).

    Returns:
        dict with at least 'intent' key.
    """
    text = text.strip()

    # --- Help ---
    if text in ("עזרה", "עזרה?", "help", "/help", "הוראות"):
        return {"intent": "help"}

    # --- Who am I ---
    if text in ("מי אני", "מי אני?", "פרטים", "הפרטים שלי", "פרופיל"):
        return {"intent": "whoami"}

    # --- Toggle reminders ---
    if "תזכור" in text or "התראה" in text or "remind" in text.lower():
        if any(w in text for w in ["הפסק", "כבה", "בטל", "לא רוצה", "עצור", "stop", "אל"]):
            return {"intent": "toggle_reminders", "enable": False}
        if any(w in text for w in ["תפעיל", "הפעל", "כן", "חזר", "התחל", "תזכיר", "start"]):
            return {"intent": "toggle_reminders", "enable": True}
        return {"intent": "toggle_reminders"}  # no explicit off/on → toggle

    # --- Shift type filter ---
    shift_type = None
    if any(w in text for w in ["לילה", "לילית", "ערב", "לילי"]):
        shift_type = "לילה"
    elif any(w in text for w in ["בוקר", "בבוקר", "בוקרית"]):
        shift_type = "בוקר"

    # --- Next shift ---
    if any(w in text for w in ["הבא", "הבאה", "הקרוב", "הקרובה", "הבאה שלי"]):
        return {"intent": "next_shift", "shift_type": shift_type}

    # --- Tomorrow (whos on vs my shift) ---
    if "מחר" in text:
        if "מי" in text or "מיה" in text:
            return {"intent": "whos_on", "date": "tomorrow", "shift_type": shift_type or "בוקר"}
        if "לי" in text or "שלי" in text or "יש לי" in text:
            return {"intent": "tomorrow", "shift_type": shift_type}
        return {"intent": "tomorrow", "shift_type": shift_type}

    # --- Today / this evening ---
    if any(w in text for w in ["היום", "הערב", "עכשיו", "היום בלילה"]):
        if "מי" in text:
            return {"intent": "whos_on", "date": "today", "shift_type": shift_type or "בוקר"}
        return {"intent": "today", "shift_type": shift_type}

    # --- This week ---
    if "שבוע" in text or "השבוע" in text:
        return {"intent": "this_week", "shift_type": shift_type}

    # --- Next week ---
    if "שבוע הבא" in text:
        return {"intent": "next_week", "shift_type": shift_type}

    # --- Who is on duty ---
    if "מי" in text or "מיה" in text:
        date = "today"
        if "מחר" in text:
            date = "tomorrow"
        return {"intent": "whos_on", "date": date, "shift_type": shift_type or "בוקר"}

    # --- List all upcoming ---
    if any(w in text for w in ["כל המשמרות", "כל המשמרות שלי", "רשימה", "לוח"]):
        return {"intent": "list_shifts", "shift_type": shift_type}

    # --- Default / unknown ---
    return {"intent": "unknown"}
