# Miluim Shift Scheduler

Automated shift scheduling system for IDF Miluim (reserve duty) units. Built for Hermes Agent.

## What It Does

- **Two-pass scheduling engine** — fills shifts + runs automated QA verification
- **Draft ↔ Production workflow** — schedule in draft, verify, then copy to prod
- **Multi-channel notifications** — Telegram, Email, WhatsApp
- **Auto change detection** — checks draft for manual edits twice daily
- **Syncs to Google Calendar** — color-coded events per person
- **Daily email reports** — formatted HTML with today's assignments

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
| **Rules-driven** | All config in the `rules` sheet |
| **Self-destruct** | Cron jobs auto-disable on end date |

## Two-Pass Scheduling

### Pass 1 — Initial Schedule
Greedy week-by-week solver fills all shifts respecting constraints, fairness, and scheduling rules.

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

Configure `auto_copy_to_prod` in the rules sheet:

**Auto-Publish (`true`):**
After QA passes → auto-copy draft → `✅ Published to production`
If QA fails after `max_iterations` → `⚠️ Manual review needed`

**Wait for Approval (`false` — default):**
After QA passes → notify admin → admin runs `hermes miluim:copy-to-prod`
Admin can review draft before publishing.

## Configuration Sheet

All settings in the `rules` sheet (3rd sheet in the template):

### Sections

| Section | Settings | Description |
|---------|----------|-------------|
| Basic Scheduling | `shifts_per_day`, `shift_1_name`, `people_per_shift_X` | Core shift config |
| Departments | `num_departments`, `department_X_name`, `department_X_rows` | Team structure |
| Dates | `date_start`, `date_end` | Scheduling period |
| Sheets | `draft_sheet_id`, `prod_sheet_id` | Google Sheets IDs |
| Rules | `consecutive_night_limit`, `rule_no_same_day` | Scheduling rules |
| Workflow | `workflow_mode`, `auto_verify_draft`, `draft_check_times` | Workflow config |
| Notifications | `notify_channel_X`, `telegram_chat_id`, `email_recipients` | Alert destinations |
| Advanced | `calendar_name`, `report_send_time`, `sync_time` | Misc settings |

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

## Commands

| Command | Description |
|---------|-------------|
| `hermes miluim:fill` | Run two-pass scheduling on draft |
| `hermes miluim:verify` | Run QA verification only |
| `hermes miluim:copy-to-prod` | Copy draft → production sheet |
| `hermes miluim:sync` | Sync production → Google Calendar |
| `hermes miluim:setup` | Setup all cron jobs |
| `hermes miluim:status` | Show scheduling status and stats |
| `hermes miluim:check-draft` | Manually trigger draft change check |

## Cron Jobs

| Job | Schedule | Description | Self-Destruct |
|-----|----------|-------------|---------------|
| `sync-miluim-shifts` | 06:30 daily | Sync prod → Calendar | On end date |
| `miluim-daily-report` | 07:00 daily | Email today's shifts | On end date |
| `miluim-draft-check` | 09:00, 15:00 | Check draft for edits | On end date |

## Quick Start

```bash
# 1. Install
hermes skill install miluim-shift-scheduler

# 2. Create templates (draft + prod)
cp template/shifts_template.xlsx unit_draft.xlsx
cp template/shifts_template.xlsx unit_prod.xlsx

# 3. Upload both to Google Sheets

# 4. Configure rules sheet with sheet IDs, dates, notifications

# 5. Schedule!
hermes miluim:fill           # Two-pass scheduling with QA
hermes miluim:copy-to-prod   # Deploy to production
hermes miluim:setup          # Enable cron jobs
```

## License

MIT
