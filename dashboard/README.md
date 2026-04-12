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

## TradingView Webhook Setup

Point TradingView alerts at:

```
http://YOUR-NGROK-URL/api/alert
```

The dashboard auto-logs entries and exits and calculates P&L ($5/point for
MES). No manual trade entry required. Original alert text is also forwarded
to WhatsApp if `TWILIO_WEBHOOK_URL` is set.

Local test:

```bash
curl -X POST http://localhost:8080/api/alert \
  -H "Content-Type: application/json" \
  -d '{"message": "MES ORB v3 — SHORT ENTRY — MES1! @ 6468.75"}'

curl -X POST http://localhost:8080/api/alert \
  -H "Content-Type: application/json" \
  -d '{"message": "MES ORB v3 — SHORT EXIT — MES1! @ 6459.75"}'
```

## Task queue workflow

- Senior Claude creates tasks via `POST /api/tasks`
- Dashboard chimes and shows a toast when a new pending task arrives
- VS Claude reads pending tasks via `GET /api/tasks/pending`
- VS Claude marks complete via `POST /api/tasks/<id>/complete` with a result summary
