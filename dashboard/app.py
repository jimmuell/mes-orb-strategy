import os
import re
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request
from supabase import create_client

from database import get_conn, init_db
from notifier import notify_task_complete, notify_task_ready

app = Flask(__name__)

# In-memory open trade tracker. Key: "{strategy}_{direction}", value: dict.
open_trades = {}

# Supabase client for /webhook/trade. Init lazily so the app can boot without the env var.
SUPABASE_URL = "https://iwvpbnhsabnioxrlddqx.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
sb = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_KEY else None


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

def scrape_investing_calendar():
    try:
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        resp = requests.get('https://www.investing.com/economic-calendar/', headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.select('tr.js-event-item')
        if not rows:
            # Page is JS-rendered when accessed without session cookies — no
            # event rows in the raw HTML. Signal failure so the next source runs.
            return None
        events = []
        for row in rows:
            if row.get('data-importance', '') != '3':
                continue
            time_el = row.select_one('td.time')
            event_el = row.select_one('td.event')
            forecast_el = row.select_one('td.forecast')
            prev_el = row.select_one('td.prev')
            if event_el:
                events.append({
                    'time': time_el.text.strip() if time_el else '',
                    'event': event_el.text.strip(),
                    'forecast': forecast_el.text.strip() if forecast_el else '',
                    'previous': prev_el.text.strip() if prev_el else '',
                    'impact': 'HIGH',
                    'source': 'Investing.com',
                })
        return events
    except Exception as e:
        print(f'[calendar] Investing.com scrape failed: {e}')
        return None


def scrape_forexfactory_calendar():
    """Scrape ForexFactory weekly calendar, filter to today's red-impact rows.

    The FF weekly page lists Sun-Sat. Rows are separated by day-breaker rows
    (class `calendar__row--day-breaker`). We track the current day label and
    only emit events where current_day matches today's `%a %b D` format.
    """
    try:
        from bs4 import BeautifulSoup
        now = datetime.now()
        today_label = f"{now.strftime('%a %b ')}{now.day}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        resp = requests.get('https://www.forexfactory.com/calendar', headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        events = []
        current_day = None
        last_time = ''
        for row in soup.select('tr.calendar__row'):
            classes = row.get('class', [])
            if 'calendar__row--day-breaker' in classes:
                current_day = row.get_text(' ', strip=True)
                last_time = ''
                continue
            if current_day != today_label:
                continue
            icon = row.select_one('td.calendar__impact span')
            if not icon:
                continue
            if 'icon--ff-impact-red' not in ' '.join(icon.get('class', [])):
                continue
            time_el = row.select_one('td.calendar__time')
            event_el = row.select_one('td.calendar__event')
            cur_el = row.select_one('td.calendar__currency')
            forecast_el = row.select_one('td.calendar__forecast')
            prev_el = row.select_one('td.calendar__previous')
            raw_time = time_el.get_text(strip=True) if time_el else ''
            # FF leaves time blank for events at the same minute — inherit prior
            if raw_time:
                last_time = raw_time
            name = event_el.get_text(strip=True) if event_el else ''
            cur = cur_el.get_text(strip=True) if cur_el else ''
            display = f'{cur} {name}'.strip() if cur else name
            events.append({
                'time': raw_time or last_time,
                'event': display,
                'forecast': forecast_el.get_text(strip=True) if forecast_el else '',
                'previous': prev_el.get_text(strip=True) if prev_el else '',
                'impact': 'HIGH',
                'source': 'ForexFactory',
            })
        return events
    except Exception as e:
        print(f'[calendar] ForexFactory scrape failed: {e}')
        return None


def fetch_fmp_calendar():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        url = f'https://financialmodelingprep.com/api/v3/economic_calendar?from={today}&to={today}&apikey=demo'
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json() or []
        return [
            {
                'time': e.get('date', '')[-8:-3] if e.get('date') else '',
                'event': e.get('event', ''),
                'forecast': str(e.get('estimate', '') or ''),
                'previous': str(e.get('previous', '') or ''),
                'impact': 'HIGH',
                'source': 'FMP',
            }
            for e in data if e.get('impact') == 'High'
        ]
    except Exception as e:
        print(f'[calendar] FMP failed: {e}')
        return []


@app.route('/api/calendar', methods=['GET'])
def get_calendar():
    """Try sources in order. A source returning [] (worked, no events) is
    treated as success — we do NOT fall through to the next source, since
    "nothing on the calendar today" is a valid answer."""
    for name, fn in [
        ('Investing.com', scrape_investing_calendar),
        ('ForexFactory', scrape_forexfactory_calendar),
        ('FMP', fetch_fmp_calendar),
    ]:
        events = fn()
        if events is not None:
            return jsonify({
                'events': events,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'source': name,
            })
    return jsonify({
        'events': [],
        'date': datetime.now().strftime('%Y-%m-%d'),
        'source': None,
    })


# ---------- Pre-market news ----------

def _parse_rss(xml, source):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(xml, 'xml')
    out = []
    for item in soup.select('item'):
        title = item.find('title')
        link = item.find('link')
        if not title:
            continue
        out.append({
            'headline': title.get_text(strip=True),
            'url': link.get_text(strip=True) if link else '',
            'source': source,
        })
    return out


def fetch_market_news():
    """Pre-market headlines from Yahoo Finance and CNBC RSS feeds.
    MarketWatch and Reuters' public feeds are blocked/decommissioned."""
    headlines = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

    for source, url in [
        ('Yahoo', 'https://finance.yahoo.com/news/rssindex'),
        ('CNBC', 'https://www.cnbc.com/id/10000664/device/rss/rss.html'),
    ]:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                headlines.extend(_parse_rss(resp.text, source)[:6])
        except Exception as e:
            print(f'[news] {source} RSS failed: {e}')

    return headlines[:12]


@app.route('/api/news', methods=['GET'])
def get_news():
    news = fetch_market_news()
    return jsonify({
        'headlines': news,
        'updated': datetime.now().strftime('%H:%M CT'),
    })


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


@app.route('/webhook/health', methods=['GET'])
def webhook_health():
    return jsonify({'status': 'ok', 'service': 'tradinggym-webhook'}), 200


@app.route('/webhook/trade', methods=['POST'])
def webhook_trade():
    """Receive trade alerts from TradingView, write to Supabase live_trades."""
    if sb is None:
        return jsonify({'error': 'Supabase not configured (set SUPABASE_ANON_KEY)'}), 503

    data = request.get_json(silent=True)
    if not data or 'action' not in data:
        return jsonify({'error': 'Invalid payload'}), 400

    action = data.get('action')         # 'entry' or 'exit'
    direction = data.get('direction')   # 'long' or 'short'
    price = float(data.get('price', 0))
    contracts = int(data.get('contracts', 1))
    strategy_name = data.get('strategy', 'unknown')
    ticker = data.get('ticker', 'MES1!')

    session = sb.table('trading_sessions') \
        .select('*') \
        .eq('status', 'active') \
        .order('started_at', desc=True) \
        .limit(1) \
        .execute()

    if not session.data:
        return jsonify({'error': 'No active trading session'}), 400

    sess = session.data[0]
    session_id = sess['id']
    user_id = sess['user_id']
    commission_per_rt = float(sess.get('cost_per_trade', 1.27))
    tick_value = float(sess.get('tick_value', 1.25))
    tick_size = 0.25  # MES/ES

    if action == 'entry':
        trade = {
            'user_id': user_id,
            'trading_session_id': session_id,
            'direction': direction,
            'entry_price': price,
            'contracts': contracts,
            'strategy': strategy_name,
            'commission': commission_per_rt * contracts,
            'opened_at': datetime.utcnow().isoformat(),
        }
        result = sb.table('live_trades').insert(trade).execute()
        return jsonify({'status': 'entry_logged', 'trade_id': result.data[0]['id']}), 200

    elif action == 'exit':
        open_trade = sb.table('live_trades') \
            .select('*') \
            .eq('trading_session_id', session_id) \
            .eq('direction', direction) \
            .is_('result', 'null') \
            .order('opened_at', desc=True) \
            .limit(1) \
            .execute()

        if not open_trade.data:
            return jsonify({'error': 'No matching open trade'}), 400

        trade = open_trade.data[0]
        entry_price = float(trade['entry_price'])
        cts = int(trade['contracts'])

        if direction == 'long':
            ticks = (price - entry_price) / tick_size
        else:
            ticks = (entry_price - price) / tick_size

        gross_pnl = ticks * tick_value * cts
        commission = commission_per_rt * cts
        net_pnl = gross_pnl - commission
        result_val = 'win' if gross_pnl > 0 else ('loss' if gross_pnl < 0 else 'breakeven')

        sb.table('live_trades') \
            .update({
                'result': result_val,
                'gross_pnl': round(gross_pnl, 2),
                'net_pnl': round(net_pnl, 2),
                'ticks': round(ticks, 2),
                'commission': round(commission, 4),
            }) \
            .eq('id', trade['id']) \
            .execute()

        return jsonify({
            'status': 'exit_logged',
            'gross_pnl': round(gross_pnl, 2),
            'net_pnl': round(net_pnl, 2),
            'fee_drag': round((commission / gross_pnl * 100), 1) if gross_pnl > 0 else 0,
        }), 200

    return jsonify({'error': 'Unknown action'}), 400


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=8080, debug=True)
