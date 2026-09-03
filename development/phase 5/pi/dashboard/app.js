/* SAR Command Centre dashboard */

const DHAKA = [23.7979, 90.4497];
const map = L.map('map').setView(DHAKA, 14);

// offline tiles from the Pi's cache; falls back to the grey grid if absent
L.tileLayer('/tiles/{z}/{x}/{y}.png', {
  maxZoom: 16, minZoom: 11,
  attribution: 'OSM (cached)', errorTileUrl: ''
}).addTo(map);

const markers = {};   // id -> L.marker
const trails  = {};   // id -> L.polyline
const sosRing = {};   // id -> L.circle

function nodeColour(id) {
  return { A: '#4da3ff', B: '#ffb040', C: '#a06cff', PI: '#5fd08a' }[id] || '#ccc';
}

function icon(id) {
  return L.divIcon({
    className: '',
    html: `<div style="background:${nodeColour(id)};width:22px;height:22px;border-radius:50%;
           border:2px solid #fff;display:flex;align-items:center;justify-content:center;
           font:700 11px system-ui;color:#000">${id}</div>`,
    iconSize: [22, 22], iconAnchor: [11, 11]
  });
}

function placeNode(id, lat, lon, meta) {
  if (!lat && !lon) return;
  const ll = [lat, lon];
  if (markers[id]) markers[id].setLatLng(ll);
  else markers[id] = L.marker(ll, { icon: icon(id) }).addTo(map);
  markers[id].bindPopup(`<b>${id}</b><br>${lat.toFixed(6)}, ${lon.toFixed(6)}` +
                        (meta ? `<br>${meta}` : ''));
}

function setTrail(id, pts) {
  if (!pts || pts.length < 2) return;
  if (trails[id]) trails[id].setLatLngs(pts);
  else trails[id] = L.polyline(pts, { color: nodeColour(id), weight: 2, opacity: .5 }).addTo(map);
}

function fmtAge(s) {
  if (s == null) return '-';
  if (s < 60) return Math.round(s) + 's';
  if (s < 3600) return Math.round(s / 60) + 'm';
  return Math.round(s / 3600) + 'h';
}
const clock = () => document.getElementById('clock').textContent =
  new Date().toLocaleTimeString();
setInterval(clock, 1000); clock();

/* ---- full refresh -------------------------------------------------------- */
async function refresh() {
  let st;
  try { st = await (await fetch('/api/state')).json(); }
  catch (e) { setLink(false); return; }
  setLink(true);

  const routes = st.mesh.routes || {};
  const now = st.now;

  // nodes table
  const tb = document.querySelector('#nodes tbody');
  tb.innerHTML = '';
  st.nodes.sort((a, b) => a.id.localeCompare(b.id)).forEach(n => {
    const r = routes[n.id];
    const route = n.id === 'PI' ? 'self'
      : r && r.valid ? `via ${r.via} ${r.hops}h` : '-';
    tb.insertAdjacentHTML('beforeend',
      `<tr><td>${n.id}</td>
       <td class="${n.online ? 'on' : 'off'}">${n.online ? 'online' : 'LOST'}</td>
       <td>${n.rssi ?? '-'}</td><td>${route}</td>
       <td>${fmtAge(now - n.last_seen)}</td></tr>`);
  });

  // positions + trails
  Object.values(st.positions).forEach(p => {
    const srcName = { 1: 'GPS', 2: 'phone' }[p.src] || '?';
    placeNode(p.id, p.lat, p.lon, `${srcName}, ${fmtAge(now - p.ts)} ago`);
  });
  Object.entries(st.trails).forEach(([id, pts]) => setTrail(id, pts));

  // team status
  const stb = document.querySelector('#status tbody');
  stb.innerHTML = st.status.map(s =>
    `<tr><td>${s.id}</td><td>${s.team}</td><td>${s.state}</td></tr>`).join('')
    || '<tr><td colspan=3 style="color:#666">none yet</td></tr>';

  // reports
  document.getElementById('reports').innerHTML = st.reports.map(r =>
    `<li><span class="t">${new Date(r.ts * 1000).toLocaleTimeString()}</span>
     ${r.id} &middot; <b>${r.code}</b> ${r.team ? '(' + r.team + ')' : ''}</li>`).join('')
    || '<li style="color:#666">none</li>';

  // messages
  document.getElementById('messages').innerHTML = st.messages.map(m =>
    `<li><span class="t">${new Date(m.ts * 1000).toLocaleTimeString()}</span>
     ${m.direction === 'out' ? 'PI &rarr; ' + m.dest : m.src + ' &rarr; PI'}: ${escapeHtml(m.text)}</li>`).join('')
    || '<li style="color:#666">none</li>';

  // active SOS
  const active = st.sos.filter(s => !s.cleared);
  const bar = document.getElementById('sosbar');
  if (active.length) {
    const s = active[0];
    bar.classList.remove('hidden');
    bar.textContent = `SOS  ${s.victim}  @ ${s.lat.toFixed(5)}, ${s.lon.toFixed(5)}  -  ${s.msg}`;
    bar.onclick = () => { if (s.lat) map.setView([s.lat, s.lon], 16); };
    if (s.lat) {
      if (sosRing[s.victim]) sosRing[s.victim].setLatLng([s.lat, s.lon]);
      else sosRing[s.victim] = L.circle([s.lat, s.lon],
        { radius: 40, color: '#ff2b2b', fillColor: '#ff2b2b', fillOpacity: .3 }).addTo(map);
    }
  } else {
    bar.classList.add('hidden');
    Object.values(sosRing).forEach(c => map.removeLayer(c));
    for (const k in sosRing) delete sosRing[k];
  }
}

function setLink(ok) {
  const el = document.getElementById('link');
  el.textContent = ok ? 'live' : 'offline';
  el.className = 'pill ' + (ok ? 'ok' : 'bad');
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* ---- live events: refresh on any, plus instant SOS ---------------------- */
function connectSSE() {
  const es = new EventSource('/api/events');
  es.onopen = () => setLink(true);
  es.onerror = () => setLink(false);
  es.onmessage = ev => {
    let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
    if (m.kind === 'sos') refresh();          // surface immediately
    else if (['pos', 'node', 'report', 'status', 'message', 'hb', 'command'].includes(m.kind)) {
      clearTimeout(connectSSE._t);
      connectSSE._t = setTimeout(refresh, 300);   // debounce bursts
    }
  };
}

/* ---- outbound ---------------------------------------------------------- */
async function sendMsg() {
  const dest = document.getElementById('dest').value;
  const text = document.getElementById('msg').value.trim();
  if (!text) return;
  const r = await fetch('/api/send', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest, text })
  });
  document.getElementById('sendmsg').textContent =
    r.ok ? 'sent' : 'failed';
  if (r.ok) document.getElementById('msg').value = '';
}
async function cmd(verb) {
  const dest = document.getElementById('cdest').value;
  const r = await fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest, verb })
  });
  document.getElementById('sendmsg').textContent =
    r.ok ? `${verb} sent to ${dest}` : 'command failed';
}

refresh();
connectSSE();
setInterval(refresh, 10000);      // safety net if SSE drops
