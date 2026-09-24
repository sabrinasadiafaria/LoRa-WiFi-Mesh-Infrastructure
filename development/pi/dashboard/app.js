/* SAR Command Centre dashboard - with Messages panel.
   Layout:
      +----------------------------------------------------+
      |  TOP STATUS BAR                                    |
      +----------------------------+-----------------------+
      |  NODES MAP                 |  LIVE TELEMETRY       |
      |  (Leaflet, dark)           |  (per-node cards)     |
      +----------------------------+-----------------------+
      |  RECENT ACTIVITY           |  MESSAGES             |
      |  (chronological feed)      |  (conversation + compose) |
      +----------------------------+-----------------------+

   Plus a floating rover panel that appears once a rover has reported in.

   The data sources are the JSON API + SSE stream the Pi exposes
   (/api/state, /api/messages, /api/events).                          */

const LORA_MAX_TEXT = 100;
const DHAKA = [23.7979, 90.4497];
const map = L.map('map', { zoomControl: true, attributionControl: true })
              .setView(DHAKA, 13);

// offline tiles from the Pi's cache; falls back to the grey grid if absent
L.tileLayer('/tiles/{z}/{x}/{y}.png', {
  maxZoom: 16, minZoom: 11,
  attribution: 'OSM (cached)', errorTileUrl: ''
}).addTo(map);

// Tap on the map to drop a GOTO pin (operator still has to press Go).
let gotoPin = null;
map.on('click', e => {
  const { lat, lng } = e.latlng;
  if (gotoPin) { map.removeLayer(gotoPin); gotoPin = null; }
  gotoPin = L.marker([lat, lng], {
    icon: L.divIcon({
      className: 'goto-pin',
      iconSize: [18, 18], iconAnchor: [9, 9],
      html: '<div class="goto-pin-dot"></div>'
    })
  }).addTo(map);
  if (typeof window.__roverGotoPrefill === 'function') {
    window.__roverGotoPrefill(lat, lng);
  }
});

const markers = {};   // id -> L.marker
const trails  = {};   // id -> L.polyline
const sosRing = {};   // id -> L.circle
let   firstFix = true;

// ---- helpers --------------------------------------------------------
function nodeColour(id) {
  return { A: '#4da3ff', B: '#ffb040', C: '#a06cff', PI: '#5fd08a', R: '#20c5c5' }[id] || '#ccc';
}
function icon(id) {
  return L.divIcon({
    className: '',
    html: `<div style="background:${nodeColour(id)};width:24px;height:24px;border-radius:50%;
           border:2px solid #fff;display:flex;align-items:center;justify-content:center;
           font:700 11px -apple-system,system-ui;color:#000">${id}</div>`,
    iconSize: [24, 24], iconAnchor: [12, 12]
  });
}
function placeNode(id, lat, lon, meta) {
  if (lat == null || lon == null || (lat === 0 && lon === 0)) return;
  const ll = [lat, lon];
  if (markers[id]) markers[id].setLatLng(ll);
  else markers[id] = L.marker(ll, { icon: icon(id) }).addTo(map);
  markers[id].bindPopup(`<b>${id}</b><br>${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}` +
                        (meta ? `<br>${meta}` : ''));
}
function setTrail(id, pts) {
  if (!pts || pts.length < 2) return;
  if (trails[id]) trails[id].setLatLngs(pts);
  else trails[id] = L.polyline(pts, { color: nodeColour(id), weight: 2, opacity: .5 }).addTo(map);
}
function fmtAge(s) {
  if (s == null) return '--';
  if (s < 60) return Math.round(s) + 's';
  if (s < 3600) return Math.round(s / 60) + 'm';
  return Math.round(s / 3600) + 'h';
}
function signalBars(rssi) {
  if (rssi == null) return 0;
  if (rssi >= -85)  return 4;
  if (rssi >= -100) return 3;
  if (rssi >= -110) return 2;
  return 1;
}
function escHtml(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function clockFmt() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour12: false });
}
const tickClock = () => document.getElementById('clock').textContent = clockFmt();
setInterval(tickClock, 1000); tickClock();

function setLink(ok) {
  const el = document.getElementById('link');
  const txt = document.getElementById('linktxt');
  txt.textContent = ok ? 'live' : 'offline';
  el.className = 'pill ' + (ok ? 'live' : 'off');
}

// ===================================================================
// MESSAGES PANEL
// ===================================================================
const msgInput  = document.getElementById('msg-text');
const msgDest   = document.getElementById('msg-dest');
const msgSend   = document.getElementById('msg-send');
const msgCount  = document.getElementById('msg-charcount');
const msgChunk  = document.getElementById('msg-chunkinfo');
const msgConv   = document.getElementById('msg-conversation');

// character counter
msgInput.addEventListener('input', () => {
  const len = msgInput.value.length;
  msgCount.textContent = String(len);
  if (len > LORA_MAX_TEXT * 5) {
    msgCount.className = 'bad';
  } else if (len > LORA_MAX_TEXT) {
    msgCount.className = 'warn';
  } else {
    msgCount.className = '';
  }
  const chunks = len <= LORA_MAX_TEXT ? 1 : Math.ceil(len / LORA_MAX_TEXT);
  if (chunks > 1) {
    msgChunk.textContent = `${chunks} packets`;
    msgChunk.classList.add('visible');
  } else {
    msgChunk.classList.remove('visible');
  }
});

// send message
function sendMessage() {
  const text = msgInput.value.trim();
  const dest = msgDest.value;
  if (!text) return;
  msgSend.disabled = true;
  msgSend.textContent = '…';
  fetch('/api/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest, text })
  })
  .then(r => r.json())
  .then(j => {
    if (j.ok) {
      msgInput.value = '';
      msgInput.dispatchEvent(new Event('input'));
      // SSE will trigger a refresh to show the new message
    }
  })
  .catch(() => {})
  .finally(() => {
    msgSend.disabled = false;
    msgSend.textContent = 'Send';
  });
}
msgSend.addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// render message bubbles
function renderMessages(messages) {
  const badge = document.getElementById('msg-badge');
  badge.textContent = `${messages.length} message${messages.length === 1 ? '' : 's'}`;

  if (!messages.length) {
    msgConv.innerHTML = '<div class="msg-empty">No messages yet — send one below</div>';
    return;
  }

  // messages come newest-first from the API; reverse for chronological display
  const sorted = [...messages].reverse();
  const wasAtBottom = msgConv.scrollTop + msgConv.clientHeight >= msgConv.scrollHeight - 30;

  msgConv.innerHTML = sorted.map(m => {
    const dir = m.direction === 'out' ? 'out' : 'in';
    const who = m.direction === 'out'
      ? `PI → ${m.dest}`
      : `${m.src} → PI`;
    const t = new Date(m.ts * 1000).toLocaleTimeString([], { hour12: false });
    return `
      <div class="msg-bubble ${dir}">
        <div class="msg-who">${escHtml(who)}</div>
        <div class="msg-text">${escHtml(m.text)}</div>
        <div class="msg-time">${t}</div>
      </div>`;
  }).join('');

  // auto-scroll to bottom if the user was already at the bottom
  if (wasAtBottom) {
    msgConv.scrollTop = msgConv.scrollHeight;
  }
}


// ===================================================================
// MAIN REFRESH
// ===================================================================
let lastState = null;

async function refresh() {
  let st;
  try {
    st = await (await fetch('/api/state', { cache: 'no-store' })).json();
  } catch (e) { setLink(false); return; }
  setLink(true);
  lastState = st;

  const routes = (st.mesh && st.mesh.routes) || {};
  const now = st.now || (Date.now() / 1000);

  // ---- top status bar ----
  const totalNodes = st.nodes.length;
  const upNodes = st.nodes.filter(n => n.online).length;
  document.getElementById('topbar-mesh').textContent = `${upNodes} / ${totalNodes} active`;
  document.getElementById('topbar-mesh').style.color =
    upNodes === totalNodes && totalNodes > 0 ? 'var(--ok)' :
    upNodes === 0 ? 'var(--bad)' : 'var(--warn)';
  const activeSos = (st.sos || []).filter(s => !s.cleared).length;
  document.getElementById('topbar-sos').textContent = String(activeSos);
  document.getElementById('topbar-lastupdate').textContent =
    new Date(now * 1000).toLocaleTimeString([], { hour12: false });

  // ---- nodes (positions + trails + map badges) ----
  const posList = Object.values(st.positions || {});
  posList.forEach(p => {
    const srcName = { 1: 'GPS', 2: 'phone' }[p.src] || '?';
    placeNode(p.id, p.lat, p.lon,
              `${srcName}, ${fmtAge(now - p.ts)} ago, ${p.sats || 0} sats`);
  });
  Object.entries(st.trails || {}).forEach(([id, pts]) => setTrail(id, pts));
  document.getElementById('map-badge').textContent = `${Object.keys(markers).length} markers`;

  // re-centre on first position fix
  if (firstFix && posList.length) {
    firstFix = false;
    const p = posList[0];
    map.setView([p.lat, p.lon], 15);
  }

  // ---- SOS top banner ----
  const active = (st.sos || []).filter(s => !s.cleared);
  const bar = document.getElementById('sosbar');
  if (active.length) {
    const s = active[0];
    bar.classList.remove('hidden');
    document.getElementById('sosvictim').textContent = s.victim || '--';
    document.getElementById('sosmsg').textContent = s.msg || 'MAYDAY';
    document.getElementById('soscoord').textContent =
      s.lat && s.lon ? `${s.lat.toFixed(5)}, ${s.lon.toFixed(5)}` : 'no position';
    bar.onclick = () => { if (s.lat && s.lon) map.setView([s.lat, s.lon], 16); };
    if (s.lat && s.lon) {
      if (sosRing[s.victim]) sosRing[s.victim].setLatLng([s.lat, s.lon]);
      else sosRing[s.victim] = L.circle([s.lat, s.lon],
        { radius: 40, color: '#ff2b2b', fillColor: '#ff2b2b', fillOpacity: .3 }).addTo(map);
    }
  } else {
    bar.classList.add('hidden');
    Object.values(sosRing).forEach(c => map.removeLayer(c));
    for (const k in sosRing) delete sosRing[k];
  }

  // ---- live telemetry panel ----
  const telList = document.getElementById('tel-list');
  const sortedNodes = [...st.nodes].sort((a, b) => a.id.localeCompare(b.id));
  document.getElementById('tel-badge').textContent = `${sortedNodes.length} nodes`;

  if (sortedNodes.length === 0) {
    telList.innerHTML = '<div class="feed-row empty">no nodes reporting yet</div>';
  } else {
    telList.innerHTML = sortedNodes.map(n => {
      const r = routes[n.id];
      const route = n.id === 'PI' ? 'self'
                  : r && r.valid ? `via ${r.via} (${r.hops}h)`
                  : '<span class="bad">no route</span>';
      const pos = st.positions[n.id];
      const loc = pos ? `${pos.lat.toFixed(4)}, ${pos.lon.toFixed(4)}` : '<span class="dim">no fix</span>';
      const age = fmtAge(now - n.last_seen);
      const rssi = n.rssi;
      const batt = (st.rover || []).find(r => r.id === n.id);
      const battPct = batt ? batt.battery_pct : null;
      const battHtml = battPct != null && battPct >= 0
        ? `<div class="batt"><div class="batt-bar"><i class="${battPct < 25 ? 'warn' : ''} ${battPct < 15 ? 'bad' : ''}"
              style="width:${battPct}%"></i></div>${battPct}%</div>`
        : '<div class="batt dim">--</div>';
      const sigHtml = rssi != null
        ? `<span class="signal-bars s${signalBars(rssi)}"><i></i><i></i><i></i><i></i></span> ${rssi}`
        : '<span class="dim">--</span>';
      const nodeSos = active.find(s => s.victim === n.id);
      const cls = ['tel-card', !n.online && 'offline', nodeSos && 'sos'].filter(Boolean).join(' ');
      return `
        <div class="${cls}">
          <div class="badge-id" style="background:${nodeColour(n.id)}">${n.id}</div>
          <div class="body">
            <div class="title">
              <span>${escHtml(n.id)}</span>
              <span class="${n.online ? 'ok' : 'bad'}" style="font-size:11px;font-weight:600">
                ${n.online ? 'online' : 'LOST'}
              </span>
            </div>
            <div class="meta">
              <span>RSSI ${sigHtml}</span>
              <span class="dim">${route}</span>
              <span class="dim">${loc}</span>
            </div>
          </div>
          <div class="right">
            <div class="age">${age} ago</div>
            ${battHtml}
          </div>
        </div>`;
    }).join('');
  }

  // ---- recent activity panel ----
  const feed = document.getElementById('feed');
  const events = [];
  (st.sos || []).forEach(s => events.push({
    ts: s.ts, kind: 'sos',
    who: s.victim || 'unknown',
    what: (s.msg || 'MAYDAY') + (s.cleared ? ' (cleared)' : ''),
  }));
  (st.reports || []).forEach(r => events.push({
    ts: r.ts, kind: 'report',
    who: r.id || 'unknown',
    what: `${r.code}${r.team ? ' - ' + r.team : ''}${
      r.lat && r.lon ? ' @ ' + r.lat.toFixed(4) + ',' + r.lon.toFixed(4) : ''}`,
  }));
  (st.messages || []).forEach(m => events.push({
    ts: m.ts, kind: 'msg',
    who: m.direction === 'out' ? `${m.src} → ${m.dest}` : `${m.src} → PI`,
    what: m.text,
  }));
  events.sort((a, b) => b.ts - a.ts);

  document.getElementById('act-badge').textContent =
    events.length ? `${events.length} event${events.length === 1 ? '' : 's'}` : 'no events';

  if (events.length === 0) {
    feed.innerHTML = '<div class="feed-row empty">no activity yet</div>';
  } else {
    feed.innerHTML = events.slice(0, 50).map(e => {
      const t = new Date(e.ts * 1000).toLocaleTimeString([], { hour12: false });
      const ic = { sos: 'SOS', report: 'RPT', msg: 'MSG' }[e.kind] || '.';
      return `
        <div class="feed-row ${e.kind}">
          <span class="t">${t}</span>
          <span class="ic">${ic}</span>
          <div class="body">
            <div class="who">${escHtml(e.who)}</div>
            <div class="what">${escHtml(e.what)}</div>
          </div>
        </div>`;
    }).join('');
  }

  // ---- messages panel ----
  renderMessages(st.messages || []);

  // ---- rover floating panel ----
  renderRover(st.rover || [], now);
}

// ===================================================================
// ROVER PANEL
// ===================================================================
let roverHoldTimer = null;
let lastRoverMode = null;

function roverSendVerb(verb) {
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb })
  }).catch(() => {});
}
function roverStartHold(verb) {
  if (verb === 'STOP') { roverSendVerb('STOP'); return; }
  roverSendVerb(verb);
  clearInterval(roverHoldTimer);
  roverHoldTimer = setInterval(() => roverSendVerb(verb), 400);
}
function roverStopHold(verb) {
  clearInterval(roverHoldTimer);
  roverHoldTimer = null;
  if (verb !== 'STOP') roverSendVerb('STOP');
}
function roverSetMode(mode) {
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb: 'MODE', arg: mode })
  }).catch(() => {});
}

function renderRover(roverList, now) {
  const fab = document.getElementById('rover-fab');
  if (!roverList.length) {
    fab.classList.remove('visible');
    return;
  }
  fab.classList.add('visible');
  const r = roverList[0];
  const pillsEl = document.getElementById('rover-pills');
  const warn = r.obstacle_cm >= 0 && r.obstacle_cm < 25;
  const range = r.obstacle_cm >= 0 ? `${r.obstacle_cm} cm` : 'clear';
  const batt = r.battery_pct >= 0 ? `${r.battery_pct}%` : 'n/a';
  let gotoPill = '';
  if (r.dist_m != null && r.dist_m >= 0) {
    const he = r.heading_err;
    const arrow = (he == null || he <= -999)
      ? '?'
      : (Math.abs(he) < 30 ? '\u25B2' : (he > 0 ? '\u25B7' : '\u25C1'));
    gotoPill = `<span class="pill ok">${arrow} ${r.dist_m} m</span>`;
  } else if (r.mode === 'AUTO_GPS') {
    gotoPill = `<span class="pill warn">acquiring GPS</span>`;
  }
  pillsEl.innerHTML =
    `<span class="pill">id R</span>` +
    `<span class="pill ${warn ? 'warn' : 'ok'}">range ${range}</span>` +
    `<span class="pill">battery ${batt}</span>` +
    `<span class="pill">seen ${fmtAge(now - r.ts)} ago</span>` +
    gotoPill;

  if (r.mode !== lastRoverMode) {
    lastRoverMode = r.mode;
    document.querySelectorAll('#rover-fab .mode button').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === r.mode);
    });
    if (r.mode !== 'AUTO_GPS') {
      const st = document.getElementById('goto-status');
      if (st) st.textContent = 'no active target';
    }
  }
}

// wire the d-pad once
document.querySelectorAll('#rover-fab .dpad button').forEach(btn => {
  const verb = btn.dataset.verb;
  btn.addEventListener('mousedown', () => roverStartHold(verb));
  btn.addEventListener('touchstart', e => { e.preventDefault(); roverStartHold(verb); });
  ['mouseup', 'mouseleave', 'touchend', 'touchcancel'].forEach(ev =>
    btn.addEventListener(ev, () => roverStopHold(verb)));
});
// wire the mode buttons
document.querySelectorAll('#rover-fab .mode button').forEach(btn => {
  btn.addEventListener('click', () => roverSetMode(btn.dataset.mode));
});

// ===================================================================
// GOTO
// ===================================================================
function sendRoverGoto(rawLat, rawLon) {
  const st = document.getElementById('goto-status');
  const la = parseFloat(rawLat);
  const lo = parseFloat(rawLon);
  if (!isFinite(la) || !isFinite(lo) ||
      la < -90 || la > 90 || lo < -180 || lo > 180) {
    if (st) st.textContent = 'invalid coords (lat -90..90, lon -180..180)';
    return;
  }
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb: 'GOTO', arg: `${la},${lo}` })
  }).then(r => r.json()).then(j => {
    if (j.ok) {
      if (st) st.textContent = `en route to ${la.toFixed(6)}, ${lo.toFixed(6)}`;
    } else {
      if (st) st.textContent = `error: ${j.error || 'unknown'}`;
    }
  }).catch(err => {
    if (st) st.textContent = `network error: ${err}`;
  });
}

document.getElementById('goto-go').addEventListener('click', () => {
  sendRoverGoto(document.getElementById('goto-lat').value,
                document.getElementById('goto-lon').value);
});
document.getElementById('goto-clr').addEventListener('click', () => {
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb: 'GOCLR' })
  }).then(r => r.json()).then(j => {
    const st = document.getElementById('goto-status');
    if (st) st.textContent = j.ok ? 'target cancelled' : `error: ${j.error || 'unknown'}`;
  }).catch(err => {
    const st = document.getElementById('goto-status');
    if (st) st.textContent = `network error: ${err}`;
  });
});
['goto-lat', 'goto-lon'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendRoverGoto(document.getElementById('goto-lat').value,
                    document.getElementById('goto-lon').value);
    }
  });
});
window.__roverGotoPrefill = (lat, lng) => {
  document.getElementById('goto-lat').value = lat.toFixed(6);
  document.getElementById('goto-lon').value = lng.toFixed(6);
  const st = document.getElementById('goto-status');
  if (st) st.textContent = `pinned ${lat.toFixed(6)}, ${lng.toFixed(6)} - press Go`;
};

// ===================================================================
// SSE - debounced refresh + immediate SOS surface
// ===================================================================
function connectSSE() {
  let es;
  try {
    es = new EventSource('/api/events');
  } catch (e) { setLink(false); return; }
  es.onopen = () => setLink(true);
  es.onerror = () => setLink(false);
  es.onmessage = ev => {
    let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
    if (m.kind === 'sos') { refresh(); return; }
    // Immediate refresh for messages so the conversation feels real-time
    if (m.kind === 'message') {
      clearTimeout(connectSSE._tm);
      connectSSE._tm = setTimeout(refresh, 150);
      return;
    }
    if (['pos', 'node', 'report', 'status', 'hb',
         'command', 'rover', 'route'].includes(m.kind)) {
      clearTimeout(connectSSE._t);
      connectSSE._t = setTimeout(refresh, 300);
    }
  };
}

// ===================================================================
// boot
// ===================================================================
refresh();
connectSSE();
setInterval(refresh, 10000);     // safety net if SSE drops
