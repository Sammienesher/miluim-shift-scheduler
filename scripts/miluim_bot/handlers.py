"""Telegram handlers for Shiftty miluim shift scheduler bot.

Uses python-telegram-bot v21 API with async handlers.
"""
import logging
from datetime import datetime, date

from telegram import Update
from telegram.ext import ContextTypes

from config import SHIFT_1_NAME, SHIFT_2_NAME, SHIFT_1_HOURS, SHIFT_2_HOURS
import sheets
import nlp
import messages as msg

logger = logging.getLogger(__name__)

# In-memory user registry: {user_id: {name, team, role, reminders_on}}
user_registry = {}


def _hours_for(shift_type):
    """Return hours string for a shift type."""
    if shift_type == SHIFT_1_NAME:
        return SHIFT_1_HOURS
    return SHIFT_2_HOURS


def _day_context(date_key):
    """Return a Hebrew string for 'today' or 'tomorrow'."""
    if date_key == "today":
        return "היום"
    return "מחר"


def _people_list_str(people):
    """Format a list of people into a bullet string."""
    if not people:
        return "אין"
    return "\n".join(f"• {p}" for p in people)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command. Register user or show help."""
    user_id = update.effective_user.id
    user_data = user_registry.get(user_id)

    if user_data:
        # Already registered
        await update.message.reply_text(msg.HELP, parse_mode="Markdown")
        return

    # Not registered — set flag to await name
    context.user_data["awaiting_name"] = True
    await update.message.reply_text(msg.WELCOME, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any non-command text message."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_data = user_registry.get(user_id)

    # --- Registration flow ---
    if context.user_data.get("awaiting_name"):
        n_text = sheets.norm(text)
        people = sheets.get_people()

        if n_text in people:
            person = people[n_text]
            user_registry[user_id] = {
                "name": person["name"],
                "team": person["team"],
                "role": person["role"],
                "reminders_on": True,
            }
            context.user_data["awaiting_name"] = False

            # Write telegram_id to sheet
            sheets.set_telegram_id(person["name"], str(user_id))

            await update.message.reply_text(msg.REGISTERED, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                msg.NOT_FOUND.format(name=text),
                parse_mode="Markdown",
            )
        return

    # --- Not registered ---
    if not user_data:
        await update.message.reply_text(msg.NOT_REGISTERED, parse_mode="Markdown")
        return

    # --- Parse intent ---
    parsed = nlp.parse(text, registered_name=user_data["name"])
    intent = parsed.get("intent")
    shift_type = parsed.get("shift_type")

    logger.info(
        "User %s (%s) → intent=%s, shift_type=%s",
        user_id, user_data["name"], intent, shift_type,
    )

    # --- Handle intents ---
    if intent == "help":
        await update.message.reply_text(msg.HELP, parse_mode="Markdown")

    elif intent == "whoami":
        reminders_status = "מופעלות ✅" if user_data["reminders_on"] else "כבויות ❌"
        await update.message.reply_text(
            msg.WHOAMI.format(
                name=user_data["name"],
                team=user_data["team"],
                role=user_data["role"],
                reminders_status=reminders_status,
            ),
            parse_mode="Markdown",
        )

    elif intent == "toggle_reminders":
        enable = parsed.get("enable")
        if enable is True:
            user_data["reminders_on"] = True
            await update.message.reply_text(msg.REMINDERS_ON, parse_mode="Markdown")
        elif enable is False:
            user_data["reminders_on"] = False
            await update.message.reply_text(msg.REMINDERS_OFF, parse_mode="Markdown")
        else:
            # Toggle
            user_data["reminders_on"] = not user_data["reminders_on"]
            if user_data["reminders_on"]:
                await update.message.reply_text(msg.REMINDERS_ON, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg.REMINDERS_OFF, parse_mode="Markdown")

    elif intent == "next_shift":
        name = user_data["name"]
        shifts = sheets.get_person_shifts(name, num_weeks=4)

        # Filter by shift_type if specified
        if shift_type:
            shifts = [s for s in shifts if s["shift_type"] == shift_type]

        if not shifts:
            await update.message.reply_text(msg.NO_UPCOMING, parse_mode="Markdown")
        else:
            next_shift = shifts[0]
            hours = _hours_for(next_shift["shift_type"])
            await update.message.reply_text(
                msg.NEXT_SHIFT.format(
                    shift_type=next_shift["shift_type"],
                    day_name=next_shift["day_name"],
                    date=next_shift["date"],
                    hours=hours,
                ),
                parse_mode="Markdown",
            )

    elif intent == "today":
        name = user_data["name"]
        today_shifts = sheets.get_today_shifts()
        if not today_shifts:
            await update.message.reply_text(msg.NO_SHIFT_TODAY, parse_mode="Markdown")
            return

        n_name = sheets.norm(name)
        found = None
        for st in (SHIFT_1_NAME, SHIFT_2_NAME):
            if n_name in today_shifts.get(st, []):
                found = st
                break

        if found:
            hours = _hours_for(found)
            await update.message.reply_text(
                msg.SHIFT_TODAY.format(
                    shift_type=found,
                    date=today_shifts["date"],
                    hours=hours,
                ),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(msg.NO_SHIFT_TODAY, parse_mode="Markdown")

    elif intent == "tomorrow":
        name = user_data["name"]
        tomorrow_shifts = sheets.get_shifts_for_tomorrow()
        if not tomorrow_shifts:
            await update.message.reply_text(msg.NO_SHIFT_TOMORROW, parse_mode="Markdown")
            return

        n_name = sheets.norm(name)
        found = None
        for st in (SHIFT_1_NAME, SHIFT_2_NAME):
            if n_name in tomorrow_shifts.get(st, []):
                found = st
                break

        if found:
            hours = _hours_for(found)
            tomorrow_date = date.today()
            from datetime import timedelta
            tomorrow_date = (tomorrow_date + timedelta(days=1)).strftime("%d/%m/%y")
            day_name_map = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
            day_name = day_name_map[datetime.now().weekday()]  # tomorrow is (today+1)
            # Better calculation
            import datetime as dt
            day_idx = (dt.date.today() + dt.timedelta(days=1)).weekday()
            he_days = {0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת", 6: "ראשון"}

            await update.message.reply_text(
                msg.SHIFT_TOMORROW.format(
                    shift_type=found,
                    day_name=he_days[day_idx],
                    date=tomorrow_shifts["date"],
                    hours=hours,
                ),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(msg.NO_SHIFT_TOMORROW, parse_mode="Markdown")

    elif intent == "this_week":
        name = user_data["name"]
        shifts = sheets.get_person_shifts(name, num_weeks=1)

        if shift_type:
            shifts = [s for s in shifts if s["shift_type"] == shift_type]

        if not shifts:
            await update.message.reply_text(msg.NO_SHIFTS_THIS_WEEK, parse_mode="Markdown")
        else:
            lines = [msg.THIS_WEEK]
            for s in shifts:
                hours = _hours_for(s["shift_type"])
                lines.append(
                    msg.SHIFT_LINE.format(
                        day_name=s["day_name"],
                        date=s["date"],
                        shift_type=s["shift_type"],
                        hours=hours,
                    )
                )
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif intent == "whos_on":
        date_key = parsed.get("date", "today")
        st = shift_type or "בוקר"

        if date_key == "today":
            shifts_data = sheets.get_today_shifts()
        else:
            shifts_data = sheets.get_shifts_for_tomorrow()

        if not shifts_data:
            await update.message.reply_text(
                msg.WHOS_ON_NONE.format(
                    shift_type=st,
                    day_context=_day_context(date_key),
                ),
                parse_mode="Markdown",
            )
            return

        people_list = shifts_data.get(st, [])
        if not people_list:
            await update.message.reply_text(
                msg.WHOS_ON_NONE.format(
                    shift_type=st,
                    day_context=_day_context(date_key),
                ),
                parse_mode="Markdown",
            )
        else:
            hours = _hours_for(st)
            await update.message.reply_text(
                msg.WHOS_ON.format(
                    shift_type=st,
                    day_context=_day_context(date_key),
                    date=shifts_data["date"],
                    hours=hours,
                    people_list=_people_list_str(people_list),
                ),
                parse_mode="Markdown",
            )

    elif intent == "list_shifts":
        name = user_data["name"]
        shifts = sheets.get_person_shifts(name, num_weeks=4)

        if shift_type:
            shifts = [s for s in shifts if s["shift_type"] == shift_type]

        if not shifts:
            await update.message.reply_text(msg.NO_UPCOMING, parse_mode="Markdown")
        else:
            lines = ["*המשמרות הקרובות:*"]
            for s in shifts:
                hours = _hours_for(s["shift_type"])
                lines.append(
                    msg.SHIFT_LINE.format(
                        day_name=s["day_name"],
                        date=s["date"],
                        shift_type=s["shift_type"],
                        hours=hours,
                    )
                )
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    else:
        await update.message.reply_text(msg.UNKNOWN, parse_mode="Markdown")


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Job queue callback: iterate registered users and send reminder
    to those who have a shift tomorrow and have reminders_on.
    """
    logger.info("Running daily reminder check...")
    import datetime as dt

    tomorrow_shifts = sheets.get_shifts_for_tomorrow()
    if not tomorrow_shifts:
        logger.info("No shifts tomorrow — skipping reminders")
        return

    n_morning = [sheets.norm(n) for n in tomorrow_shifts.get(SHIFT_1_NAME, [])]
    n_night = [sheets.norm(n) for n in tomorrow_shifts.get(SHIFT_2_NAME, [])]

    # Build {normalized_name: shift_type} lookup
    assigned = {}
    for n in n_morning:
        assigned[n] = SHIFT_1_NAME
    for n in n_night:
        assigned[n] = SHIFT_2_NAME

    if not assigned:
        logger.info("No one assigned tomorrow — skipping reminders")
        return

    tomorrow_date = dt.date.today() + dt.timedelta(days=1)
    day_idx = tomorrow_date.weekday()
    he_days = {0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת", 6: "ראשון"}
    day_name = he_days[day_idx]
    date_str = tomorrow_date.strftime("%d/%m/%y")

    people = sheets.get_people()

    for user_id, user_data in list(user_registry.items()):
        if not user_data.get("reminders_on", True):
            continue

        n_name = sheets.norm(user_data["name"])
        shift_type_assigned = assigned.get(n_name)
        if not shift_type_assigned:
            continue

        hours = _hours_for(shift_type_assigned)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=msg.REMINDER_MSG.format(
                    shift_type=shift_type_assigned,
                    day_name=day_name,
                    date=date_str,
                    hours=hours,
                ),
                parse_mode="Markdown",
            )
            logger.info("Reminder sent to %s (user %s)", user_data["name"], user_id)
        except Exception as e:
            logger.error("Failed to send reminder to user %s: %s", user_id, e)
