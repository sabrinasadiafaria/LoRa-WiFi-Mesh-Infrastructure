/* SAR Command Centre dashboard - redesigned layout.
   Layout (matches the attached design image):

      +----------------------------------------------------+
      |  TOP STATUS BAR                                    |
      +----------------------------+-----------------------+
      |  NODES MAP                 |  LIVE TELEMETRY       |
      |  (Leaflet, dark)           |  (per-node cards)     |
      +----------------------------+-----------------------+
      |  RECENT ACTIVITY           |  TEAM STATUS          |
      |  (chronological feed)      |  (per-team cards)     |
      +----------------------------+-----------------------+

   Plus a floating rover panel that appears once a rover has reported in.

   The data sources are the unchanged JSON API + SSE stream the Pi already
   exposes (/api/state and /api/events). The state shape is documented at
   the top of refresh() below.                                       */

const DHAKA = [23.7979, 90.4497];
const map = L.map('map', { zoomControl: true, attributionControl: true })
              .setView(DHAKA, 13);

// offline tiles from the Pi's cache; falls back to the grey grid if absent
L.tileLayer('/tiles/{z}/{x}/{y}.png', {
  maxZoom: 16, minZoom: 11,
  attribution: 'OSM (cached)', errorTileUrl: ''
}).addTo(map);

// Tap on the map to drop a GOTO pin (operator still has to press Go).
// A previous pin is cleared so only one pin is visible at a time.
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
// MAIN REFRESH
//
// /api/state shape:
//   now       : float
//   nodes     : [{id, last_seen, rssi, snr, uptime, heap, online}]
//   positions : { id -> {id,lat,lon,src,sats,ts} }
//   trails    : { id -> [[lat,lon], ...] }      last 30 minutes
//   sos       : [{ts,victim,lat,lon,msg,cleared}]   last 20
//   messages  : [{ts,src,dest,text,direction}]    last 40
//   reports   : [{ts,id,code,lat,lon,team}]       last 30
//   status    : [{id,team,state,ts}]
//   rover     : [{id,mode,obstacle_cm,battery_pct,ts}]
//   mesh      : {neighbors:{...}, routes:{...}}
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

  // re-centre on first position fix so the operator actually sees something
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
      const batt = (st.rover || []).find(r => r.id === n.id);     // rover carries battery
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

  // ---- recent activity panel (chronological merge of reports + messages + SOS) ----
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
    who: m.direction === 'out' ? `${m.src} -> ${m.dest}` : `${m.src} -> PI`,
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

  // ---- team status panel ----
  const teamList = document.getElementById('team-list');
  const teamArr = (st.status || []).slice().sort((a, b) => a.id.localeCompare(b.id));
  document.getElementById('team-badge').textContent =
    `${teamArr.length} member${teamArr.length === 1 ? '' : 's'}`;
  if (teamArr.length === 0) {
    teamList.innerHTML = '<div class="feed-row empty">no team members yet</div>';
  } else {
    teamList.innerHTML = teamArr.map(t => {
      const initials = (t.id || '??').slice(0, 2).toUpperCase();
      const state = (t.state || 'UNKNOWN').toUpperCase();
      const stateCls = ['AVAILABLE','SEARCHING','NEED_ASSIST','EMERGENCY','VICTIM_FOUND']
                       .includes(state) ? state : 'UNKNOWN';
      const age = fmtAge(now - t.ts);
      return `
        <div class="team-card">
          <div class="avatar">${escHtml(initials)}</div>
          <div class="body">
            <div class="name">${escHtml(t.id)}</div>
            <div class="role">Team ${escHtml(t.team || '?')}</div>
          </div>
          <div class="right">
            <span class="status-chip ${stateCls}">${escHtml(state)}</span>
            <span class="age">${age} ago</span>
          </div>
        </div>`;
    }).join('');
  }

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
  // GOTO target progress. dist_m == -1 means "no target" (rover not in
  // AUTO_GPS, or just arrived, or GOCLR). heading_err == -999 means "no
  // GPS fix yet so we can't compute it". Both are sentinels the rover
  // sends so the dashboard can tell "we don't know" from "perfect aim".
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

  // update mode-button highlight if it changed
  if (r.mode !== lastRoverMode) {
    lastRoverMode = r.mode;
    document.querySelectorAll('#rover-fab .mode button').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === r.mode);
    });
    // If the rover just dropped AUTO_GPS (arrived, GOCLR'd, or fell back
    // to RELAY), reset the GO inputs so the operator doesn't think the
    // stale numbers are still live.
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
// GOTO  -  send the rover to a target GPS coordinate.
//   * type lat/lon into the inputs and press Go
//   * or click on the map - it copies the clicked coords into the
//     inputs and previews them so the operator can hit Go
//   * "Cancel current target" sends GOCLR which makes the rover drop
//     the route and sit as a RELAY node at wherever it happens to be
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
// Enter key on either input -> Go
['goto-lat', 'goto-lon'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendRoverGoto(document.getElementById('goto-lat').value,
                    document.getElementById('goto-lon').value);
    }
  });
});
// Map click -> drop a pin and prefill the inputs. The map is set up further
// down in the file; this event hook attaches to it on first user click by
// registering a one-shot listener bound to the same Leaflet map variable.
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
    if (['pos', 'node', 'report', 'status', 'message', 'hb',
         'command', 'rover', 'route'].includes(m.kind)) {
      clearTimeout(connectSSE._t);
      connectSSE._t = setTimeout(refresh, 300);    // debounce bursts
    }
  };
}

// ===================================================================
// boot
// ===================================================================
refresh();
connectSSE();
setInterval(refresh, 10000);     // safety net if SSE drops
