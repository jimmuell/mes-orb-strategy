// MES Dashboard client
const api = (p, opts={}) => fetch(p, opts).then(r => r.json());

// ---------- Sounds (Web Audio API) ----------
let audioCtx;
function getAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}
function playTones(freqs, dur) {
  const ctx = getAudio();
  const now = ctx.currentTime;
  const step = dur / freqs.length;
  freqs.forEach((f, i) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = f;
    o.type = 'sine';
    g.gain.setValueAtTime(0, now + i * step);
    g.gain.linearRampToValueAtTime(0.15, now + i * step + 0.02);
    g.gain.linearRampToValueAtTime(0, now + (i + 1) * step);
    o.connect(g); g.connect(ctx.destination);
    o.start(now + i * step);
    o.stop(now + (i + 1) * step);
  });
}
function playChime() { playTones([880, 1100, 1320], 0.5); }
function playComplete() { playTones([660, 880], 0.4); }

// ---------- Helpers ----------
function el(tag, opts = {}, children = []) {
  const e = document.createElement(tag);
  if (opts.class) e.className = opts.class;
  if (opts.text !== undefined) e.textContent = opts.text;
  if (opts.style) Object.assign(e.style, opts.style);
  if (opts.onClick) e.addEventListener('click', opts.onClick);
  children.forEach(c => e.appendChild(c));
  return e;
}
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

function showConfirm(title, message, onConfirm) {
  const modal = document.getElementById('confirmModal');
  document.getElementById('confirmTitle').textContent = title;
  document.getElementById('confirmMessage').textContent = message;
  modal.style.display = 'flex';

  const okBtn = document.getElementById('confirmOk');
  const cancelBtn = document.getElementById('confirmCancel');

  function cleanup() {
    modal.style.display = 'none';
    okBtn.replaceWith(okBtn.cloneNode(true));
    cancelBtn.replaceWith(cancelBtn.cloneNode(true));
  }

  document.getElementById('confirmOk').addEventListener('click', () => {
    cleanup();
    onConfirm();
  });
  document.getElementById('confirmCancel').addEventListener('click', cleanup);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) cleanup();
  }, { once: true });
}

// ---------- Clock + countdown ----------
function updateClock() {
  const now = new Date();
  const ct = new Date(now.toLocaleString('en-US', { timeZone: 'America/Chicago' }));
  const h = String(ct.getHours()).padStart(2, '0');
  const m = String(ct.getMinutes()).padStart(2, '0');
  const s = String(ct.getSeconds()).padStart(2, '0');
  document.getElementById('ctTime').textContent = `${h}:${m}:${s} CT`;

  const open = new Date(ct);
  open.setHours(8, 30, 0, 0);
  let diff = open - ct;
  let label = 'to open';
  if (diff < 0) { diff += 24 * 3600 * 1000; label = 'to next open'; }
  const hh = Math.floor(diff / 3600000);
  const mm = Math.floor((diff % 3600000) / 60000);
  const ss = Math.floor((diff % 60000) / 1000);
  document.getElementById('countdown').textContent =
    `${hh}h ${mm}m ${ss}s ${label}`;
}
setInterval(updateClock, 1000);
updateClock();

// ---------- Price ----------
async function loadPrice() {
  try {
    const d = await api('/api/price');
    if (d.error) return;
    document.getElementById('priceNum').textContent = d.price.toFixed(2);
    const chg = document.getElementById('priceChg');
    const sign = d.change >= 0 ? '+' : '';
    chg.textContent = `${sign}${d.change.toFixed(2)} (${sign}${d.change_pct.toFixed(2)}%)`;
    chg.className = 'chg mono ' + (d.change >= 0 ? 'up' : 'down');
    document.getElementById('priceNum').className = 'num mono ' + (d.change >= 0 ? 'up' : 'down');
  } catch {}
}
setInterval(loadPrice, 30000);
loadPrice();

// ---------- Session status ----------
let sessionState = { phase1_valid: null, phase2_valid: null };
function renderPhase(id, val) {
  const e = document.getElementById(id);
  if (val === true) { e.textContent = 'VALID'; e.className = 'badge green'; }
  else if (val === false) { e.textContent = 'FILTERED'; e.className = 'badge red'; }
  else { e.textContent = '—'; e.className = 'badge amber'; }
  e.style.marginTop = '14px'; e.style.fontSize = '14px'; e.style.padding = '8px 16px';
}
function togglePhase(key, id) {
  document.getElementById(id).addEventListener('click', () => {
    const cur = sessionState[key];
    sessionState[key] = cur === null ? true : cur === true ? false : null;
    renderPhase(id, sessionState[key]);
  });
}
togglePhase('phase1_valid', 'phase1Badge');
togglePhase('phase2_valid', 'phase2Badge');
renderPhase('phase1Badge', null);
renderPhase('phase2Badge', null);

document.getElementById('saveSession').addEventListener('click', async () => {
  const adx = parseFloat(document.getElementById('adxVal').textContent) || null;
  const atr = parseFloat(document.getElementById('atrVal').textContent) || null;
  await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phase1_valid: sessionState.phase1_valid,
      phase2_valid: sessionState.phase2_valid,
      adx_value: adx,
      atr_pct: atr,
    }),
  });
  playComplete();
});

function colorMetrics() {
  const adx = parseFloat(document.getElementById('adxVal').textContent);
  const atr = parseFloat(document.getElementById('atrVal').textContent);
  document.getElementById('adxVal').style.color = isNaN(adx) ? '' : (adx > 15 ? 'var(--green)' : 'var(--red)');
  document.getElementById('atrVal').style.color = isNaN(atr) ? '' : (atr >= 0.3 && atr <= 2.0 ? 'var(--green)' : 'var(--red)');
}
document.getElementById('adxVal').addEventListener('input', colorMetrics);
document.getElementById('atrVal').addEventListener('input', colorMetrics);

// ---------- Trades ----------
async function loadTrades() {
  const rows = await api('/api/trades');
  const tbody = document.getElementById('tradesBody');
  clear(tbody);
  rows.forEach(t => {
    const tr = document.createElement('tr');
    const pnl = t.pnl_dollars;
    tr.className = pnl == null ? '' : (pnl > 0 ? 'win' : 'loss');
    const cells = [
      { text: t.date || '', cls: 'num-cell' },
      { text: t.strategy || '' },
      { text: t.direction || '' },
      { text: t.entry_price ?? '', cls: 'num-cell' },
      { text: t.exit_price ?? '', cls: 'num-cell' },
      { text: t.exit_reason || '' },
      { text: pnl == null ? '' : '$' + pnl.toFixed(2), cls: 'num-cell' },
    ];
    cells.forEach(c => tr.appendChild(el('td', { class: c.cls || '', text: String(c.text) })));

    const actionTd = el('td');
    const del = el('button', {
      text: 'Del',
      style: { color: 'var(--red)', borderColor: 'var(--red)', padding: '2px 8px' },
      onClick: () => deleteTrade(t.id),
    });
    actionTd.appendChild(del);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });
}

function deleteTrade(id) {
  showConfirm(
    'Delete Trade',
    'Remove this trade from the log? This cannot be undone.',
    async () => {
      await fetch(`/api/trades/${id}`, { method: 'DELETE' });
      loadTrades();
      loadSummary();
    }
  );
}

document.getElementById('clearAllTrades').addEventListener('click', () => {
  showConfirm(
    'Clear All Trades',
    'Delete every trade in the log? This cannot be undone.',
    async () => {
      await fetch('/api/trades/all', { method: 'DELETE' });
      loadTrades();
      loadSummary();
    }
  );
});

// Manual trade entry removed — trades now arrive via /api/alert webhook.

// Refresh trades list periodically so new auto-captured trades show up.
setInterval(() => { loadTrades(); loadSummary(); }, 15000);

// ---------- Summary + equity curve ----------
async function loadSummary() {
  const s = await api('/api/summary');
  const setTxt = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  setTxt('mTrades', s.total_trades);
  setTxt('mWR', s.win_rate + '%');
  setTxt('mPnl', '$' + s.total_pnl.toFixed(2));
  setTxt('mPF', s.profit_factor ?? '—');
  setTxt('mTradesOv', s.total_trades);
  setTxt('mWROv', s.win_rate + '%');
  setTxt('mPnlOv', '$' + s.total_pnl.toFixed(2));
  setTxt('mPFOv', s.profit_factor ?? '—');

  const svg = document.getElementById('equitySvg');
  clear(svg);
  const pts = s.equity_curve;
  if (!pts.length) return;
  const w = svg.clientWidth || 400, h = 140;
  const vals = pts.map(p => p.equity);
  const min = Math.min(0, ...vals), max = Math.max(0, ...vals);
  const span = (max - min) || 1;
  const d = pts.map((p, i) => {
    const x = (i / Math.max(1, pts.length - 1)) * (w - 10) + 5;
    const y = h - 5 - ((p.equity - min) / span) * (h - 10);
    return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
  const final = vals[vals.length - 1];
  const color = final >= 0 ? '#00d084' : '#ff4560';
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', d);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', color);
  path.setAttribute('stroke-width', '2');
  svg.appendChild(path);
}
setInterval(loadSummary, 60000);

// ---------- Tasks ----------
let knownPendingIds = new Set();
let firstTaskLoad = true;
async function loadTasks() {
  const rows = await api('/api/tasks');
  const pending = rows.filter(t => t.status === 'pending');
  document.getElementById('pendCount').textContent = pending.length;

  const newPendingIds = new Set(pending.map(t => t.id));
  if (!firstTaskLoad) {
    for (const id of newPendingIds) {
      if (!knownPendingIds.has(id)) {
        playChime();
        const toast = document.getElementById('toast');
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 4000);
        break;
      }
    }
  }
  knownPendingIds = newPendingIds;
  firstTaskLoad = false;

  const tbody = document.getElementById('tasksBody');
  clear(tbody);
  rows.forEach(t => {
    const tr = document.createElement('tr');
    let badgeCls = 'badge amber pulse', label = 'PENDING';
    if (t.status === 'in_progress') { badgeCls = 'badge blue'; label = 'IN PROGRESS'; }
    else if (t.status === 'complete') { badgeCls = 'badge green'; label = 'COMPLETE'; }

    tr.appendChild(el('td', { text: t.priority || '' }));
    tr.appendChild(el('td', { text: t.title || '' }));
    const statusTd = el('td');
    statusTd.appendChild(el('span', { class: badgeCls, text: label }));
    tr.appendChild(statusTd);
    tr.appendChild(el('td', { class: 'num-cell', text: (t.created_at || '').slice(0, 16) }));

    const actionsTd = el('td');
    if (t.status === 'pending') {
      actionsTd.appendChild(el('button', { text: 'Start', onClick: () => startTask(t.id) }));
      actionsTd.appendChild(el('button', { class: 'primary', text: 'Complete', onClick: () => completeTask(t.id) }));
    } else if (t.status === 'in_progress') {
      actionsTd.appendChild(el('button', { class: 'primary', text: 'Complete', onClick: () => completeTask(t.id) }));
    }
    tr.appendChild(actionsTd);
    tbody.appendChild(tr);
  });
}
async function startTask(id) {
  await fetch(`/api/tasks/${id}/start`, { method: 'POST' });
  loadTasks();
}
async function completeTask(id) {
  const result = prompt('Result summary?') || '';
  await fetch(`/api/tasks/${id}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ result }),
  });
  playComplete();
  loadTasks();
}
setInterval(loadTasks, 10000);


// ---------- Calendar + News (brief tab + overview strip) ----------
function renderCalendarInto(container, events, emptyText) {
  clear(container);
  if (!events || !events.length) {
    container.appendChild(el('div', {
      class: 'good',
      text: emptyText || 'No high-impact events today ✓',
    }));
    return;
  }
  events.forEach(e => {
    const row = el('div', { class: 'cal-ev' });
    row.appendChild(el('div', { class: 'dot high' }));
    row.appendChild(el('div', { class: 'time', text: e.time || '—' }));
    const body = el('div', { class: 'body' });
    body.appendChild(el('div', { class: 'name', text: e.event || '' }));
    const stats = `Forecast: ${e.forecast || '—'}  |  Previous: ${e.previous || '—'}`;
    body.appendChild(el('div', { class: 'stats', text: stats }));
    row.appendChild(body);
    container.appendChild(row);
  });
}

async function loadCalendar() {
  try {
    const d = await api('/api/calendar');
    const events = (d && d.events) || [];

    const briefBox = document.getElementById('calendarEvents');
    if (briefBox) renderCalendarInto(briefBox, events);

    const strip = document.getElementById('calendar');
    if (strip) {
      clear(strip);
      if (!events.length) {
        strip.appendChild(el('div', { text: 'No high-impact events scheduled today', style: { color: 'var(--muted)' } }));
      } else {
        events.forEach(e => {
          const box = el('div', { class: 'cal-event' });
          box.appendChild(el('span', { class: 'badge blue mono', text: e.time || '' }));
          box.appendChild(el('span', { text: e.event || '' }));
          box.appendChild(el('span', { class: 'badge red', text: e.impact || '' }));
          box.appendChild(el('span', { class: 'mono', text: `${e.forecast || ''} / ${e.previous || ''}` }));
          strip.appendChild(box);
        });
      }
    }
  } catch (err) {
    const briefBox = document.getElementById('calendarEvents');
    if (briefBox) { clear(briefBox); briefBox.appendChild(el('div', { text: 'Error loading calendar', style: { color: 'var(--red)' } })); }
  }
}

async function loadNews() {
  const box = document.getElementById('newsHeadlines');
  if (!box) return;
  try {
    const d = await api('/api/news');
    const items = (d && d.headlines) || [];
    clear(box);
    if (!items.length) {
      box.appendChild(el('div', { text: 'No headlines available', style: { color: 'var(--muted)' } }));
      return;
    }
    items.forEach(h => {
      const a = document.createElement('a');
      a.className = 'news-item';
      a.href = h.url || '#';
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = h.headline;
      const src = el('span', { class: 'src', text: h.source || '' });
      a.appendChild(src);
      box.appendChild(a);
    });
  } catch {
    clear(box);
    box.appendChild(el('div', { text: 'Error loading news', style: { color: 'var(--red)' } }));
  }
}
setInterval(() => { loadCalendar(); loadNews(); }, 300000);

// ---------- Tabs ----------
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab-panel').forEach(p => {
      p.classList.toggle('active', p.id === 'panel-' + target);
    });
    if (target === 'brief') { loadMorningBrief(); loadCalendar(); loadNews(); }
  });
});

// ---------- Morning brief ----------
function pad(s, n) { s = String(s ?? ''); return s + ' '.repeat(Math.max(0, n - s.length)); }
function fmtNum(v, d = 2) { return (v == null || isNaN(v)) ? '—' : Number(v).toFixed(d); }
function mark(ok) { return ok ? '✓' : '✗'; }

function renderBrief(b) {
  if (!b || b.status === 'no_data') {
    return 'No session data yet.\n\nRun /morning-brief from a Claude session with TradingView MCP\navailable to populate this view.';
  }
  const date = b.date || '—';
  const open = fmtNum(b.mes_open);
  const prior = fmtNum(b.prior_day_close);
  const gap = b.gap_pct;
  const gapStr = gap == null ? '—' : `${gap >= 0 ? '+' : ''}${gap.toFixed(2)}%`;
  const adx = fmtNum(b.adx_value);
  const atr = fmtNum(b.atr_pct);

  const p1 = b.phase1 || {};
  const p2 = b.phase2 || {};

  const lines = [];
  lines.push(`MORNING BRIEF — ${date}`);
  lines.push('━'.repeat(44));
  lines.push('');
  lines.push(`MES1!  Open: ${open}    Prior Close: ${prior}`);
  lines.push(`Gap:   ${gapStr}`);
  lines.push('');
  lines.push('REGIME FILTERS');
  lines.push(`  ADX (14):  ${pad(adx, 8)} P1(≥15) ${mark(p1.adx_ok)}   P2(<20) ${mark(p2.adx_ok)}`);
  lines.push(`  ATR%(10):  ${pad(atr + '%', 8)} both(0.3-2.0) ${mark(p1.atr_ok)}`);
  lines.push('');
  lines.push('PHASE 1 — MES ORB');
  lines.push(`  Status: ${p1.valid ? 'WATCHING ✓' : 'BLOCKED ✗'}`);
  lines.push('');
  lines.push('PHASE 2 — GAP FADE');
  lines.push(`  Status: ${p2.valid ? 'WATCHING ✓' : 'BLOCKED ✗'}`);
  lines.push(`  Gap in 0.32-0.55% band: ${mark(p2.gap_ok)}`);
  if (b.notes) { lines.push(''); lines.push('NOTES'); lines.push('  ' + b.notes); }
  lines.push('');
  lines.push('━'.repeat(44));
  lines.push(`Last updated: ${b.updated_at || '—'}`);
  return lines.join('\n');
}

async function loadMorningBrief() {
  const pre = document.getElementById('briefText');
  if (!pre) return;
  try {
    const b = await api('/api/morning-brief');
    pre.textContent = renderBrief(b);
  } catch (e) {
    pre.textContent = 'Error loading brief: ' + e;
  }
}
document.getElementById('refreshBrief')?.addEventListener('click', loadMorningBrief);

// ---------- Init ----------
loadTrades();
loadSummary();
loadTasks();
loadCalendar();
loadNews();
loadMorningBrief();
