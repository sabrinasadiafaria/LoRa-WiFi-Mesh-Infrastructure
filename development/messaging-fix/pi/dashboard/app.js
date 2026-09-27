/* ===================================================================
   SAR Command Centre Dashboard — Client Engine (app.js)
   =================================================================== */

const LORA_MAX_TEXT = 100;
const DEFAULT_CENTER = [23.7979, 90.4497];

// Leaflet Map Initialization
const map = L.map('map', { zoomControl: true, attributionControl: true, scrollWheelZoom: false })
              .setView(DEFAULT_CENTER, 13);

L.tileLayer('/tiles/{z}/{x}/{y}.png', {
  maxZoom: 16, minZoom: 11,
  attribution: 'OSM (cached)', errorTileUrl: ''
}).addTo(map);

let gotoPin = null;
map.on('click', e => {
  const { lat, lng } = e.latlng;
  if (gotoPin) { map.removeLayer(gotoPin); gotoPin = null; }
  gotoPin = L.marker([lat, lng], {
    icon: L.divIcon({
      className: 'goto-pin',
      iconSize: [18, 18], iconAnchor: [9, 9],
      html: '<div style="background:#ff7a1a;width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 10px #ff7a1a;"></div>'
    })
  }).addTo(map);
  
  // Prefill goto inputs in Rover console
  const latStr = lat.toFixed(6);
  const lonStr = lng.toFixed(6);
  const fullLatInput = document.getElementById('full-goto-lat');
  const fullLonInput = document.getElementById('full-goto-lon');
  if (fullLatInput) fullLatInput.value = latStr;
  if (fullLonInput) fullLonInput.value = lonStr;
  showToast(`Pin dropped: ${latStr}, ${lonStr}`, 'info');
});

const markers = {};   // id -> L.marker
const trails  = {};   // id -> L.polyline
const sosRing = {};   // id -> L.circle
let   firstFix = true;
let   activeSosData = null;

// ---- Helpers ----
function nodeColour(id) {
  return { A: '#38bdf8', B: '#fbbf24', C: '#a855f7', PI: '#4ade80', R: '#2dd4bf', PHONE: '#f43f5e' }[id] || '#cbd5e1';
}
function icon(id) {
  return L.divIcon({
    className: '',
    html: `<div style="background:${nodeColour(id)};width:26px;height:26px;border-radius:50%;
           border:2px solid #fff;display:flex;align-items:center;justify-content:center;
           font:800 11px -apple-system,system-ui;color:#000;box-shadow:0 4px 10px rgba(0,0,0,0.5)">${id}</div>`,
    iconSize: [26, 26], iconAnchor: [13, 13]
  });
}
function placeNode(id, lat, lon, meta) {
  if (lat == null || lon == null || (lat === 0 && lon === 0)) return;
  const ll = [lat, lon];
  if (markers[id]) markers[id].setLatLng(ll);
  else markers[id] = L.marker(ll, { icon: icon(id) }).addTo(map);
  markers[id].bindPopup(`<b>Node ${id}</b><br>${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}` +
                        (meta ? `<br><small>${meta}</small>` : ''));
}
function setTrail(id, pts) {
  if (!pts || pts.length < 2) return;
  if (trails[id]) trails[id].setLatLngs(pts);
  else trails[id] = L.polyline(pts, { color: nodeColour(id), weight: 3, opacity: 0.6 }).addTo(map);
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
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => { t.remove(); }, 3500);
}

// Clock tick
setInterval(() => {
  const el = document.getElementById('clock');
  if (el) el.textContent = clockFmt();
}, 1000);

function setLink(ok) {
  const el = document.getElementById('link');
  const txt = document.getElementById('linktxt');
  if (txt) txt.textContent = ok ? 'live' : 'offline';
  if (el) el.className = 'pill ' + (ok ? 'live' : 'off');
}

// ===================================================================
// NAVIGATION TABS SWITCHER
// ===================================================================
const navTabs = document.querySelectorAll('.nav-tab');
const viewPanels = document.querySelectorAll('.view-panel');

navTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const targetView = tab.getAttribute('data-view');
    navTabs.forEach(t => t.classList.remove('active'));
    viewPanels.forEach(p => p.classList.remove('active'));
    
    tab.classList.add('active');
    const activePanel = document.getElementById(`view-${targetView}`);
    if (activePanel) activePanel.classList.add('active');
    
    // Invalidate map size on view switch to ensure Leaflet renders correctly
    if (targetView === 'overview') {
      setTimeout(() => map.invalidateSize(), 100);
    }
  });
});

// Map Recenter Button
document.getElementById('btn-recenter-map')?.addEventListener('click', () => {
  const posList = Object.values(lastState?.positions || {});
  if (posList.length) {
    const p = posList[0];
    map.setView([p.lat, p.lon], 15);
    showToast('Map centered on active nodes', 'info');
  } else {
    map.setView(DEFAULT_CENTER, 13);
  }
});

// Map Rover Drawer Toggle
const mapRoverDrawer = document.getElementById('map-rover-drawer');
document.getElementById('btn-toggle-map-rover')?.addEventListener('click', () => {
  mapRoverDrawer?.classList.toggle('hidden');
});
document.getElementById('btn-close-map-rover')?.addEventListener('click', () => {
  mapRoverDrawer?.classList.add('hidden');
});

// ===================================================================
// SOS ALERT BANNER ACTIONS
// ===================================================================
const btnSosLocate = document.getElementById('btn-sos-locate');
const btnSosClear  = document.getElementById('btn-sos-clear');

btnSosLocate?.addEventListener('click', () => {
  if (activeSosData && activeSosData.lat && activeSosData.lon) {
    map.setView([activeSosData.lat, activeSosData.lon], 16);
    showToast(`Focused on SOS Victim ${activeSosData.victim}`, 'info');
  } else {
    showToast('No GPS coordinates available for SOS victim', 'error');
  }
});

btnSosClear?.addEventListener('click', () => {
  const victim = activeSosData ? activeSosData.victim : '*';
  fetch('/api/clear_sos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ victim })
  })
  .then(r => r.json())
  .then(j => {
    if (j.ok) {
      showToast(`SOS Alert Cleared for ${victim}`, 'success');
      document.getElementById('sosbar')?.classList.add('hidden');
      refresh();
    }
  })
  .catch(() => showToast('Failed to clear SOS alert', 'error'));
});

// ===================================================================
// MESSAGES PANEL & WORKSPACE
// ===================================================================
const msgInput  = document.getElementById('msg-text');
const msgDest   = document.getElementById('msg-dest');
const msgSend   = document.getElementById('msg-send');
const msgCount  = document.getElementById('msg-charcount');
const msgChunk  = document.getElementById('msg-chunkinfo');
const msgConv   = document.getElementById('msg-conversation');

const fullMsgInput = document.getElementById('full-msg-text');
const fullMsgSend  = document.getElementById('full-msg-send');
const fullMsgCount = document.getElementById('full-msg-charcount');
const fullMsgChunk = document.getElementById('full-msg-chunkinfo');
const fullMsgConv  = document.getElementById('full-msg-conversation');

let selectedTarget = '*';

// Input Budget Counters
function updateMsgBudget(inputEl, countEl, chunkEl) {
  if (!inputEl || !countEl) return;
  const len = inputEl.value.length;
  countEl.textContent = String(len);
  if (len > LORA_MAX_TEXT * 5) {
    countEl.className = 'bad';
  } else if (len > LORA_MAX_TEXT) {
    countEl.className = 'warn';
  } else {
    countEl.className = '';
  }
  const chunks = len <= LORA_MAX_TEXT ? 1 : Math.ceil(len / LORA_MAX_TEXT);
  if (chunkEl) {
    if (chunks > 1) {
      chunkEl.textContent = `${chunks} packets`;
      chunkEl.classList.add('visible');
    } else {
      chunkEl.classList.remove('visible');
      chunkEl.textContent = '';
    }
  }
}

msgInput?.addEventListener('input', () => updateMsgBudget(msgInput, msgCount, msgChunk));
fullMsgInput?.addEventListener('input', () => updateMsgBudget(fullMsgInput, fullMsgCount, fullMsgChunk));

// Send Handler
function sendMessage(dest, text, sendBtn, inputEl) {
  if (!text || !text.trim()) return;
  sendBtn.disabled = true;
  sendBtn.textContent = '…';
  fetch('/api/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest, text })
  })
  .then(r => r.json())
  .then(j => {
    if (j.ok) {
      inputEl.value = '';
      inputEl.dispatchEvent(new Event('input'));
      showToast(`Sent message to ${dest} (${j.chunks || 1} chunk)`, 'success');
      refresh();
    } else {
      showToast(j.error || 'Failed to send message', 'error');
    }
  })
  .catch(() => showToast('Network error sending message', 'error'))
  .finally(() => {
    sendBtn.disabled = false;
    sendBtn.textContent = sendBtn.id === 'full-msg-send' ? 'Send Message' : 'Send';
  });
}

msgSend?.addEventListener('click', () => sendMessage(msgDest.value, msgInput.value, msgSend, msgInput));
fullMsgSend?.addEventListener('click', () => sendMessage(selectedTarget, fullMsgInput.value, fullMsgSend, fullMsgInput));

msgInput?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); msgSend.click(); } });
fullMsgInput?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); fullMsgSend.click(); } });

// Workspace Recipient Selector
const recipientItems = document.querySelectorAll('.recipient-item');
recipientItems.forEach(item => {
  item.addEventListener('click', () => {
    recipientItems.forEach(i => i.classList.remove('active'));
    item.classList.add('active');
    selectedTarget = item.getAttribute('data-dest');
    document.getElementById('full-target-name').textContent = item.querySelector('.name').textContent;
    refresh();
  });
});

// Quick Presets
document.querySelectorAll('.btn-preset').forEach(btn => {
  btn.addEventListener('click', () => {
    const presetText = btn.getAttribute('data-text');
    if (fullMsgInput) {
      fullMsgInput.value = presetText;
      fullMsgInput.dispatchEvent(new Event('input'));
      fullMsgInput.focus();
    }
  });
});

// Render Conversations
function renderMessages(messages) {
  const badge = document.getElementById('msg-badge');
  const fullBadge = document.getElementById('full-msg-badge');
  if (badge) badge.textContent = `${messages.length} msgs`;
  if (fullBadge) fullBadge.textContent = `${messages.length} msgs`;

  const sorted = [...messages].reverse();
  const renderBubbleHTML = m => {
    const dir = m.direction === 'out' ? 'out' : 'in';
    const who = m.direction === 'out' ? `PI → ${m.dest}` : `${m.src} → PI`;
    const t = new Date(m.ts * 1000).toLocaleTimeString([], { hour12: false });
    return `
      <div class="msg-bubble ${dir}">
        <div class="msg-who">${escHtml(who)}</div>
        <div class="msg-text">${escHtml(m.text)}</div>
        <div class="msg-time">${t}</div>
      </div>`;
  };

  const html = sorted.length
    ? sorted.map(renderBubbleHTML).join('')
    : '<div class="msg-empty">No messages recorded</div>';

  if (msgConv) { msgConv.innerHTML = html; msgConv.scrollTop = msgConv.scrollHeight; }
  
  // Workspace Filtered Messages
  if (fullMsgConv) {
    const filtered = selectedTarget === '*'
      ? sorted
      : sorted.filter(m => m.dest === selectedTarget || m.src === selectedTarget);
    const fullHtml = filtered.length
      ? filtered.map(renderBubbleHTML).join('')
      : `<div class="msg-empty">No messages for target ${selectedTarget}</div>`;
    fullMsgConv.innerHTML = fullHtml;
    fullMsgConv.scrollTop = fullMsgConv.scrollHeight;
  }
}

// ===================================================================
// ROVER CONTROLS
// ===================================================================
let roverHoldTimer = null;

function roverSendVerb(verb) {
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb })
  })
  .then(r => r.json())
  .then(j => {
    if (!j.ok) showToast(j.error || 'Rover command error', 'error');
  })
  .catch(() => {});
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

function bindDpad(selector) {
  document.querySelectorAll(selector).forEach(btn => {
    const verb = btn.getAttribute('data-verb');
    const start = e => { e.preventDefault(); btn.classList.add('active'); roverStartHold(verb); };
    const stop  = e => { e.preventDefault(); btn.classList.remove('active'); roverStopHold(verb); };
    
    btn.addEventListener('mousedown', start);
    btn.addEventListener('mouseup', stop);
    btn.addEventListener('mouseleave', stop);
    btn.addEventListener('touchstart', start, { passive: false });
    btn.addEventListener('touchend', stop, { passive: false });
  });
}

bindDpad('.dbtn');
bindDpad('.dbtn-full');

// Rover Mode Switching
function bindRoverMode(selector) {
  document.querySelectorAll(selector).forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');
      fetch('/api/command', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dest: 'R', verb: 'MODE', arg: mode })
      })
      .then(r => r.json())
      .then(j => {
        if (j.ok) {
          showToast(`Rover mode set to ${mode}`, 'success');
          refresh();
        } else {
          showToast(j.error || 'Failed to set mode', 'error');
        }
      });
    });
  });
}

bindRoverMode('.mbtn');
bindRoverMode('.btn-mode');

// Rover GOTO Waypoint
document.getElementById('full-goto-go')?.addEventListener('click', () => {
  const lat = document.getElementById('full-goto-lat').value.trim();
  const lon = document.getElementById('full-goto-lon').value.trim();
  if (!lat || !lon) { showToast('Latitude and Longitude required', 'error'); return; }
  
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb: 'GOTO', arg: `${lat},${lon}` })
  })
  .then(r => r.json())
  .then(j => {
    if (j.ok) {
      showToast(`Rover dispatched to ${lat}, ${lon}`, 'success');
      document.getElementById('full-goto-status').textContent = `Target set: ${lat}, ${lon}`;
    } else {
      showToast(j.error || 'GOTO target error', 'error');
    }
  });
});

document.getElementById('full-goto-clr')?.addEventListener('click', () => {
  fetch('/api/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: 'R', verb: 'GOCLR', arg: '' })
  })
  .then(r => r.json())
  .then(j => {
    if (j.ok) {
      showToast('Rover target cancelled', 'info');
      document.getElementById('full-goto-status').textContent = 'Target status: idle';
    }
  });
});

function renderRover(roverList, now) {
  const r = (roverList || []).find(x => x.id === 'R');
  const badge = document.getElementById('rover-status-badge');
  const mRoverStatus = document.getElementById('m-rover-status');
  const mRoverBatt   = document.getElementById('m-rover-batt');

  if (!r) {
    if (badge) { badge.textContent = 'Rover Offline'; badge.className = 'badge bad'; }
    if (mRoverStatus) mRoverStatus.textContent = 'OFFLINE';
    return;
  }

  const ageS = now - r.ts;
  const isOnline = ageS < 120;
  if (badge) {
    badge.textContent = isOnline ? `ONLINE (${r.mode})` : 'Rover Lost';
    badge.className = isOnline ? 'badge ok' : 'badge bad';
  }
  if (mRoverStatus) mRoverStatus.textContent = r.mode || 'MANUAL';
  if (mRoverBatt) mRoverBatt.textContent = `${r.battery_pct}%`;

  // Update Full Console
  const valMode = document.getElementById('r-val-mode');
  const valBatt = document.getElementById('r-val-batt');
  const valObs  = document.getElementById('r-val-obs');
  const valAge  = document.getElementById('r-val-age');

  if (valMode) valMode.textContent = r.mode || 'MANUAL';
  if (valBatt) valBatt.textContent = `${r.battery_pct}%`;
  if (valObs)  valObs.textContent  = `${r.obstacle_cm} cm`;
  if (valAge)  valAge.textContent  = `${fmtAge(ageS)} ago`;
}

// ===================================================================
// LOGS WORKSPACE & FILTERS
// ===================================================================
let currentLogFilter = 'all';
let currentSearchQuery = '';

document.querySelectorAll('.log-filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.log-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentLogFilter = btn.getAttribute('data-filter');
    renderLogs();
  });
});

document.getElementById('logs-search')?.addEventListener('input', e => {
  currentSearchQuery = e.target.value.toLowerCase().trim();
  renderLogs();
});

document.getElementById('btn-export-logs')?.addEventListener('click', () => {
  if (!lastState) return;
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(lastState, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `sar_mission_logs_${Math.floor(Date.now()/1000)}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  showToast('Exported JSON mission logs', 'success');
});

function renderLogs() {
  if (!lastState) return;
  const feed = document.getElementById('feed');
  const logsFeed = document.getElementById('logs-feed');

  const events = [];
  (lastState.sos || []).forEach(s => events.push({
    ts: s.ts, kind: 'sos', who: s.victim || 'unknown',
    what: (s.msg || 'MAYDAY') + (s.cleared ? ' (cleared)' : ''),
  }));
  (lastState.reports || []).forEach(r => events.push({
    ts: r.ts, kind: 'report', who: r.id || 'unknown',
    what: `${r.code}${r.team ? ' - ' + r.team : ''}${r.lat && r.lon ? ' @ ' + r.lat.toFixed(4) + ',' + r.lon.toFixed(4) : ''}`,
  }));
  (lastState.messages || []).forEach(m => events.push({
    ts: m.ts, kind: 'msg', who: m.direction === 'out' ? `${m.src} → ${m.dest}` : `${m.src} → PI`,
    what: m.text,
  }));
  
  events.sort((a, b) => b.ts - a.ts);

  // Recent Activity Feed
  document.getElementById('act-badge').textContent = `${events.length} events`;
  if (feed) {
    feed.innerHTML = events.length
      ? events.slice(0, 50).map(e => `
        <div class="feed-row ${e.kind}">
          <span class="t">${new Date(e.ts * 1000).toLocaleTimeString([], { hour12: false })}</span>
          <span class="ic">${e.kind.toUpperCase()}</span>
          <div class="body">
            <div class="who">${escHtml(e.who)}</div>
            <div class="what">${escHtml(e.what)}</div>
          </div>
        </div>`).join('')
      : '<div class="feed-row empty">No events recorded</div>';
  }

  // Full Activity Logs Workspace
  if (logsFeed) {
    let filtered = events;
    if (currentLogFilter !== 'all') {
      filtered = filtered.filter(e => e.kind === currentLogFilter);
    }
    if (currentSearchQuery) {
      filtered = filtered.filter(e =>
        e.who.toLowerCase().includes(currentSearchQuery) ||
        e.what.toLowerCase().includes(currentSearchQuery)
      );
    }

    logsFeed.innerHTML = filtered.length
      ? filtered.map(e => `
        <div class="feed-row ${e.kind}">
          <span class="t">${new Date(e.ts * 1000).toLocaleTimeString([], { hour12: false })}</span>
          <span class="ic">${e.kind.toUpperCase()}</span>
          <div class="body">
            <div class="who">${escHtml(e.who)}</div>
            <div class="what">${escHtml(e.what)}</div>
          </div>
        </div>`).join('')
      : '<div class="feed-row empty">No matching log entries</div>';
  }
}

// ===================================================================
// MAIN REFRESH & SSE STREAM
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

  // Top Status Bar
  const totalNodes = st.nodes.length;
  const upNodes = st.nodes.filter(n => n.online).length;
  document.getElementById('topbar-mesh').textContent = `${upNodes} / ${totalNodes} active`;
  const activeSosList = (st.sos || []).filter(s => !s.cleared);
  document.getElementById('topbar-sos').textContent = String(activeSosList.length);
  document.getElementById('topbar-lastupdate').textContent = new Date(now * 1000).toLocaleTimeString([], { hour12: false });

  // Map Markers
  const posList = Object.values(st.positions || {});
  posList.forEach(p => {
    const srcName = { 1: 'GPS', 2: 'phone' }[p.src] || '?';
    placeNode(p.id, p.lat, p.lon, `${srcName}, ${fmtAge(now - p.ts)} ago`);
  });
  Object.entries(st.trails || {}).forEach(([id, pts]) => setTrail(id, pts));
  document.getElementById('map-badge').textContent = `${Object.keys(markers).length} markers`;

  if (firstFix && posList.length) {
    firstFix = false;
    map.setView([posList[0].lat, posList[0].lon], 15);
  }

  // Active SOS Banner
  const sosBar = document.getElementById('sosbar');
  if (activeSosList.length) {
    activeSosData = activeSosList[0];
    sosBar.classList.remove('hidden');
    document.getElementById('sosvictim').textContent = activeSosData.victim || '--';
    document.getElementById('sosmsg').textContent = activeSosData.msg || 'MAYDAY';
    document.getElementById('soscoord').textContent = activeSosData.lat && activeSosData.lon
      ? `${activeSosData.lat.toFixed(5)}, ${activeSosData.lon.toFixed(5)}`
      : 'No position';
  } else {
    activeSosData = null;
    sosBar.classList.add('hidden');
  }

  // Telemetry Cards
  const telList = document.getElementById('tel-list');
  const sortedNodes = [...st.nodes].sort((a, b) => a.id.localeCompare(b.id));
  document.getElementById('tel-badge').textContent = `${sortedNodes.length} nodes`;

  if (sortedNodes.length === 0) {
    telList.innerHTML = '<div class="feed-row empty">No nodes reporting</div>';
  } else {
    telList.innerHTML = sortedNodes.map(n => {
      const r = routes[n.id];
      const route = n.id === 'PI' ? 'self' : (r && r.valid ? `via ${r.via} (${r.hops}h)` : '<span class="bad">no route</span>');
      const pos = st.positions[n.id];
      const loc = pos ? `${pos.lat.toFixed(4)}, ${pos.lon.toFixed(4)}` : '<span class="dim">no fix</span>';
      const age = fmtAge(now - n.last_seen);
      const nodeSos = activeSosList.find(s => s.victim === n.id);
      return `
        <div class="tel-card ${!n.online ? 'offline' : ''} ${nodeSos ? 'sos' : ''}">
          <div class="badge-id" style="background:${nodeColour(n.id)}">${n.id}</div>
          <div class="body">
            <div class="title">
              <span>${escHtml(n.id)}</span>
              <span class="${n.online ? 'ok' : 'bad'}" style="font-size:11px">${n.online ? 'ONLINE' : 'LOST'}</span>
            </div>
            <div class="meta">
              <span>RSSI ${n.rssi != null ? `<span class="signal-bars s${signalBars(n.rssi)}"><i></i><i></i><i></i><i></i></span> ${n.rssi}` : '--'}</span>
              <span class="dim">${route}</span>
              <span class="dim">${loc}</span>
            </div>
          </div>
          <div class="right">
            <div class="age">${age} ago</div>
          </div>
        </div>`;
    }).join('');
  }

  renderMessages(st.messages || []);
  renderRover(st.rover || [], now);
  renderLogs();
}

// Initial refresh & periodic interval
refresh();
setInterval(refresh, 5000);

// SSE Live Event Stream
const es = new EventSource('/api/events');
es.onmessage = e => {
  try {
    const ev = JSON.parse(e.data);
    if (ev.kind === 'sos') {
      showToast(`🚨 SOS MAYDAY from ${ev.data.victim || 'node'}!`, 'error');
    } else if (ev.kind === 'message') {
      showToast(`💬 New message from ${ev.data.src}`, 'info');
    }
    refresh();
  } catch (err) {}
};
