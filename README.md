# Miluim Shift Scheduler

Automated shift scheduling system for IDF Miluim (reserve duty) units. Built for AI agents (Claude Code, Hermes Agent, OpenClaw, etc.).

## What It Does

- **Two-pass scheduling engine** — fills shifts + runs automated QA verification
- **Draft ↔ Production workflow** — schedule in draft, verify, then copy to prod
- **Multi-channel notifications** — Telegram, Email, WhatsApp
- **Auto change detection** — checks draft for manual edits twice daily
- **Syncs to Google Calendar** — color-coded events per person
- **Daily email reports** — formatted HTML with today's assignments

## Dashboard

The scheduler maintains a **dashboard** sheet with live visual summary:

| Section | Content |
|---------|---------|
| **Status Cards** | Total shifts filled, fill %, days remaining |
| **Leaderboard** | Ranked list of all personnel with morning/night/total counts + bar chart |
| **Team Leaderboards** | Per-team breakdowns (Team 1, Team 2) |
| **Charts** | Column chart (morning vs night per person), Pie chart (overall distribution) |
| **Today's Shifts** | Who's on duty right now (both teams, both shifts) |
| **QA Log** | Recent verification results |

The dashboard updates automatically after each scheduling run and draft check.

## Features

| Feature | Description |
|---------|-------------|
| **Constraint-aware scheduling** | Respects constraints per person per day |
| **Fair distribution** | Balances shift loads evenly |
| **Two-pass verification** | Schedule + QA pass catches violations |
| **Auto-fix** | Re-schedules when QA finds issues |
| **Draft/Prod workflow** | Test in draft, deploy to production |
| **Multi-channel notifications** | Telegram, email, WhatsApp on success/failure |
| **Change detection** | 2x daily check for manual draft edits |
| **Google Calendar sync** | Color-coded events per officer |
| **Daily report** | HTML email with today's assignments |
| **Rules-driven** | All config in the `settings` sheet |
| **Self-destruct** | Cron jobs auto-disable on end date |
| **Framework-agnostic** | Works with Claude Code, Hermes Agent, OpenClaw, etc. |

## Two-Pass Scheduling

### Pass 1 — Initial Schedule
Greedy week-by-week solver fills all shifts respecting constraints, fairness, and scheduling rules.
- **Unfillable shifts**: If no one is available, the cell is painted **red** and skipped — the scheduler continues without stopping.

### Pass 2 — QA Verification
Automated checks after scheduling:
- ✅ No same person on both shifts of the same day
- ✅ No consecutive night→next-morning
- ✅ Consecutive night limit (default: max 2)
- ✅ Fairness variance (gap between most/least assigned)
- ✅ Weekend separation (same person Fri+Sat)
- ✅ All slots assigned
- ✅ Unavailable people not assigned
- ✅ Constraints honored

**On success**: Sends notification to configured channels.
**On failure**: Auto-fix and retry (up to `max_iterations`). After max: alert admin with detailed report.

### Auto-Fix
When QA finds violations:
1. Identify problematic days
2. Re-solve those weeks with tighter constraints
3. Re-run QA
4. Repeat up to `max_iterations` times

## Draft → Production Workflow

```
                   ┌─────────────┐
                   │   DRAFT     │
                   └──────┬──────┘
                          │
              ┌───────────▼───────────┐
              │  Two-Pass Scheduler   │
              │  1. Fill shifts       │
              │  2. QA verification   │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │  QA Passed?           │
              │  Yes → Notify ✅      │
              │  No  → Fix & Retry 🔄 │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │  Copy to Production   │
              └───────────┬───────────┘
                          │
                   ┌──────┴──────┐
                   │ PRODUCTION │
                   │  (live)    │
                   └─────────────┘
```

Both sheets must have identical structure (rows, columns, layout).

### Auto-Publish vs Admin Approval

Configure `auto_copy_to_prod` in the settings sheet:

**Auto-Publish (`true`):**
After QA passes → auto-copy draft → `✅ Published to production`
If QA fails after `max_iterations` → `⚠️ Manual review needed`

**Wait for Approval (`false` — default):**
After QA passes → notify admin → admin runs `copy-to-prod` command
Admin can review draft before publishing.

## Configuration Sheet

All settings in the `settings` sheet (3rd sheet in the template):

### Sections

| Section | Settings | Description |
|---------|----------|-------------|
| Basic Scheduling | `shifts_per_day`, `shift_1_name`, `people_per_shift_X` | Core shift config |
| Groups | `num_groups`, `group_X_name`, `group_X_rows` | Team structure (names auto-populated from `groups` sheet) |
| Dates | `date_start`, `date_end` | Scheduling period |
| Sheets | `draft_sheet_id`, `prod_sheet_id` | Google Sheets IDs |
| Rules | `consecutive_night_limit`, `rule_no_same_day` | Scheduling rules |
| Workflow | `workflow_mode`, `auto_verify_draft`, `draft_check_times` | Workflow config |
| Notifications | `notify_channel_X`, `telegram_chat_id`, `email_recipients` | Alert destinations |
| Advanced | `calendar_name`, `report_send_time`, `sync_time` | Misc settings |

## Spreadsheet Structure

The spreadsheet has 4 sheets:

### 1. `משמרות` (Shifts)
The main assignment table. Organized in weekly blocks (7 days + summary column). Two teams per sheet:
- **Team 1** — rows 3-5 (header, shift 1, shift 2)
- **Team 2** — rows 7-10 (header, header, shift 1, shift 2)
- **Constraints section** — below the shifts (row 13+), lists each person's availability per day. The person names in this section are **formula-linked** to the `groups` sheet — adding/removing members there auto-updates the constraint list.

### 2. `groups`
Source of truth for group membership. Column A = group 1 (header `=groups!A1` + members), Column B = group 2 (header `=groups!B1` + members). Adding or removing a person here auto-updates the constraint names, the settings sheet group names, and the dashboard team sections.

### 3. `settings`  
Scheduling settings and configuration. Group name settings (`group_1_name`, `group_2_name`) are auto-populated from the `groups` sheet via formulas.

### 4. `dashboard`
Read-only dashboard with live stats, leaderboards (team sections linked to `groups` sheet), and charts. Auto-updated after each scheduling run.

## Scheduling Rules (Hard)

These rules are always enforced:

1. **No same person on both shifts of the same day** — a person cannot work shift 1 AND shift 2
2. **No consecutive shift 2→next shift 1** — if someone works shift 2, they cannot work the next shift 1
3. **Respect constraints** — "לא יכול" (unavailable), "יכול רק בוקר" (shift 1 only), "יכול רק לילה" (shift 2 only) are honored
4. **No unknown people assigned** — "לא ידוע" (unknown) is treated as unavailable

## Scheduling Rules (Soft)

Configured in the `settings` sheet:

- **Consecutive shift 2 limit** — default max 2 consecutive shifts for the same person
- **Weekend separation** — avoid same person on consecutive Fri/Sat (optional)
- **Fair distribution** — solver balances total shift counts per person

## Notifications

### Channels
- **Telegram** — sends to configured chat ID
- **Email** — sends to comma-separated recipients
- **WhatsApp** — sends via configured integration

### Events
- ✅ Scheduling success (after QA passes)
- ⚠️ Scheduling failure (after max retries)
- 📋 Draft change detected (manual edit)
- 📊 Daily shift report

## AI Agent Compatibility

This skill works with multiple AI agent frameworks:

| Framework | Compatibility | Notes |
|-----------|--------------|-------|
| **Claude Code** | ✅ Full | Use Claude Code CLI with the Google Workspace MCP tools |
| **Hermes Agent** | ✅ Full | Native skill support with `hermes skill install` |
| **OpenClaw** | ✅ Full | Install via OpenClaw skill marketplace |
| **Any LLM CLI** | ✅ Read-only | Use the Google Sheets API directly with any LLM |

The core logic is self-contained in Python scripts that use the Google Sheets API (via `gws` CLI). No framework-specific dependencies.

## Commands

| Command | Description |
|---------|-------------|
| `miluim:fill` | Run two-pass scheduling on the draft sheet |
| `miluim:verify` | Run QA verification only (no changes) |
| `miluim:copy-to-prod` | Copy draft → production |
| `miluim:sync` | Sync production sheet → Google Calendar |
| `miluim:setup` | Setup all cron jobs (sync, report, draft check) |
| `miluim:status` | Show current scheduling status and stats |
| `miluim:check-draft` | Manually trigger draft change check |

These commands work in any agent framework. In Hermes, use `hermes miluim:fill`. In Claude Code, use `/miluim:fill`. In OpenClaw, use `miluim:fill`.

## Auto Change Detection

If `auto_verify_draft = true`, the agent checks the draft sheet for manual changes twice a day (default: 09:00, 15:00). If changes detected:
1. Re-run QA verification
2. If violations found: alert admin
3. Notify admin about the change

## Cron Jobs

| Job | Schedule | Description | Self-Destruct |
|-----|----------|-------------|---------------|
| `sync-miluim-shifts` | 06:30 daily | Sync prod → Calendar | On end date |
| `miluim-daily-report` | 07:00 daily | Email today's shifts | On end date |
| `miluim-draft-check` | 09:00, 15:00 | Check draft for edits | On end date |

## Daily Report

The daily report (sent at 07:00) includes:
- Today's date
- All shifts for today (both teams)
- Who's on leave / unavailable today
- Running shift counts per person
- Quick stats

## Calendar Sync

The sync job (06:30 daily):
- Reads the latest assignments from the production sheet
- Creates/updates Google Calendar events
- Color-codes by person (up to 9 distinct colors)
- Never deletes existing events (additive only)

## Quick Start

```bash
# 1. Create your spreadsheets (draft + prod)
cp template/shifts_template.xlsx unit_draft.xlsx
cp template/shifts_template.xlsx unit_prod.xlsx

# 2. Upload both to Google Sheets

# 3. Configure the settings sheet with:
#    - Sheet IDs for draft and prod
#    - Date range
#    - Notification channels
#    - Scheduling rules

# 4. Run the scheduler (varies by framework):
#    Hermes:  hermes miluim:fill
#    Claude:  claude "Run miluim shift scheduler"
#    OpenClaw: miluim:fill

# 5. Deploy to production:
#    miluim:copy-to-prod

# 6. Enable cron jobs:
#    miluim:setup
```

## Dependencies

- Google Workspace CLI (`gws`) for sheet/calendar/gmail access
- Google Sheets, Calendar, and Gmail APIs enabled
- Python 3.11+ with openpyxl (for template creation)

## License

MIT
