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
      { text: '' },
    ];
    cells.forEach(c => tr.appendChild(el('td', { class: c.cls || '', text: String(c.text) })));
    tbody.appendChild(tr);
  });
}

// Manual trade entry removed — trades now arrive via /api/alert webhook.

// Refresh trades list periodically so new auto-captured trades show up.
setInterval(() => { loadTrades(); loadSummary(); }, 15000);

// ---------- Summary + equity curve ----------
async function loadSummary() {
  const s = await api('/api/summary');
  document.getElementById('mTrades').textContent = s.total_trades;
  document.getElementById('mWR').textContent = s.win_rate + '%';
  document.getElementById('mPnl').textContent = '$' + s.total_pnl.toFixed(2);
  document.getElementById('mPF').textContent = s.profit_factor ?? '—';

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

document.getElementById('taskHead').addEventListener('click', () => {
  document.getElementById('taskBody').classList.toggle('hidden');
});

// ---------- Calendar ----------
async function loadCalendar() {
  try {
    const evs = await api('/api/calendar');
    const container = document.getElementById('calendar');
    clear(container);
    if (!evs.length) {
      container.appendChild(el('div', { text: 'No high-impact events scheduled today', style: { color: 'var(--muted)' } }));
      return;
    }
    evs.forEach(e => {
      const box = el('div', { class: 'cal-event' });
      box.appendChild(el('span', { class: 'badge blue mono', text: e.time_ct || '' }));
      box.appendChild(el('span', { text: e.name || '' }));
      box.appendChild(el('span', { class: 'badge red', text: e.impact || '' }));
      box.appendChild(el('span', { class: 'mono', text: `${e.forecast || ''} / ${e.previous || ''}` }));
      container.appendChild(box);
    });
  } catch {}
}
setInterval(loadCalendar, 300000);

// ---------- Init ----------
loadTrades();
loadSummary();
loadTasks();
loadCalendar();
