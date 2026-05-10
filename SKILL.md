---
name: miluim-shift-scheduler
description: Automated shift scheduling for IDF Miluim (reserve duty) units. Generates fair schedules respecting constraints, syncs to Google Calendar, and sends daily email reports.
license: MIT
---

# Miluim Shift Scheduler

Automatic shift scheduling for reserve duty units. Manages morning/night shifts, respects individual constraints, and pushes everything to Google Calendar.

## When to Use

- Setting up a new shift schedule for a miluim rotation
- Generating fair assignments across a pool of officers
- Syncing schedules to a shared Google Calendar
- Setting up daily email reports for commanders

## Setup

### 1. Create Your Spreadsheet

Copy the template included with this skill:

```bash
cp skills/miluim-shift-scheduler/template/shifts_template.xlsx my_unit.xlsx
```

Upload to Google Sheets and fill in:
- **Team names** in cells B1 and A7 (or use your own layout)
- **People names** in the constraints section
- **Constraints** per person per day (יכול / לא יכול / יכול רק בוקר / יכול רק לילה / לא ידוע)
- **Rules** in the `rules` sheet

### 2. Configure the Sheet ID

```bash
# Store the sheet ID
hermes config set miluim_sheet_id "your-spreadsheet-id-here"
```

The sheet ID is the long string in the URL: `https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit`

### 3. Run the Scheduler

```bash
# Fill the schedule
hermes miluim:fill

# Sync to calendar
hermes miluim:sync

# Set up daily reports
hermes miluim:setup-reports
```

## Spreadsheet Layout

The template has these columns:
- **Column A**: Labels (person names, shift labels)
- **Columns B onward**: Days, grouped in 7-day weeks + 1 summary column
- **Constraints section**: Below the shift assignments, each row = one person with per-day availability

### Team Structure

By default, the template supports two teams:
- **Team 1** (הערכה/Evaluation): rows 3-5
- **Team 2** (עיבוד/Analysis): rows 8-10

### Constraint Values

| Value | Meaning |
|-------|---------|
| `יכול` | Available for any shift |
| `לא יכול` | Not available |
| `יכול רק בוקר` | Morning only |
| `יכול רק לילה` | Night only |
| `לא ידוע` | Unknown — treated as unavailable |

## Scheduling Rules

### Hard Rules (always enforced):

1. **No same person on both shifts of the same day**
2. **No consecutive night→morning** — night-shift worker can't work next morning
3. **Constraints are respected** — unavailable people are never assigned
4. **No guessing** — "לא ידוע" = unavailable

### Soft Rules (configured in `rules` sheet):

- **Consecutive night limit** — max nights in a row for same person (default: 2)
- **Fair distribution** — balances total shift loads

## Commands

### `hermes miluim:fill`

Reads the current spreadsheet, solves the schedule from today forward, and writes assignments back. Respects existing data for past dates.

### `hermes miluim:sync`

Reads the latest assignments from the spreadsheet and syncs them to a Google Calendar named "משמרות מילואים". Creates one event per officer per shift. Events are color-coded per person.

### `hermes miluim:setup-reports`

Creates two cron jobs:
- `sync-miluim-shifts` — runs daily at 06:30, syncs sheet → calendar
- `miluim-daily-report` — runs daily at 07:00, emails HTML report to configured recipients

Both self-destruct on the configured end date.

## Email Reports

Daily reports are HTML-formatted and include:
- Today's date
- Morning shift assignments (both teams)
- Night shift assignments (both teams)
- Who's unavailable today
- Running shift counts per person
- Quick stats

## Calendar Events

Each event in the Google Calendar is formatted as:
```
[Name] - Shift [Morning/Night] - [Team Name]
```
Example: `עומר נשר - משמרת בוקר - הערכה`

Events span the full shift period (default: 06:00-18:00 or 18:00-06:00).

## Cron Jobs

### Sync Job (06:30 daily)
```
python3 sync_miluim_shifts.py
```
- Reads sheet → computes current assignments
- Updates calendar events (adds/changes only, never deletes)
- Self-destructs on end date

### Report Job (07:00 daily)
```
python3 daily_report.py
```
- Generates HTML report
- Emails to configured recipients
- Self-destructs on end date

## Troubleshooting

### "No data found in range"
Check the sheet tab name and range. The skill expects a tab named "משמרות" or use the configured name.

### "Calendar sync failed"
Ensure the calendar exists with the right name. Create it manually first:
```bash
gws calendar insert --summary "משמרות מילואים"
```

### "Email not sending"
Check that gmail API is enabled and the sender email has access.
