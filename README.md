# Miluim Shift Scheduler

Automated shift scheduling system for IDF Miluim (reserve duty) units. Built for Hermes Agent.

## What It Does

- **Generates fair shift schedules** — automatically assigns morning/night shifts across a pool of officers, respecting individual constraints and distribution rules
- **Syncs to Google Calendar** — creates events per officer per shift, color-coded by person
- **Sends daily email reports** — emails shift assignments and constraints to commanders each morning
- **Reads rules from the spreadsheet** — no hardcoded logic; all rules come from a dedicated "rules" sheet

## Features

| Feature | Description |
|---------|-------------|
| **Constraint-aware scheduling** | Respects "can do morning only", "can do night only", "unavailable", and "unknown" constraints per person per day |
| **Fair distribution** | Balances shift loads evenly across the available pool |
| **Rule enforcement** | No same person on morning + night of same day; no consecutive night→next-morning; weekend separation (Fri/Sat) |
| **Soft constraint: consecutive limit** | Limits how many consecutive night shifts one person can get (default: max 2) |
| **Weekly auto-scheduling** | Solves each 7-day block independently for clean boundaries |
| **Google Calendar sync** | Pushes schedule to a shared calendar; each officer gets their own events, color-coded per person |
| **Daily report email** | Sends a beautifully formatted HTML email every morning with today's assignments |
| **Self-destruct on end date** | Cron jobs auto-disable when the duty period ends |
| **Rules-driven** | All scheduling rules, shift times, and team config are read from the spreadsheet — no code changes needed |

## Quick Start

### 1. Install the Skill in Hermes

```bash
hermes skill install miluim-shift-scheduler
```

### 2. Set Up Your Spreadsheet

Copy the template:

```bash
cp template/shifts_template.xlsx my_unit_schedule.xlsx
```

Upload to Google Sheets. Fill in your data.

### 3. Configure

Update the "rules" sheet with your preferences:
- Shift times (default: 06:00–18:00 / 18:00–06:00)
- Email recipients for daily reports
- Date range for the duty period
- Consecutive night limit

### 4. Run the Scheduler

```bash
# Load the skill
hermes skill load miluim-shift-scheduler

# Run: fill shifts and sync
hermes miluim:sync
```

## Spreadsheet Structure

The template has 3 sheets:

### 1. `משמרות` (Shifts)
The main assignment table. Organized in weekly blocks (7 days + summary column). Two teams per sheet:
- **Evaluation team** (הערכה) — rows 3-5 (header, morning, night)
- **Analysis team** (עיבוד) — rows 7-10 (header, header, morning, night)
- **Constraints section** — below the shifts, lists each person's availability per day

### 2. `rules`  
Scheduling rules and configuration. The skill reads this sheet to determine:
- `max_consecutive_nights` — maximum consecutive night shifts per person (default: 2)
- `shift_times_morning` — morning shift hours (default: "06:00-18:00")
- `shift_times_night` — night shift hours (default: "18:00-06:00")
- `email_recipients` — comma-separated list of daily report recipients
- `date_start` / `date_end` — the scheduling period
- `team_evaluation_name` / `team_analysis_name` — display names
- `rule_no_same_day` — enable/disable same-day check
- `rule_no_consecutive_night_morning` — enable/disable rule 2
- `rule_weekend_separation` — enable/disable weekend rule

### 3. `instructions`
Usage guide and legend for the spreadsheet.

## Scheduling Rules (Hard)

These rules are always enforced:

1. **No same person on both shifts of the same day** — a person cannot work morning AND night
2. **No consecutive night→morning** — if someone works night shift, they cannot work the next morning
3. **Respect constraints** — "לא יכול" (unavailable), "יכול רק בוקר" (morning only), "יכול רק לילה" (night only) are honored
4. **No unknown people assigned** — "לא ידוע" (unknown) is treated as unavailable

## Scheduling Rules (Soft)

Configured in the `rules` sheet:

- **Consecutive night limit** — default max 2 nights in a row for the same person
- **Weekend separation** — avoid same person on consecutive Fri/Sat (optional)
- **Fair distribution** — solver balances total shift counts per person

## Daily Report

The cron job `miluim-daily-report` sends an HTML email every morning at 07:00 with:
- Today's date
- All shifts for today (morning + night, both teams)
- Who's on leave / unavailable today
- Quick stats

## Calendar Sync

The cron job `sync-miluim-shifts` runs daily at 06:30 and:
- Reads the latest assignments from the spreadsheet
- Creates/updates Google Calendar events
- Color-codes by person (up to 9 distinct colors)
- Never deletes existing events (additive only)

## Dependencies

- Hermes Agent with Google Workspace integration (`gws` CLI)
- Google Sheets API enabled
- Gmail API enabled (for email reports)
- Google Calendar API enabled (for calendar sync)

## License

MIT
