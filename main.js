// ============================================================
// RCLA Project Map — main.js
// Phase 1: Layout + Data loading + Map + Maintainer Mode
// ============================================================

const BACKEND_URL = 'http://127.0.0.1:8000';

// --- Inject app CSS ---
const style = document.createElement('style');
style.textContent = `
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: Arial, sans-serif;
    font-size: 14px;
    color: #333;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* ---- Maintainer Mode Toolbar ---- */
  #maintainer-panel {
    background: #0f172a;
    color: #f8fafc;
    padding: 6px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    z-index: 1000;
    border-bottom: 2px solid #3b82f6;
    flex-shrink: 0;
  }
  .maint-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  #sync-status-badge {
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 10px;
    text-transform: uppercase;
    background: #475569;
    color: #fff;
  }
  .maint-btn {
    color: #fff;
    border: none;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
    font-size: 11px;
    transition: opacity 0.15s;
  }
  .maint-btn:hover { opacity: 0.9; }
  .btn-dry  { background: #3b82f6; }
  .btn-sync { background: #059669; }
  .btn-push { background: #d97706; }
  .btn-log  { background: #334155; }

  /* ---- Maintainer Log Drawer ---- */
  #log-drawer {
    display: none;
    background: #020617;
    color: #38bdf8;
    font-family: Consolas, Menlo, Monaco, "Courier New", monospace;
    font-size: 11px;
    padding: 8px 16px;
    height: 120px;
    overflow-y: auto;
    border-bottom: 1px solid #1e293b;
    flex-shrink: 0;
  }
  .log-line { margin-bottom: 2px; }

  /* ---- Top nav ---- */
  #nav {
    background: #1a3a5c;
    color: white;
    display: flex;
    align-items: center;
    padding: 0 16px;
    height: 48px;
    flex-shrink: 0;
    gap: 8px;
  }
  #nav .club-name {
    font-size: 15px;
    font-weight: bold;
    margin-right: auto;
  }
  #nav button {
    background: transparent;
    border: 1px solid rgba(255,255,255,0.4);
    color: white;
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: background 0.15s;
  }
  #nav button:hover    { background: rgba(255,255,255,0.15); }
  #nav button.active   { background: rgba(255,255,255,0.25); border-color: white; }

  /* ---- Two-pane body ---- */
  #app {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* ---- Left pane: map ---- */
  #map-pane {
    flex: 0 0 55%;
    position: relative;
    min-width: 200px;
  }
  #map {
    width: 100%;
    height: 100%;
  }

  /* ---- Divider ---- */
  #divider {
    width: 6px;
    background: #ddd;
    cursor: col-resize;
    flex-shrink: 0;
    position: relative;
    transition: background 0.15s;
  }
  #divider:hover, #divider.dragging { background: #1a3a5c; }
  #divider::after {
    content: '⋮';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: #999;
    font-size: 14px;
    pointer-events: none;
  }
  #divider:hover::after, #divider.dragging::after { color: white; }

  /* ---- Right pane ---- */
  #right-pane {
    flex: 1;
    overflow-y: auto;
    background: #f7f7f7;
    display: flex;
    flex-direction: column;
    min-width: 200px;
  }

  /* ---- Shared panel styles ---- */
  .panel { padding: 20px; flex: 1; }

  .panel h2 {
    font-size: 17px;
    color: #1a3a5c;
    margin-bottom: 12px;
    border-bottom: 2px solid #1a3a5c;
    padding-bottom: 6px;
  }

  .panel h3 {
    font-size: 14px;
    color: #1a3a5c;
    margin: 16px 0 6px;
  }

  /* ---- Loading / error states ---- */
  #loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #888;
    font-size: 15px;
  }

  /* ---- STATUS BADGE ---- */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .badge-closed   { background: #ffe0b2; color: #e65100; }
  .badge-approved { background: #c8e6c9; color: #1b5e20; }
  .badge-proposed { background: #bbdefb; color: #0d47a1; }

  /* ---- PROJECT DETAIL ---- */
  #detail-panel .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 16px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 12px;
  }
  #detail-panel .meta-item label {
    display: block;
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
  }
  #detail-panel .meta-item span {
    font-size: 13px;
    color: #222;
    font-weight: 500;
  }

  #detail-panel .narrative {
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 12px;
    line-height: 1.6;
    color: #444;
    margin-bottom: 12px;
  }
  #detail-panel .narrative h2,
  #detail-panel .narrative h3 {
    color: #1a3a5c;
    margin: 14px 0 6px;
    font-size: 14px;
    border: none;
  }
  #detail-panel .narrative p  { margin-bottom: 8px; }
  #detail-panel .narrative ul,
  #detail-panel .narrative ol { margin: 6px 0 8px 18px; }
  #detail-panel .narrative li { margin-bottom: 3px; }
  #detail-panel .narrative table {
    border-collapse: collapse;
    width: 100%;
    font-size: 12px;
    margin: 8px 0;
  }
  #detail-panel .narrative th,
  #detail-panel .narrative td {
    border: 1px solid #ddd;
    padding: 4px 8px;
    text-align: left;
  }
  #detail-panel .narrative th { background: #f0f4f8; }
  #detail-panel .narrative hr { border: none; border-top: 1px solid #eee; margin: 10px 0; }

  #detail-panel .narrative.placeholder {
    color: #aaa;
    font-style: italic;
  }

  /* ---- FILES & LINKS ---- */
  .files-section {
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 12px;
  }
  .files-section a {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 4px;
    color: #1a3a5c;
    text-decoration: none;
    border-bottom: 1px solid #f0f0f0;
    font-size: 13px;
  }
  .files-section a:last-child { border-bottom: none; }
  .files-section a:hover { background: #f0f4f8; border-radius: 4px; }
  .file-icon { font-size: 16px; }

  /* ---- PHOTO CAROUSEL ---- */
  .photo-carousel {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    margin-bottom: 12px;
    padding-bottom: 4px;
  }
  .photo-carousel img {
    height: 140px;
    border-radius: 6px;
    cursor: pointer;
    flex-shrink: 0;
    object-fit: cover;
    border: 1px solid #ddd;
  }

  /* ---- DETAIL NAV ---- */
  .detail-nav {
    display: flex;
    justify-content: space-between;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #ddd;
  }
  .detail-nav button {
    background: #1a3a5c;
    color: white;
    border: none;
    padding: 7px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }
  .detail-nav button:hover { background: #2a5a8c; }
  .detail-nav button:disabled { background: #ccc; cursor: default; }

  /* ---- PROJECT LIST ---- */
  #list-panel .filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }
  #list-panel .filters select,
  #list-panel .filters input {
    padding: 5px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 13px;
    background: white;
  }
  #list-panel table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    overflow: hidden;
  }
  #list-panel th {
    background: #1a3a5c;
    color: white;
    text-align: left;
    padding: 8px 10px;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  #list-panel th:hover { background: #2a5a8c; }
  #list-panel td {
    padding: 7px 10px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
  }
  #list-panel tr:last-child td { border-bottom: none; }
  #list-panel tr:hover td { background: #f0f4f8; cursor: pointer; }
  #list-panel .amount { text-align: right; font-variant-numeric: tabular-nums; }
  #list-panel .no-results {
    text-align: center;
    color: #888;
    padding: 24px;
    font-style: italic;
  }

  /* ---- OVERVIEW ---- */
  #overview-panel .summary-text {
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 14px;
    line-height: 1.7;
    margin-bottom: 16px;
    color: #444;
  }
  #overview-panel .stat-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 16px;
  }
  #overview-panel .stat-card {
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 12px;
    text-align: center;
  }
  #overview-panel .stat-card .stat-value {
    font-size: 22px;
    font-weight: bold;
    color: #1a3a5c;
  }
  #overview-panel .stat-card .stat-label {
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
  }
  #overview-panel .chart-card {
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 14px;
    margin-bottom: 14px;
  }
  #overview-panel .chart-card h3 {
    margin: 0 0 10px;
    font-size: 13px;
    color: #1a3a5c;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* ---- EDIT MODAL ---- */
  #edit-modal {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6);
    z-index: 99999;
    align-items: center;
    justify-content: center;
  }
  .modal-content {
    background: #fff;
    width: 850px;
    max-width: 95vw;
    height: 85vh;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .modal-header { background: #1a3a5c; color: white; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; }
  .modal-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .editor-split { display: flex; gap: 12px; height: 220px; }
  .editor-split textarea { flex: 1; font-family: monospace; font-size: 12px; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; }
  .editor-split .preview { flex: 1; border: 1px solid #cbd5e1; border-radius: 4px; padding: 8px; overflow-y: auto; background: #f8fafc; }
  .modal-footer { padding: 12px 16px; background: #f1f5f9; display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid #e2e8f0; }
  .link-row { display: flex; gap: 8px; margin-bottom: 6px; }
`;
document.head.appendChild(style);

// --- Render Page Structure ---
document.body.innerHTML = `
  <div id="maintainer-panel">
    <div class="maint-group">
      <strong>🛠️ Maint Mode</strong>
      <span id="sync-status-badge">Connecting...</span>
      <span id="sync-step" style="color: #94a3b8;"></span>
    </div>
    <div class="maint-group">
      <button id="btn-sync-dry" class="maint-btn btn-dry" onclick="triggerSync(true)">Dry Run Sync</button>
      <button id="btn-sync-live" class="maint-btn btn-sync" onclick="triggerSync(false)">Full Sync</button>
      <button id="btn-publish" class="maint-btn btn-push" onclick="publishChanges()">Push to Git</button>
      <button class="maint-btn btn-log" onclick="toggleLogConsole()">Logs</button>
    </div>
  </div>

  <div id="log-drawer">
    <div id="log-output">-- Orchestrator log stream initialized --</div>
  </div>

  <div id="nav">
    <span class="club-name">Rotary Club of Lake Atitlán — Projects</span>
    <button id="btn-overview" class="active">Overview</button>
    <button id="btn-list">Projects</button>
  </div>
  <div id="app">
    <div id="map-pane"><div id="map"></div></div>
    <div id="divider"></div>
    <div id="right-pane">
      <div id="loading">Loading project data…</div>
    </div>
  </div>
`;

// ============================================================
// STATE
// ============================================================
let allProjects      = [];
let map              = null;
let markers          = [];
let currentView      = 'overview';
let currentIndex     = 0;
let isMaintenanceMode= false;
let listSort         = { col: 'start_year', dir: 'asc' };

// ============================================================
// MAINTAINER CLIENT (SSE & STATUS)
// ============================================================
function initMaintainerClient() {
  const evtSource = new EventSource(`${BACKEND_URL}/api/logs`);
  evtSource.onmessage = (event) => {
    const logDiv = document.getElementById('log-output');
    if (!logDiv) return;
    const newLine = document.createElement('div');
    newLine.className = 'log-line';
    newLine.textContent = event.data;
    logDiv.appendChild(newLine);
    logDiv.scrollTop = logDiv.scrollHeight;
    pollMaintStatus();
  };

  evtSource.onerror = () => {
    isMaintenanceMode = false;
    const badge = document.getElementById('sync-status-badge');
    if (badge) {
      badge.textContent = 'Offline';
      badge.style.background = '#64748b';
    }
  };

  setInterval(pollMaintStatus, 4000);
  pollMaintStatus();
}

async function pollMaintStatus() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/status`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    isMaintenanceMode = true;
    const badge = document.getElementById('sync-status-badge');
    const step = document.getElementById('sync-step');
    if (!badge) return;

    badge.textContent = `Status: ${data.status.toUpperCase()}`;
    if (data.status === 'running') {
      badge.style.background = '#d97706';
    } else if (data.status === 'error') {
      badge.style.background = '#dc2626';
    } else {
      badge.style.background = '#059669';
    }

    if (step) {
      step.textContent = data.current_step ? `— ${data.current_step}` : '';
    }
  } catch {
    isMaintenanceMode = false;
    const badge = document.getElementById('sync-status-badge');
    if (badge) {
      badge.textContent = 'Offline';
      badge.style.background = '#64748b';
    }
  }
}

window.triggerSync = async function (dryRun = true) {
  window.toggleLogConsole(true);
  try {
    const res = await fetch(`${BACKEND_URL}/api/sync?dry_run=${dryRun}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || 'Failed to start sync');
    }
    pollMaintStatus();
  } catch {
    alert('Could not connect to orchestrator.');
  }
};

window.publishChanges = async function () {
  const msg = prompt('Commit message:', 'chore(sync): automated grant sync');
  if (!msg) return;
  try {
    const res = await fetch(`${BACKEND_URL}/api/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    alert(data.message || `Published commit: ${data.commit}`);
  } catch {
    alert('Publish failed. Check orchestrator logs.');
  }
};

window.toggleLogConsole = function (forceOpen = false) {
  const drawer = document.getElementById('log-drawer');
  if (!drawer) return;
  drawer.style.display = forceOpen || drawer.style.display === 'none' ? 'block' : 'none';
};

// ============================================================
// ENTRY POINT (Explicitly on window for Google Maps callback)
// ============================================================
window.initMap = function () {
  initMaintainerClient();
  loadData()
    .then(projects => {
      allProjects = projects;
      buildMap();
      showOverview();
      wireNavButtons();
      initDivider();
    })
    .catch(err => {
      document.getElementById('loading').textContent =
        'Error loading project data: ' + err.message;
      console.error(err);
    });
};

// If Google Maps loaded prior to main.js definition, initialize immediately
if (window.google && window.google.maps) {
  window.initMap();
}

// ============================================================
// DATA LOADING
// ============================================================
function loadData() {
  return fetch('RCLA_Projects_v2.csv')
    .then(r => {
      if (!r.ok) throw new Error('Could not fetch RCLA_Projects_v2.csv');
      return r.text();
    })
    .then(csv => new Promise((resolve, reject) => {
      Papa.parse(csv, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
        complete: res => resolve(res.data),
        error:    err => reject(err),
      });
    }));
}

// ============================================================
// MAP
// ============================================================
// Handles standard separate columns AND combined "lat, lng" strings (like DG projects)
function getProjectCoords(project) {
  let latVal = project.position_lat;
  let lngVal = project.position_lng;

  if (typeof latVal === 'string' && latVal.includes(',')) {
    const parts = latVal.split(',');
    latVal = parts[0].trim();
    lngVal = parts[1].trim();
  }

  const lat = Number(latVal);
  const lng = Number(lngVal);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
}

// 48px illuminated red-and-gold star badge
const SELECTED_PIN_ICON = {
  url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" fill="#dc2626" stroke="#ffffff" stroke-width="2.5"/>
      <polygon points="12,4 14.5,9.5 20.5,10 16,14 17.5,20 12,17 6.5,20 8,14 3.5,10 9.5,9.5" fill="#facc15"/>
    </svg>
  `),
  scaledSize: new google.maps.Size(46, 46),
  anchor: new google.maps.Point(23, 23)
};

function buildMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    zoom: 10,
    center: { lat: 14.703454, lng: -91.191623 },
    mapTypeId: 'roadmap',
    tilt: 45,
    mapTypeControl: true,
    mapTypeControlOptions: {
      style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
      mapTypeIds: ['roadmap', 'satellite', 'hybrid', 'terrain'],
    },
    rotateControl: true,
    fullscreenControl: true,
  });

  markers = allProjects.map((project, idx) => {
    const coords = getProjectCoords(project);
    if (!coords) return null;

    const marker = new google.maps.Marker({
      position: coords,
      map,
      title: project.title || project.id,
      icon: `https://maps.google.com/mapfiles/ms/icons/${markerColor(project.status)}-dot.png`,
    });

    marker.addListener('click', () => showDetail(idx));
    return marker;
  });
}

// --- 1. Resilient High-Visibility Marker Selection ---
function highlightMarker(idx) {
  resetMarkers();
  const active = markers[idx];
  if (!active || typeof active.getPosition !== "function") return;

  try {
    // High-visibility target icon definition
    const pinIcon = {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" fill="#dc2626" stroke="#ffffff" stroke-width="2.5"/>
          <polygon points="12,4 14.5,9.5 20.5,10 16,14 17.5,20 12,17 6.5,20 8,14 3.5,10 9.5,9.5" fill="#facc15"/>
        </svg>
      `),
      scaledSize: (window.google && google.maps && google.maps.Size) ? new google.maps.Size(46, 46) : null,
      anchor: (window.google && google.maps && google.maps.Point) ? new google.maps.Point(23, 23) : null
    };

    active.setIcon(pinIcon);
    if (typeof active.setZIndex === "function") active.setZIndex(999999);
    if (typeof active.setAnimation === "function" && google.maps.Animation) {
      active.setAnimation(google.maps.Animation.BOUNCE);
    }

    if (map && active.getPosition()) {
      map.panTo(active.getPosition());
      if (map.getZoom() < 12) map.setZoom(12);
    }
  } catch (err) {
    console.warn("Marker highlighting encountered an issue:", err);
  }
}

function resetMarkers() {
  markers.forEach((m, i) => {
    if (!m) return;
    m.setAnimation(null);
    m.setIcon(
      `https://maps.google.com/mapfiles/ms/icons/${markerColor(allProjects[i].status)}-dot.png`
    );
    m.setZIndex(1);
  });
}


function markerColor(status) {
  switch (status) {
    case 'closed':               return 'orange';
    case 'approved':             return 'green';
    case 'proposed':             return 'blue';
    case 'approved/delinquent':  return 'yellow';
    default:                     return 'red';
  }
}

// ============================================================
// NAV WIRING
// ============================================================
function wireNavButtons() {
  document.getElementById('btn-overview').addEventListener('click', showOverview);
  document.getElementById('btn-list').addEventListener('click', showList);
}

function setActiveNav(view) {
  document.getElementById('btn-overview').classList.toggle('active', view === 'overview');
  document.getElementById('btn-list').classList.toggle('active', view === 'list');
}

// ============================================================
// VIEW: OVERVIEW
// ============================================================
function showOverview() {
  currentView = 'overview';
  setActiveNav('overview');
  if (markers.length) resetMarkers();

  const closed   = allProjects.filter(p => p.status === 'closed');
  const approved = allProjects.filter(p => p.status === 'approved');
  const proposed = allProjects.filter(p => p.status === 'proposed');
  const totalGrants = allProjects.reduce((s, p) => s + (Number(p.amount) || 0), 0);

  const rp = document.getElementById('right-pane');
  rp.innerHTML = `
    <div class="panel" id="overview-panel">
      <h2>Club Projects Overview</h2>

      <div class="summary-text">
        <p>The Rotary Club of Lake Atitlán has been funding community development projects
        around Lake Atitlán since 2015. Working alongside international partner clubs and
        local NGOs, the club has deployed over $1.2 million in Rotary Foundation Global
        Grants across health, water &amp; sanitation, education, economic development,
        and environmental initiatives.</p>
        <br>
        <p>Early projects focused on health infrastructure — medical equipment for
        Hospitalito Schafer and maternal health in Tecpán. Water and sanitation became
        a major theme through the 2018–2022 period, with multiple WASH grants serving
        indigenous communities. In recent years the portfolio has broadened to include
        education, women's economic empowerment, and watershed protection.</p>
        <br>
      </div>

      <div style="
        background: #fffbeb;
        border: 1px solid #f59e0b;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 16px;
        font-size: 12px;
        color: #78350f;
        line-height: 1.5;
      ">
        <strong>Note:</strong> Individual project summaries on this site were generated
        with the assistance of an AI language model (Claude, by Anthropic) based on
        Rotary Foundation grant documents. While we have reviewed these summaries for
        accuracy, AI-generated content may contain errors or omissions. For authoritative
        information please refer to the original grant documents linked in each project.
      </div>

      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-value">${allProjects.length}</div>
          <div class="stat-label">Total Projects</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">$${(totalGrants / 1e6).toFixed(2)}M</div>
          <div class="stat-label">Total Grant Funding</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${closed.length} / ${approved.length} / ${proposed.length}</div>
          <div class="stat-label">Closed / Active / Proposed</div>
        </div>
      </div>

      <div class="chart-card">
        <h3>Grant funding by year</h3>
        <div style="position:relative;height:200px;">
          <canvas id="chart-by-year"></canvas>
        </div>
      </div>

      <div class="chart-card">
        <h3>Portfolio by category</h3>
        <div style="position:relative;height:220px;">
          <canvas id="chart-by-cat"></canvas>
        </div>
      </div>

      <div class="chart-card">
        <h3>Cumulative funding over time</h3>
        <div style="position:relative;height:180px;">
          <canvas id="chart-cumulative"></canvas>
        </div>
      </div>
    </div>
  `;

  loadChartJS().then(buildOverviewCharts);
}

function loadChartJS() {
  return new Promise(resolve => {
    if (window.Chart) { resolve(); return; }
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';
    s.onload = resolve;
    document.head.appendChild(s);
  });
}

function buildOverviewCharts() {
  const BLUE  = '#1a3a5c';
  const COLORS = ['#1a3a5c','#2196f3','#4caf50','#ff9800','#9c27b0','#f44336'];

  const yearMap = {};
  allProjects.forEach(p => {
    const y = p.start_year;
    if (!y) return;
    yearMap[y] = (yearMap[y] || 0) + (Number(p.amount) || 0);
  });
  const years   = Object.keys(yearMap).sort();
  const amounts = years.map(y => yearMap[y]);

  new Chart(document.getElementById('chart-by-year'), {
    type: 'bar',
    data: {
      labels: years,
      datasets: [{ label: 'Grant Amount', data: amounts, backgroundColor: BLUE }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: v => '$' + (v/1000).toFixed(0) + 'k' } }
      }
    }
  });

  const catMap = {};
  allProjects.forEach(p => {
    const c = p.category || 'Unknown';
    catMap[c] = (catMap[c] || 0) + (Number(p.amount) || 0);
  });
  const cats    = Object.keys(catMap);
  const catAmts = cats.map(c => catMap[c]);

  new Chart(document.getElementById('chart-by-cat'), {
    type: 'doughnut',
    data: {
      labels: cats,
      datasets: [{ data: catAmts, backgroundColor: COLORS }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { font: { size: 11 } } }
      }
    }
  });

  const sorted = [...allProjects]
    .filter(p => p.start_year && (p.amount))
    .sort((a, b) => a.start_year - b.start_year);
  let running = 0;
  const cumLabels = [];
  const cumData   = [];
  sorted.forEach(p => {
    running += Number(p.amount) || 0;
    cumLabels.push(p.start_year);
    cumData.push(running);
  });

  new Chart(document.getElementById('chart-cumulative'), {
    type: 'line',
    data: {
      labels: cumLabels,
      datasets: [{
        label: 'Cumulative Funding',
        data: cumData,
        borderColor: BLUE,
        backgroundColor: 'rgba(26,58,92,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: v => '$' + (v/1000).toFixed(0) + 'k' } }
      }
    }
  });
}

// ============================================================
// VIEW: PROJECT LIST
// ============================================================
function showList() {
  currentView = 'list';
  setActiveNav('list');
  if (markers.length) resetMarkers();
  renderList();
}

function renderList() {
  const rp = document.getElementById('right-pane');

  const statuses    = [...new Set(allProjects.map(p => p.status))].sort();
  const categories  = [...new Set(allProjects.map(p => p.category))].sort();
  const years       = [...new Set(allProjects.map(p => p.start_year).filter(Boolean))].sort();

  rp.innerHTML = `
    <div class="panel" id="list-panel">
      <h2>All Projects</h2>
      <div class="filters">
        <select id="filter-status">
          <option value="">All statuses</option>
          ${statuses.map(s => `<option value="${s}">${capitalize(s)}</option>`).join('')}
        </select>
        <select id="filter-category">
          <option value="">All categories</option>
          ${categories.map(c => `<option value="${c}">${c}</option>`).join('')}
        </select>
        <select id="filter-year">
          <option value="">All years</option>
          ${years.map(y => `<option value="${y}">${y}</option>`).join('')}
        </select>
        <select id="filter-budget">
          <option value="">All budgets</option>
          <option value="0-50000">Under $50K</option>
          <option value="50000-100000">$50K – $100K</option>
          <option value="100000-200000">$100K – $200K</option>
          <option value="200000-99999999">Over $200K</option>
          <option value="none">No amount listed</option>
        </select>
        <input id="filter-search" type="text" placeholder="Search…" style="flex:1;min-width:120px;">
      </div>
      <table id="project-table">
        <thead>
          <tr>
            <th style="width:36px;">#</th>
            <th data-col="id" style="width:90px;">ID</th>
            <th data-col="title">Project</th>
            <th data-col="category">Category</th>
            <th data-col="start_year">Year</th>
            <th data-col="status">Status</th>
            <th data-col="amount" style="text-align:right">Budget</th>
            <th data-col="shepard">Shepherd</th>
          </tr>
        </thead>
        <tbody id="project-tbody"></tbody>
        <tfoot id="project-tfoot" style="background:#f0f4f8;font-weight:500;border-top:2px solid #1a3a5c;">
          <tr>
            <td colspan="6" style="padding:7px 10px;font-size:12px;color:#555;">Total</td>
            <td class="amount" style="padding:7px 10px;font-size:13px;" id="budget-total">—</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  `;

  wireListFilters();
  renderListRows();
}

function wireListFilters() {
  ['filter-status','filter-category','filter-year','filter-budget','filter-search'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderListRows);
  });
  document.querySelectorAll('#project-table th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (listSort.col === col) {
        listSort.dir = listSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        listSort = { col, dir: 'asc' };
      }
      renderListRows();
    });
  });
}

function renderListRows() {
  const status   = document.getElementById('filter-status').value;
  const category = document.getElementById('filter-category').value;
  const year     = document.getElementById('filter-year').value;
  const budget   = document.getElementById('filter-budget').value;
  const search   = document.getElementById('filter-search').value.toLowerCase();

  let filtered = allProjects.filter(p => {
    if (status   && p.status   !== status)              return false;
    if (category && p.category !== category)            return false;
    if (year     && String(p.start_year) !== year)      return false;
    if (budget) {
      const amt = Number(p.amount) || 0;
      if (budget === 'none') {
        if (p.amount && Number(p.amount) > 0)           return false;
      } else {
        const [min, max] = budget.split('-').map(Number);
        if (amt < min || amt > max)                     return false;
      }
    }
    if (search   && !p.title.toLowerCase().includes(search) &&
                    !p.id.toLowerCase().includes(search) &&
                    !(p.category || '').toLowerCase().includes(search) &&
                    !(String(p.start_year || '')).includes(search) &&
                    !(p.shepard || '').toLowerCase().includes(search) &&
                    !(p.internationalClub_name || '').toLowerCase().includes(search))
                                                        return false;
    return true;
  });

  filtered.sort((a, b) => {
    let av = a[listSort.col] ?? '';
    let bv = b[listSort.col] ?? '';
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av < bv) return listSort.dir === 'asc' ? -1 : 1;
    if (av > bv) return listSort.dir === 'asc' ?  1 : -1;
    return 0;
  });

  const tbody = document.getElementById('project-tbody');
  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="no-results">No projects match the current filters.</td></tr>';
    const totalEl = document.getElementById('budget-total');
    if (totalEl) totalEl.textContent = '—';
    return;
  }

  tbody.innerHTML = filtered.map((p, rowNum) => {
    const idx = allProjects.indexOf(p);
    const rawAmt = p.amount;
    const amt = rawAmt
      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(rawAmt)
      : '—';
    return `
      <tr data-idx="${idx}">
        <td style="color:#aaa;font-size:11px;text-align:center;">${rowNum + 1}</td>
        <td style="font-size:11px;color:#888;white-space:nowrap;">${p.id}</td>
        <td>${p.title}</td>
        <td>${p.category || '—'}</td>
        <td>${p.start_year || '—'}</td>
        <td><span class="badge badge-${p.status}">${p.status}</span></td>
        <td class="amount">${amt}</td>
        <td>${p.shepard || '—'}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('tr[data-idx]').forEach(row => {
    row.addEventListener('click', () => showDetail(Number(row.dataset.idx)));
  });

  const total = filtered.reduce((sum, p) => sum + (Number(p.amount) || 0), 0);
  const totalEl = document.getElementById('budget-total');
  if (totalEl) {
    totalEl.textContent = total > 0
      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(total)
      : '—';
  }
}

// --- 2. Hardened Project Detail View ---
function showDetail(idx) {
  const numericIdx = Number(idx);
  const project = allProjects[numericIdx];
  if (!project) {
    console.error("Project not found at index:", idx);
    return;
  }

  currentView  = 'detail';
  currentIndex = numericIdx;
  setActiveNav('');
  highlightMarker(numericIdx);

  const rp = document.getElementById('right-pane');
  if (!rp) return;

  const rawAmt = project.amount ?? project.budget ?? '';
  const numAmt = Number(rawAmt);
  const amt = (!isNaN(numAmt) && numAmt > 0)
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(numAmt)
    : '—';

  const startYr = project.start_year || '';
  const endYr = project.end_year || '';
  const period = (startYr && endYr && startYr !== endYr) ? `${startYr}–${endYr}` : (startYr || '—');

  const encodedNarrative = project.narrative ? encodeURIComponent(project.narrative) : '';
  const projectId = project.id || project.grant_id || 'N/A';

  // Maintenance mode edit button (guarded)
  const isMaint = (typeof isMaintenanceMode !== "undefined") && isMaintenanceMode;
  const editBtn = isMaint
    ? `<button onclick="openEditModal(${numericIdx})" style="background:#d97706;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">✏️ Edit Project</button>`
    : '';

  rp.innerHTML = `
    <div class="panel" id="detail-panel">
      <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
        <div style="flex:1">
          <h2 style="border:none;padding:0;margin-bottom:4px;">${project.title || 'Untitled Project'}</h2>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <span class="badge badge-${(project.status || '').toLowerCase()}">${project.status || '—'}</span>
            <span style="color:#888;font-size:12px;">${projectId}</span>
            <span style="color:#888;font-size:12px;">${period}</span>
            <span style="color:#555;font-size:12px;font-weight:500;">${project.category || ''}</span>
          </div>
        </div>
        <div style="display:flex;gap:6px;">
          ${editBtn}
          <button onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;white-space:nowrap;">
            ← All Projects
          </button>
        </div>
      </div>

      <div id="photo-area"></div>

      <h3>Summary</h3>
      <div class="narrative ${project.narrative ? '' : 'placeholder'}" id="narrative-body" data-raw="${encodedNarrative}">
        ${project.narrative ? '' : (project.description || 'No narrative available yet.')}
      </div>

      <h3>Project Details</h3>
      <div class="meta-grid">
        <div class="meta-item">
          <label>Project Budget</label>
          <span>${amt}</span>
        </div>
        <div class="meta-item">
          <label>Beneficiaries</label>
          <span>${project.beneficiaries || '—'}</span>
        </div>
        <div class="meta-item">
          <label>Shepherd</label>
          <span>${project.shepard || project.shepherd || '—'}</span>
        </div>
        <div class="meta-item">
          <label>International Club</label>
          <span>${project.internationalClub_name || '—'}${project.internationalClub_district ? ' (D' + project.internationalClub_district + ')' : ''}</span>
        </div>
        <div class="meta-item">
          <label>Key Partner</label>
          <span>${project.partner || '—'}</span>
        </div>
      </div>

      <div id="files-area"></div>

      <div class="detail-nav">
        <button id="btn-prev" ${numericIdx === 0 ? 'disabled' : ''} onclick="showDetail(${numericIdx - 1})">
          ← Previous
        </button>
        <button id="btn-next" ${numericIdx === allProjects.length - 1 ? 'disabled' : ''} onclick="showDetail(${numericIdx + 1})">
          Next →
        </button>
      </div>
    </div>
  `;

  if (typeof loadProjectFiles === "function") {
    setTimeout(() => loadProjectFiles(projectId), 0);
  }
  if (typeof renderMarkdown === "function") {
    renderMarkdown();
  }
}


// ============================================================
// EDIT PROJECT MODAL
// ============================================================
function setupEditModal() {
  if (document.getElementById('edit-modal')) return;
  const modal = document.createElement('div');
  modal.id = 'edit-modal';
  modal.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h3 id="modal-title-text">Edit Project</h3>
        <button onclick="closeEditModal()" style="background:transparent;border:none;color:white;font-size:18px;cursor:pointer;">✕</button>
      </div>
      <div class="modal-body">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div><label style="font-size:11px;font-weight:bold;">Title</label><input type="text" id="modal-title" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
          <div><label style="font-size:11px;font-weight:bold;">Status</label><input type="text" id="modal-status" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
          <div><label style="font-size:11px;font-weight:bold;">Shepherd</label><input type="text" id="modal-shepard" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
          <div><label style="font-size:11px;font-weight:bold;">Budget / Amount</label><input type="text" id="modal-amount" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
        </div>
        <label style="font-size:11px;font-weight:bold;">Markdown Narrative</label>
        <div class="editor-split">
          <textarea id="modal-narrative" oninput="loadMarked().then(() => document.getElementById('modal-preview').innerHTML = marked.parse(this.value))"></textarea>
          <div class="preview" id="modal-preview"></div>
        </div>
        <div>
          <label style="font-size:11px;font-weight:bold;">Web Links</label>
          <div id="modal-links-list"></div>
          <button type="button" onclick="addLinkInput()" style="margin-top:4px;padding:3px 8px;font-size:11px;cursor:pointer;">+ Add Link</button>
        </div>
        <div>
          <label style="font-size:11px;font-weight:bold;">Upload Files / Photos</label>
          <input type="file" id="modal-file-upload" multiple style="display:block;margin-top:4px;">
        </div>
      </div>
      <div class="modal-footer">
        <button onclick="closeEditModal()" style="padding:6px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;">Cancel</button>
        <button id="btn-save-project" onclick="saveProjectEdits()" style="padding:6px 14px;border:none;background:#059669;color:white;border-radius:4px;cursor:pointer;font-weight:bold;">Save Changes</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}

let activeEditIdx = null;

window.openEditModal = async function (idx) {
  setupEditModal();
  activeEditIdx = idx;
  const p = allProjects[idx];

  document.getElementById('modal-title-text').textContent = `Edit Project: ${p.id}`;
  document.getElementById('modal-title').value = p.title || '';
  document.getElementById('modal-status').value = p.status || '';
  document.getElementById('modal-shepard').value = p.shepard || '';
  document.getElementById('modal-amount').value = p.amount || '';
  document.getElementById('modal-narrative').value = p.narrative || '';

  loadMarked().then(() => {
    document.getElementById('modal-preview').innerHTML = marked.parse(p.narrative || '');
  });

  const linksContainer = document.getElementById('modal-links-list');
  linksContainer.innerHTML = '';
  try {
    const res = await fetch(`projects/${p.id}/files.json`);
    const data = await res.json();
    (data.links || []).forEach(l => addLinkInput(l.label, l.url));
  } catch {
    addLinkInput();
  }

  document.getElementById('edit-modal').style.display = 'flex';
};

window.addLinkInput = function (label = '', url = '') {
  const div = document.createElement('div');
  div.className = 'link-row';
  div.innerHTML = `
    <input type="text" placeholder="Label" value="${label}" style="width:35%;padding:4px;border:1px solid #cbd5e1;border-radius:4px;">
    <input type="text" placeholder="URL" value="${url}" style="flex:1;padding:4px;border:1px solid #cbd5e1;border-radius:4px;">
    <button onclick="this.parentElement.remove()" style="background:#ef4444;color:white;border:none;padding:2px 6px;border-radius:4px;cursor:pointer;">✕</button>
  `;
  document.getElementById('modal-links-list').appendChild(div);
};

window.closeEditModal = function () {
  document.getElementById('edit-modal').style.display = 'none';
};

window.saveProjectEdits = async function () {
  const p = allProjects[activeEditIdx];
  const btn = document.getElementById('btn-save-project');
  btn.textContent = 'Saving...';
  btn.disabled = true;

  try {
    const updates = {
      title: document.getElementById('modal-title').value,
      status: document.getElementById('modal-status').value,
      shepard: document.getElementById('modal-shepard').value,
      amount: document.getElementById('modal-amount').value,
      narrative: document.getElementById('modal-narrative').value
    };

    await fetch(`${BACKEND_URL}/api/projects/${p.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });

    const links = [];
    document.querySelectorAll('#modal-links-list .link-row').forEach(r => {
      const inputs = r.querySelectorAll('input');
      if (inputs[0].value.trim() && inputs[1].value.trim()) {
        links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
      }
    });

    await fetch(`${BACKEND_URL}/api/projects/${p.id}/links`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ links })
    });

    const fileInput = document.getElementById('modal-file-upload');
    if (fileInput.files.length > 0) {
      for (const file of fileInput.files) {
        const fd = new FormData();
        fd.append('file', file);
        await fetch(`${BACKEND_URL}/api/projects/${p.id}/upload`, { method: 'POST', body: fd });
      }
    }

    closeEditModal();
    loadData().then(projects => {
      allProjects = projects;
      showDetail(activeEditIdx);
    });
  } catch {
    alert('Error updating project data.');
  } finally {
    btn.textContent = 'Save Changes';
    btn.disabled = false;
  }
};

// ============================================================
// FILES.JSON LOADER
// ============================================================
function loadProjectFiles(projectId) {
  fetch(`projects/${projectId}/files.json`)
    .then(r => r.ok ? r.json() : { files: [], links: [] })
    .catch(() => ({ files: [], links: [] }))
    .then(manifest => renderFilesAndLinks(manifest, projectId));
}

function renderFilesAndLinks(manifest, projectId) {
  const files = manifest.files || [];
  const links = manifest.links || [];

  const images = files.filter(f => /\.(jpg|jpeg|png|gif|webp)$/i.test(f));
  const docs   = files.filter(f => !/\.(jpg|jpeg|png|gif|webp)$/i.test(f));

  const photoArea = document.getElementById('photo-area');
  const filesArea = document.getElementById('files-area');
  if (!photoArea || !filesArea) return;

  if (images.length > 0) {
    photoArea.innerHTML = `
      <div class="photo-carousel">
        ${images.map(f =>
          `<img src="projects/${projectId}/${f}" alt="${f}"
               onerror="this.style.display='none'"
               onclick="window.open('projects/${projectId}/${f}','_blank')">`
        ).join('')}
      </div>
    `;
  }

  if (docs.length === 0 && links.length === 0) return;

  filesArea.innerHTML = `<h3>Documents &amp; Links</h3><div class="files-section" id="files-list"></div>`;
  const list = document.getElementById('files-list');

  docs.forEach(f => {
    const icon = fileIcon(f);
    const a = document.createElement('a');
    a.href   = `projects/${projectId}/${f}`;
    a.target = '_blank';
    a.innerHTML = `<span class="file-icon">${icon}</span> ${f}`;
    list.appendChild(a);
  });

  links.forEach(l => {
    const a = document.createElement('a');
    a.href   = l.url;
    a.target = '_blank';
    a.innerHTML = `<span class="file-icon">🔗</span> ${l.label || l.url}`;
    list.appendChild(a);
  });
}

function fileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  switch (ext) {
    case 'pdf':  return '📄';
    case 'doc':
    case 'docx': return '📝';
    case 'xls':
    case 'xlsx': return '📊';
    case 'txt':  return '📃';
    default:     return '📎';
  }
}

// ============================================================
// UTILITIES
// ============================================================
function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

// ============================================================
// MARKDOWN RENDERING
// ============================================================
function renderMarkdown() {
  const el = document.getElementById('narrative-body');
  if (!el) return;
  if (el.classList.contains('placeholder')) return;

  const raw = el.dataset.raw ? decodeURIComponent(el.dataset.raw) : '';
  if (!raw.trim()) return;

  loadMarked().then(() => {
    el.innerHTML = marked.parse(raw);
  });
}

function loadMarked() {
  return new Promise(resolve => {
    if (window.marked) { resolve(); return; }
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js';
    s.onload = resolve;
    document.head.appendChild(s);
  });
}

// ============================================================
// DIVIDER — drag to resize panes
// ============================================================
function initDivider() {
  const divider  = document.getElementById('divider');
  const mapPane  = document.getElementById('map-pane');
  const app      = document.getElementById('app');
  let dragging   = false;
  let startX     = 0;
  let startWidth = 0;

  divider.addEventListener('mousedown', e => {
    dragging   = true;
    startX     = e.clientX;
    startWidth = mapPane.getBoundingClientRect().width;
    divider.classList.add('dragging');
    document.body.style.cursor     = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const appWidth = app.getBoundingClientRect().width;
    const newWidth = startWidth + (e.clientX - startX);
    const pct      = Math.min(Math.max(newWidth / appWidth * 100, 15), 85);
    mapPane.style.flex = `0 0 ${pct}%`;
  });

  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    divider.classList.remove('dragging');
    document.body.style.cursor     = '';
    document.body.style.userSelect = '';
  });
}
