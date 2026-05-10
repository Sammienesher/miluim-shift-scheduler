---
name: miluim-shift-scheduler
description: Automated shift scheduling for IDF Miluim (reserve duty) units. Two-pass scheduling with QA verification, draft/prod workflow, auto-notification via Telegram/Email/WhatsApp.
license: MIT
---

# Miluim Shift Scheduler

Automatic shift scheduling for reserve duty units. Two-pass scheduling engine with QA verification, draft→production workflow, and multi-channel notifications.

## Workflow

### Two-Pass Scheduling

**Pass 1 — Initial Schedule**
Greedy week-by-week solver fills all shifts for the configured date range. Respects:
- Per-person constraints (available, morning-only, night-only, unavailable)
- No same person on both shifts of the same day
- No consecutive night→next-morning
- Fair distribution across available pool
- Consecutive night limit (default: max 2)

**Pass 2 — QA Verification**
After initial scheduling, runs automated checks:
- ✅ Same-day violations (same person both shifts)
- ✅ Rule 2 violations (night→next morning)
- ✅ Consecutive night limit exceeded
- ✅ Fairness variance (gap between most/least assigned)
- ✅ Weekend separation (same person Fri+Sat)
- ✅ All slots assigned
- ✅ Unavailable people not assigned

If violations found: auto-fix and re-run (up to `max_iterations`). On success: notify admin. On failure: alert with detailed report.

### Draft → Production Workflow

```
                          ┌─────────────┐
                          │   DRAFT     │
                          │  (editable) │
                          └──────┬──────┘
                                 │
                    ┌────────────▼──────────┐
                    │  Two-Pass Scheduler   │
                    │  1. Fill              │
                    │  2. Verify            │
                    └────────────┬──────────┘
                                 │
                    ┌────────────▼──────────┐
                    │  QA Passed?            │
                    │  Yes → Notify Admin    │
                    │  No  → Fix & Retry     │
                    └────────────┬──────────┘
                                 │
                    ┌────────────▼──────────┐
                    │  Admin: Copy to Prod   │
                    └────────────┬──────────┘
                                 │
                          ┌──────┴──────┐
                          │ PRODUCTION  │
                          │  (live)     │
                          └─────────────┘
```

Both sheets must have **identical structure** — same rows, columns, and layout. The `rules` sheet configures which rows map to which departments.

### Auto Change Detection

If `auto_verify_draft = true`, a cron job checks the draft sheet for manual changes twice a day (default: 09:00, 15:00). If changes detected:
1. Re-run QA verification
2. If violations found: alert admin
3. Notify admin about the change

## Configuration

All settings in the `rules` sheet:

### Basic Scheduling
| Setting | Description |
|---------|-------------|
| `shifts_per_day` | Number of shifts per day (default: 2) |
| `shift_1_name` | Name of first shift (default: בוקר) |
| `shift_2_name` | Name of second shift (default: לילה) |
| `people_per_shift_1` | People needed per shift 1 per day (default: 1) |
| `people_per_shift_2` | People needed per shift 2 per day (default: 1) |

### Departments
| Setting | Description |
|---------|-------------|
| `num_departments` | Number of departments (e.g., 2: הערכה, עיבוד) |
| `department_X_name` | Display name for department X |
| `department_X_morning_row` | Sheet row for department X, shift 1 |
| `department_X_night_row` | Sheet row for department X, shift 2 |

### Sheets
| Setting | Description |
|---------|-------------|
| `draft_sheet_id` | Google Sheets ID of the DRAFT spreadsheet |
| `prod_sheet_id` | Google Sheets ID of the PRODUCTION spreadsheet |
| `draft_tab_name` | Tab name for shifts in draft (default: משמרות) |
| `constraint_start_row` | First row of constraint data (default: 27) |

### Workflow
| Setting | Description |
|---------|-------------|
| `workflow_mode` | `draft_first` (default) schedule in draft then copy to prod / `prod_direct` write directly to prod / `manual` no auto-scheduling |
| `auto_verify_draft` | Check draft for changes 2x/day (default: true) |
| `draft_check_times` | Comma-separated check times (default: 09:00,15:00) |
| `auto_copy_to_prod` | `true` = auto-publish to prod after QA passes / `false` (default) = notify admin and wait for approval |
| `max_iterations` | Max scheduling iterations before alert (default: 3) |

### Auto-Publish vs Admin Approval

Configured via `auto_copy_to_prod` in the rules sheet:

**Auto-Publish (`auto_copy_to_prod: true`):**
1. Run `hermes miluim:fill` → two-pass scheduling
2. QA passes → auto-copy draft to prod
3. Notify admin: "✅ Published to production"
4. QA fails → auto-fix and retry (up to max_iterations)
5. All iterations fail → alert admin: "⚠️ Manual review needed"

**Wait for Approval (`auto_copy_to_prod: false` — default):**
1. Run `hermes miluim:fill` → two-pass scheduling
2. QA passes → notify admin: "✅ Scheduling complete, waiting for approval"
3. Admin reviews, then runs `hermes miluim:copy-to-prod`
4. QA fails → same auto-fix/retry behavior
5. Admin can also manually edit draft and re-run verification

### Notifications
| Setting | Description |
|---------|-------------|
| `notify_channel_1` | Primary notification channel (telegram/email/whatsapp) |
| `notify_channel_2` | Secondary notification channel |
| `telegram_chat_id` | Telegram chat ID for notifications |
| `email_recipients` | Comma-separated email recipients |
| `notify_on_success` | Send notification when scheduling succeeds |
| `notify_on_failure` | Send notification when scheduling fails |
| `notify_on_draft_change` | Alert when draft sheet is modified |

## Commands

| Command | Description |
|---------|-------------|
| `hermes miluim:fill` | Run two-pass scheduling on the draft sheet |
| `hermes miluim:verify` | Run QA verification only (no changes) |
| `hermes miluim:copy-to-prod` | Copy draft → production |
| `hermes miluim:sync` | Sync production sheet → Google Calendar |
| `hermes miluim:setup` | Setup all cron jobs (sync, report, draft check) |
| `hermes miluim:status` | Show current scheduling status and stats |
| `hermes miluim:check-draft` | Manually trigger draft change check |

## Cron Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| `sync-miluim-shifts` | 06:30 daily | Sync prod → Google Calendar |
| `miluim-daily-report` | 07:00 daily | Send email report with today's shifts |
| `miluim-draft-check` | 09:00, 15:00 | Check draft for manual changes + re-verify |

All jobs self-destruct on the configured end date.

## Notification Messages

### Success (after QA passes)
```
✅ Scheduling Complete — [unit name]
Two-pass verification passed.
Days scheduled: [X]
Shifts filled: [X]
Violations found: 0
Shift breakdown by person: [summary]
Next step: run 'copy draft to prod'
```

### Failure (QA fails after max iterations)
```
⚠️ Scheduling Alert — [unit name]
QA failed after [N] iterations.
Issues found: [list of violations]
Manual review required.
```

### Draft Change Detected
```
📋 Draft Change Detected — [unit name]
The draft sheet was modified manually.
Re-running QA verification...
[results]
```

## Quick Start

```bash
# Install the skill
hermes skill install miluim-shift-scheduler

# Copy the template (create 2 copies: draft + prod)
cp template/shifts_template.xlsx my_unit_draft.xlsx
cp template/shifts_template.xlsx my_unit_prod.xlsx

# Upload both to Google Sheets

# Configure the rules sheet with your sheet IDs and settings
# Then:
hermes miluim:fill        # Two-pass scheduling
hermes miluim:verify      # QA check
hermes miluim:copy-to-prod  # Push to production
hermes miluim:setup       # Enable cron jobs
```
