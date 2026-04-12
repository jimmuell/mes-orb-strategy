# MES Trading Dashboard

Local web dashboard for morning briefing, paper trade tracking, and a task queue
Senior Claude uses to hand work to VS Claude.

## Quick start

```bash
cd dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080

## Stack

- Flask + SQLite (file at `dashboard/data/trading.db`, gitignored)
- Vanilla HTML/CSS/JS — no npm, no React
- Notifications: macOS `osascript` + WhatsApp via Twilio webhook
  (set `TWILIO_WEBHOOK_URL` env var; see `.env.example`)

## API

| Method | Route | Purpose |
|---|---|---|
| GET  | `/api/trades` | List trades |
| POST | `/api/trades` | Log a trade |
| PUT  | `/api/trades/<id>` | Update exit details |
| GET  | `/api/sessions` | Last 30 sessions |
| POST | `/api/sessions` | Upsert today's session |
| GET  | `/api/summary` | P&L stats + equity curve |
| GET  | `/api/price` | Live MES price via yfinance |
| GET  | `/api/calendar` | Today's high-impact events (stub) |
| GET  | `/api/tasks` | All tasks |
| GET  | `/api/tasks/pending` | Pending only |
| POST | `/api/tasks` | Create task (fires desktop notification) |
| POST | `/api/tasks/<id>/start` | Mark in progress |
| POST | `/api/tasks/<id>/complete` | Complete (fires notification + WhatsApp) |

## Task queue workflow

- Senior Claude creates tasks via `POST /api/tasks`
- Dashboard chimes and shows a toast when a new pending task arrives
- VS Claude reads pending tasks via `GET /api/tasks/pending`
- VS Claude marks complete via `POST /api/tasks/<id>/complete` with a result summary
