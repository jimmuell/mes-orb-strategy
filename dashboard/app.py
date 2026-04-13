import os
import re
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

from database import get_conn, init_db
from notifier import notify_task_complete, notify_task_ready

app = Flask(__name__)

# In-memory open trade tracker. Key: "{strategy}_{direction}", value: dict.
open_trades = {}


def parse_alert(message: str):
    """Parse a TradingView alert string into structured fields."""
    msg = (message or '').strip()
    m = re.match(
        r'^(.+?)\s+—\s+(LONG|SHORT)\s+(ENTRY|EXIT)\s+—\s+\S+\s+@\s+([\d.]+)',
        msg,
    )
    if m:
        strategy_raw = m.group(1)
        return {
            'strategy': 'Phase1' if 'ORB' in strategy_raw else 'Phase2',
            'direction': m.group(2),
            'action': m.group(3),
            'price': float(m.group(4)),
            'raw': message,
        }
    m2 = re.match(
        r'^(.+?)\s+—\s+SESSION CLOSE\s+—\s+\S+\s+@\s+([\d.]+)',
        msg,
    )
    if m2:
        strategy_raw = m2.group(1)
        return {
            'strategy': 'Phase1' if 'ORB' in strategy_raw else 'Phase2',
            'direction': None,
            'action': 'SESSION CLOSE',
            'price': float(m2.group(2)),
            'raw': message,
        }
    return None


def forward_to_whatsapp(message: str) -> None:
    """Forward alert to WhatsApp via Twilio webhook if configured."""
    webhook_url = os.environ.get('TWILIO_WEBHOOK_URL', '')
    if not webhook_url:
        return
    try:
        requests.post(
            webhook_url,
            json={'message': message, 'source': 'TradingView'},
            timeout=5,
        )
    except Exception as e:
        print(f'[alert] WhatsApp forward failed: {e}')


@app.route('/')
def index():
    return render_template('index.html')


# ---------- Trades ----------

@app.route('/api/trades', methods=['GET'])
def list_trades():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM trades ORDER BY date DESC, id DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/trades', methods=['POST'])
def add_trade():
    d = request.get_json(force=True) or {}
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO trades (date, strategy, direction, entry_time, entry_price,
                            exit_time, exit_price, exit_reason, pnl_dollars,
                            orb_high, orb_low, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            d.get('date') or datetime.now().strftime('%Y-%m-%d'),
            d.get('strategy', 'Phase1'),
            d.get('direction', 'LONG'),
            d.get('entry_time'),
            d.get('entry_price'),
            d.get('exit_time'),
            d.get('exit_price'),
            d.get('exit_reason'),
            d.get('pnl_dollars'),
            d.get('orb_high'),
            d.get('orb_low'),
            d.get('notes'),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({'id': new_id}), 201


@app.route('/api/trades/all', methods=['DELETE'])
def delete_all_trades():
    conn = get_conn()
    conn.execute('DELETE FROM trades')
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})


@app.route('/api/trades/<int:trade_id>', methods=['DELETE'])
def delete_trade(trade_id):
    conn = get_conn()
    conn.execute('DELETE FROM trades WHERE id = ?', (trade_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})


@app.route('/api/trades/<int:trade_id>', methods=['PUT'])
def update_trade(trade_id):
    d = request.get_json(force=True) or {}
    conn = get_conn()
    conn.execute(
        """
        UPDATE trades
        SET exit_time = COALESCE(?, exit_time),
            exit_price = COALESCE(?, exit_price),
            exit_reason = COALESCE(?, exit_reason),
            pnl_dollars = COALESCE(?, pnl_dollars),
            notes = COALESCE(?, notes)
        WHERE id = ?
        """,
        (
            d.get('exit_time'),
            d.get('exit_price'),
            d.get('exit_reason'),
            d.get('pnl_dollars'),
            d.get('notes'),
            trade_id,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------- Sessions ----------

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM sessions ORDER BY date DESC LIMIT 30').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/sessions', methods=['POST'])
def upsert_session():
    d = request.get_json(force=True) or {}
    conn = get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO sessions
        (date, phase1_valid, phase2_valid, adx_value, atr_pct, gap_pct,
         mes_open, prior_day_close, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            d.get('date') or datetime.now().strftime('%Y-%m-%d'),
            int(bool(d.get('phase1_valid'))) if d.get('phase1_valid') is not None else None,
            int(bool(d.get('phase2_valid'))) if d.get('phase2_valid') is not None else None,
            d.get('adx_value'),
            d.get('atr_pct'),
            d.get('gap_pct'),
            d.get('mes_open'),
            d.get('prior_day_close'),
            d.get('notes'),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------- Morning brief ----------

@app.route('/api/morning-brief', methods=['GET'])
def morning_brief():
    """Computed morning brief based on latest session row."""
    conn = get_conn()
    row = conn.execute(
        'SELECT * FROM sessions ORDER BY date DESC LIMIT 1'
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({'status': 'no_data'})

    session = dict(row)
    adx = session.get('adx_value')
    atr = session.get('atr_pct')
    gap = session.get('gap_pct')
    mes_open = session.get('mes_open')
    prior_close = session.get('prior_day_close')

    adx_ok_p1 = adx is not None and adx >= 15
    adx_ok_p2 = adx is not None and adx < 20
    atr_ok = atr is not None and 0.3 <= atr <= 2.0
    gap_ok = gap is not None and 0.32 <= abs(gap) <= 0.55

    return jsonify({
        'status': 'ok',
        'date': session.get('date'),
        'mes_open': mes_open,
        'prior_day_close': prior_close,
        'gap_pct': gap,
        'adx_value': adx,
        'atr_pct': atr,
        'phase1': {
            'valid': bool(session.get('phase1_valid')),
            'adx_ok': adx_ok_p1,
            'atr_ok': atr_ok,
        },
        'phase2': {
            'valid': bool(session.get('phase2_valid')),
            'adx_ok': adx_ok_p2,
            'atr_ok': atr_ok,
            'gap_ok': gap_ok,
        },
        'notes': session.get('notes'),
        'updated_at': session.get('created_at'),
    })


# ---------- Summary ----------

@app.route('/api/summary', methods=['GET'])
def summary():
    conn = get_conn()
    rows = conn.execute(
        'SELECT date, pnl_dollars FROM trades WHERE pnl_dollars IS NOT NULL ORDER BY date ASC, id ASC'
    ).fetchall()
    conn.close()

    pnls = [r['pnl_dollars'] for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total = sum(pnls)
    win_rate = (len(wins) / len(pnls) * 100) if pnls else 0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else None

    equity = []
    running = 0.0
    for r in rows:
        running += r['pnl_dollars']
        equity.append({'date': r['date'], 'equity': round(running, 2)})

    return jsonify({
        'total_trades': len(pnls),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(win_rate, 1),
        'total_pnl': round(total, 2),
        'profit_factor': round(pf, 2) if pf is not None else None,
        'equity_curve': equity,
    })


# ---------- Live price ----------

@app.route('/api/price', methods=['GET'])
def price():
    try:
        import yfinance as yf
        t = yf.Ticker('MES=F')
        data = t.history(period='1d', interval='1m')
        if data.empty:
            return jsonify({'error': 'no data'}), 503
        last = float(data['Close'].iloc[-1])
        first = float(data['Open'].iloc[0])
        change = last - first
        pct = (change / first * 100) if first else 0
        return jsonify({
            'symbol': 'MES=F',
            'price': round(last, 2),
            'change': round(change, 2),
            'change_pct': round(pct, 2),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 503


# ---------- Economic calendar ----------

@app.route('/api/calendar', methods=['GET'])
def calendar():
    # Free sources require API keys or scraping; return empty array by default.
    # Populate via scheduled job or manual POST in a future iteration.
    return jsonify([])


# ---------- Tasks ----------

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM tasks ORDER BY id DESC LIMIT 50').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/tasks/pending', methods=['GET'])
def pending_tasks():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/tasks', methods=['POST'])
def add_task():
    d = request.get_json(force=True) or {}
    title = d.get('title')
    if not title:
        return jsonify({'error': 'title required'}), 400
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO tasks (title, description, priority, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (
            title,
            d.get('description'),
            d.get('priority', 'normal'),
            d.get('created_by', 'Senior Claude'),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    notify_task_ready(title)
    return jsonify({'id': new_id}), 201


@app.route('/api/tasks/<int:task_id>/start', methods=['POST'])
def start_task(task_id):
    conn = get_conn()
    conn.execute("UPDATE tasks SET status = 'in_progress' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    d = request.get_json(force=True) or {}
    result = d.get('result', '')
    conn = get_conn()
    conn.execute(
        """
        UPDATE tasks
        SET status = 'complete', result = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (result, task_id),
    )
    row = conn.execute('SELECT title FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.commit()
    conn.close()
    if row:
        notify_task_complete(row['title'], result)
    return jsonify({'ok': True})


# ---------- TradingView webhook ----------

@app.route('/api/alert', methods=['POST'])
def receive_alert():
    """
    TradingView webhook endpoint. Accepts either JSON `{"message": "..."}`
    or a raw text body (TradingView can send either depending on config).
    """
    if request.is_json:
        data = request.get_json(silent=True) or {}
        message = data.get('message', '')
    else:
        message = request.get_data(as_text=True).strip()

    if not message:
        return jsonify({'status': 'error', 'reason': 'empty message'}), 400

    print(f'[ALERT] {message}')
    forward_to_whatsapp(message)

    parsed = parse_alert(message)
    if not parsed:
        return jsonify({'status': 'ok', 'parsed': False, 'message': message})

    strategy = parsed['strategy']
    direction = parsed['direction']
    action = parsed['action']
    price = parsed['price']
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    trade_key = f'{strategy}_{direction}' if direction else None

    if action == 'ENTRY':
        open_trades[trade_key] = {
            'date': today,
            'strategy': strategy,
            'direction': direction,
            'entry_time': now.strftime('%H:%M'),
            'entry_price': price,
        }
        print(f'[ENTRY] {trade_key} @ {price}')

    elif action in ('EXIT', 'SESSION CLOSE'):
        if action == 'SESSION CLOSE':
            keys_to_close = [k for k in list(open_trades.keys()) if k.startswith(strategy)]
        else:
            keys_to_close = [trade_key] if trade_key in open_trades else []

        for key in keys_to_close:
            open_trade = open_trades.pop(key, None)
            if not open_trade:
                continue

            entry_price = open_trade['entry_price']
            trade_direction = open_trade['direction']

            if trade_direction == 'LONG':
                pnl = (price - entry_price) * 5
            else:
                pnl = (entry_price - price) * 5
            pnl = round(pnl, 2)

            if action == 'SESSION CLOSE':
                exit_reason = 'Session Close'
            else:
                exit_reason = 'TP' if pnl > 0 else 'SL'

            conn = get_conn()
            conn.execute(
                """
                INSERT INTO trades
                (date, strategy, direction, entry_time, entry_price,
                 exit_time, exit_price, exit_reason, pnl_dollars)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    open_trade['date'],
                    open_trade['strategy'],
                    open_trade['direction'],
                    open_trade['entry_time'],
                    open_trade['entry_price'],
                    now.strftime('%H:%M'),
                    price,
                    exit_reason,
                    pnl,
                ),
            )
            conn.commit()
            conn.close()
            print(f'[TRADE LOGGED] {trade_direction} {strategy} P&L: ${pnl}')

    return jsonify({
        'status': 'ok',
        'parsed': True,
        'action': action,
        'strategy': strategy,
        'price': price,
    })


@app.route('/api/test-alert', methods=['POST'])
def test_alert():
    """Local curl-testable proxy to /api/alert."""
    return receive_alert()


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=8080, debug=True)
