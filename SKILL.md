---
name: miluim-shift-scheduler
description: Automated shift scheduling for IDF Miluim (reserve duty) units. Two-pass scheduling with QA verification, draft/prod workflow, auto-notification. Works with Claude Code, Hermes Agent, OpenClaw.
license: MIT
---

# Miluim Shift Scheduler

Automatic shift scheduling for reserve duty units. Two-pass scheduling engine with QA verification, draft→production workflow, and multi-channel notifications. Framework-agnostic — works with Claude Code, Hermes Agent, OpenClaw, or any AI agent with Google Sheets access.

## What It Does

- **Two-pass scheduling** — initial fill + QA verification with auto-fix
- **Draft ↔ Production** — schedule in draft, verify, deploy to prod
- **Notifications** — Telegram, Email, WhatsApp on success/failure
- **Change detection** — monitors draft for manual edits 2x/day
- **Calendar sync** — pushes to Google Calendar, color-coded per person
- **Daily reports** — HTML email with today's assignments

## Workflow

### Two-Pass Scheduling

**Pass 1 — Initial Schedule**
Greedy week-by-week solver fills all shifts. Respects:
- Per-person constraints (available, shift-1-only, shift-2-only, unavailable)
- No same person on both shifts of the same day
- No consecutive shift-2→next-shift-1
- Fair distribution across available pool
- Consecutive shift-2 limit (default: max 2)

**Pass 2 — QA Verification**
Automated checks after scheduling:
- ✅ Same-day violations (same person both shifts)
- ✅ Rule 2 violations (shift 2 → next shift 1)
- ✅ Consecutive shift-2 limit exceeded
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

### Auto-Publish vs Admin Approval

Configured via `auto_copy_to_prod` in the rules sheet:

**Auto-Publish (`auto_copy_to_prod: true`):**
1. Run `miluim:fill` → two-pass scheduling
2. QA passes → auto-copy draft to prod
3. Notify admin: "✅ Published to production"
4. QA fails → auto-fix and retry (up to max_iterations)
5. All iterations fail → alert admin: "⚠️ Manual review needed"

**Wait for Approval (`auto_copy_to_prod: false` — default):**
1. Run `miluim:fill` → two-pass scheduling
2. QA passes → notify admin: "✅ Scheduling complete, waiting for approval"
3. Admin reviews, then runs `miluim:copy-to-prod`
4. QA fails → same auto-fix/retry behavior
5. Admin can also manually edit draft and re-run verification

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
| `num_departments` | Number of departments (default: 2) |
| `department_1_name` | Display name for department 1 |
| `department_1_shift1_row` | Sheet row for department 1, shift 1 |
| `department_1_shift2_row` | Sheet row for department 1, shift 2 |
| `department_2_name` | Display name for department 2 |
| `department_2_shift1_row` | Sheet row for department 2, shift 1 |
| `department_2_shift2_row` | Sheet row for department 2, shift 2 |

### Dates
| Setting | Description |
|---------|-------------|
| `date_start` | First scheduling day (dd/mm/yyyy) |
| `date_end` | Last scheduling day (dd/mm/yyyy) |

### Sheets
| Setting | Description |
|---------|-------------|
| `draft_sheet_id` | Google Sheets ID of the DRAFT spreadsheet |
| `prod_sheet_id` | Google Sheets ID of the PRODUCTION spreadsheet |
| `draft_tab_name` | Tab name for shifts in draft (default: משמרות) |
| `constraint_start_row` | First row of constraint data (default: 27) |

### Rules
| Setting | Description |
|---------|-------------|
| `consecutive_night_limit` | Max consecutive shift 2 per person (default: 2, 0=no limit) |
| `rule_no_same_day` | Prevent same person on both shifts of one day |
| `rule_no_consecutive_shift2_shift1` | Prevent shift-2→next-shift-1 consecutive |
| `rule_weekend_separation` | Avoid same person Fri+Sat |
| `verification_enabled` | Run QA pass after initial scheduling |
| `max_iterations` | Max scheduling iterations before alert (default: 3) |

### Workflow
| Setting | Description |
|---------|-------------|
| `workflow_mode` | `draft_first` (default) / `prod_direct` / `manual` |
| `auto_verify_draft` | Check draft for changes 2x/day (default: true) |
| `draft_check_times` | Check times (default: 09:00,15:00) |
| `auto_copy_to_prod` | `true` = auto-publish / `false` = wait for approval |

### Notifications
| Setting | Description |
|---------|-------------|
| `notify_channel_1` | Primary channel (telegram/email/whatsapp) |
| `notify_channel_2` | Secondary channel |
| `telegram_chat_id` | Telegram chat ID for notifications |
| `email_recipients` | Comma-separated email recipients |
| `notify_on_success` | Send notification when scheduling succeeds |
| `notify_on_failure` | Send notification when scheduling fails |
| `notify_on_draft_change` | Alert when draft sheet is modified |

## Notification Messages

### Success (after QA passes)
```
✅ Scheduling Complete — [unit name]
Two-pass verification passed.
Days scheduled: [X]
Shifts filled: [X]
Violations found: 0
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

Usage per framework:
- **Hermes Agent**: `hermes miluim:fill`
- **Claude Code**: `/miluim:fill` (slash command)
- **OpenClaw**: `miluim:fill` (native command)

## Cron Jobs

| Job | Schedule | Description | Self-Destruct |
|-----|----------|-------------|---------------|
| `sync-miluim-shifts` | 06:30 daily | Sync prod → Calendar | On end date |
| `miluim-daily-report` | 07:00 daily | Email today's shifts | On end date |
| `miluim-draft-check` | 09:00, 15:00 | Check draft for edits | On end date |

All jobs self-destruct on the configured end date.

## AI Agent Compatibility

This skill is designed to work with multiple AI agent frameworks:

| Framework | Compatibility | Setup |
|-----------|--------------|-------|
| **Claude Code** | ✅ Full | Load the SKILL.md context, use Google Sheets MCP tools |
| **Hermes Agent** | ✅ Full | `hermes skill install miluim-shift-scheduler` |
| **OpenClaw** | ✅ Full | Install from skill marketplace |
| **Any LLM** | ✅ Read-only | Access via Google Sheets API directly |

The scheduling logic is pure Python using the Google Sheets API (`gws` CLI). No framework-specific code.

## Quick Start

```bash
# 1. Create spreadsheets (draft + prod)
cp template/shifts_template.xlsx unit_draft.xlsx
cp template/shifts_template.xlsx unit_prod.xlsx

# 2. Upload to Google Sheets

# 3. Configure rules sheet: sheet IDs, dates, notifications

# 4. Run (varies by framework):
#    hermes miluim:fill
#    claude "schedule miluim shifts"
#    miluim:fill

# 5. Deploy: miluim:copy-to-prod

# 6. Enable automation: miluim:setup
```

## Dependencies

- Google Workspace CLI (`gws`) — for Sheets, Calendar, Gmail
- Google APIs enabled: Sheets, Calendar, Gmail
- Python 3.11+ with `openpyxl`

## License

MIT
