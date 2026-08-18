// ============================================================
// RCLA Project Map — main.js
// Complete: Overview + List + Detail + Maint Mode & Inline Editor
// ============================================================

const BACKEND_URL = 'http://127.0.0.1:8000';
const CSV_PATH = 'RCLA_Projects_v2.csv';

// --- 1. Inject App CSS ---
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

  /* ---- Top Nav ---- */
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

  /* ---- Two-Pane Body ---- */
  #app {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* ---- Left Pane: Map ---- */
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

  /* ---- Right Pane ---- */
  #right-pane {
    flex: 1;
    overflow-y: auto;
    background: #f7f7f7;
    display: flex;
    flex-direction: column;
    min-width: 200px;
  }

  /* ---- Shared Panel Styles ---- */
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

  /* ---- Loading / Error States ---- */
  #loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #888;
    font-size: 15px;
  }

  /* ---- Status Badges ---- */
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

  /* ---- Project Detail ---- */
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

  /* ---- Files & Links ---- */
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

  /* ---- Photo Carousel ---- */
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

  /* ---- Detail Navigation ---- */
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

  /* ---- Filters ---- */
  .filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }
  .filters select,
  .filters input {
    padding: 5px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 13px;
    background: white;
  }

  /* ---- Project List Table ---- */
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

  /* ---- Overview ---- */
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
`;
document.head.appendChild(style);

// --- 2. Base DOM Structure ---
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
let allProjects       = [];
let map               = null;
let markers           = [];
let currentView       = 'overview';
let currentIndex      = 0;
let isMaintenanceMode = false;
let listSort          = { col: 'start_year', dir: 'asc' };
let activeEditIdx     = null;
let editMarker        = null;
let mapClickListener  = null;

let currentFilters = {
  status: '',
  category: '',
  year: '',
  search: ''
};

// Safe Coordinate Parser (Handles separate columns & single-column "lat, lng" strings)
function getProjectCoords(project) {
  if (!project) return null;
  let latVal = project.position_lat ?? project.lat;
  let lngVal = project.position_lng ?? project.lng;

  if (typeof latVal === 'string' && latVal.includes(',')) {
    const parts = latVal.split(',');
    latVal = parts[0].trim();
    lngVal = parts[1].trim();
  }

  const lat = Number(latVal);
  const lng = Number(lngVal);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
}

// Centralized Filter Calculation
function getFilteredProjects() {
  const s = (currentFilters.status || '').trim().toLowerCase();
  const c = (currentFilters.category || '').trim().toLowerCase();
  const y = (currentFilters.year || '').trim();
  const q = (currentFilters.search || '').trim().toLowerCase();

  return allProjects.filter(p => {
    if (s && String(p.status || '').trim().toLowerCase() !== s) return false;
    if (c && String(p.category || '').trim().toLowerCase() !== c) return false;
    if (y && String(p.start_year || '').trim() !== y) return false;
    if (q) {
      const matchTitle   = String(p.title || '').toLowerCase().includes(q);
      const matchId      = String(p.id || '').toLowerCase().includes(q);
      const matchShepard = String(p.shepard || p.shepherd || '').toLowerCase().includes(q);
      if (!matchTitle && !matchId && !matchShepard) return false;
    }
    return true;
  });
}

// ============================================================
// ENTRY POINT & MAP INITIALIZATION
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
      const loading = document.getElementById('loading');
      if (loading) loading.textContent = 'Error loading project data: ' + err.message;
      console.error(err);
    });
};

function loadData() {
  return fetch(CSV_PATH)
    .then(r => {
      if (!r.ok) throw new Error(`Could not fetch ${CSV_PATH}`);
      return r.text();
    })
    .then(csv => new Promise((resolve, reject) => {
      Papa.parse(csv, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
        complete: res => resolve(res.data.filter(p => p.id || p.grant_id)),
        error:    err => reject(err),
      });
    }));
}

function buildMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    zoom: 10,
    center: { lat: 14.703454, lng: -91.191623 },
    mapTypeId: 'roadmap',
    mapTypeControl: true,
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

function markerColor(status) {
  switch (String(status).toLowerCase()) {
    case 'closed':               return 'orange';
    case 'approved':             return 'green';
    case 'proposed':             return 'blue';
    case 'approved/delinquent':  return 'yellow';
    default:                     return 'red';
  }
}

function highlightMarker(idx) {
  resetMarkers();
  const active = markers[idx];
  if (!active || typeof active.getPosition !== 'function') return;

  try {
    const pinIcon = {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" fill="#dc2626" stroke="#ffffff" stroke-width="2.5"/>
          <polygon points="12,4 14.5,9.5 20.5,10 16,14 17.5,20 12,17 6.5,20 8,14 3.5,10 9.5,9.5" fill="#facc15"/>
        </svg>
      `),
      scaledSize: new google.maps.Size(46, 46),
      anchor: new google.maps.Point(23, 23)
    };

    active.setIcon(pinIcon);
    active.setZIndex(999999);
    active.setAnimation(google.maps.Animation.BOUNCE);

    if (map && active.getPosition()) {
      map.panTo(active.getPosition());
      if (map.getZoom() < 12) map.setZoom(12);
    }
  } catch (err) {
    console.warn('Marker highlighting note:', err);
  }
}

function resetMarkers() {
  markers.forEach((m, i) => {
    if (!m) return;
    m.setAnimation(null);
    m.setIcon(`https://maps.google.com/mapfiles/ms/icons/${markerColor(allProjects[i].status)}-dot.png`);
    m.setZIndex(1);
  });
}

// ============================================================
// NAVIGATION & VIEWS
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
// VIEW: OVERVIEW (HONORS ACTIVE FILTERS)
// ============================================================
function showOverview() {
  currentView = 'overview';
  setActiveNav('overview');

  const filtered = getFilteredProjects();

  // Synchronize map markers with active filter
  if (markers.length) {
    resetMarkers();
    const filteredSet = new Set(filtered);
    const bounds = new google.maps.LatLngBounds();
    let count = 0;
    allProjects.forEach((p, idx) => {
      const m = markers[idx];
      if (!m) return;
      if (filteredSet.has(p)) {
        m.setMap(map);
        if (m.getPosition()) {
          bounds.extend(m.getPosition());
          count++;
        }
      } else {
        m.setMap(null);
      }
    });
    if (count > 0 && map) map.fitBounds(bounds);
  }

  const closed   = filtered.filter(p => String(p.status).toLowerCase() === 'closed');
  const approved = filtered.filter(p => String(p.status).toLowerCase() === 'approved');
  const proposed = filtered.filter(p => String(p.status).toLowerCase() === 'proposed');
  const totalGrants = filtered.reduce((s, p) => s + (Number(p.amount) || 0), 0);

  const statuses   = [...new Set(allProjects.map(p => p.status).filter(Boolean))].sort();
  const categories = [...new Set(allProjects.map(p => p.category).filter(Boolean))].sort();
  const years      = [...new Set(allProjects.map(p => p.start_year).filter(Boolean))].sort();

  const isFiltered = currentFilters.status || currentFilters.category || currentFilters.year || currentFilters.search;
  const filterNotice = isFiltered ? `<span style="font-size:12px;color:#d97706;font-weight:normal;"> (Filtered: ${filtered.length} of ${allProjects.length})</span>` : '';

  const rp = document.getElementById('right-pane');
  rp.innerHTML = `
    <div class="panel" id="overview-panel">
      <h2>Club Projects Overview ${filterNotice}</h2>

      <div class="filters">
        <select id="overview-filter-status">
          <option value="">All statuses</option>
          ${statuses.map(s => `<option value="${s}">${capitalize(s)}</option>`).join('')}
        </select>
        <select id="overview-filter-category">
          <option value="">All categories</option>
          ${categories.map(c => `<option value="${c}">${c}</option>`).join('')}
        </select>
        <select id="overview-filter-year">
          <option value="">All years</option>
          ${years.map(y => `<option value="${y}">${y}</option>`).join('')}
        </select>
        <input id="overview-filter-search" type="text" placeholder="Search…" style="flex:1;min-width:120px;">
      </div>

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
        indigenous communities.</p>
      </div>

      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-value">${filtered.length}</div>
          <div class="stat-label">Projects in View</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">$${(totalGrants / 1e6).toFixed(2)}M</div>
          <div class="stat-label">Funding in View</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${closed.length} / ${approved.length} / ${proposed.length}</div>
          <div class="stat-label">Closed / Active / Proposed</div>
        </div>
      </div>

      <div class="chart-card">
        <h3>Grant funding by year</h3>
        <div style="position:relative;height:200px;"><canvas id="chart-by-year"></canvas></div>
      </div>

      <div class="chart-card">
        <h3>Portfolio by category</h3>
        <div style="position:relative;height:220px;"><canvas id="chart-by-cat"></canvas></div>
      </div>
    </div>
  `;

  // Restore filter values into overview dropdowns
  if (document.getElementById('overview-filter-status'))   document.getElementById('overview-filter-status').value = currentFilters.status;
  if (document.getElementById('overview-filter-category')) document.getElementById('overview-filter-category').value = currentFilters.category;
  if (document.getElementById('overview-filter-year'))     document.getElementById('overview-filter-year').value = currentFilters.year;
  if (document.getElementById('overview-filter-search'))   document.getElementById('overview-filter-search').value = currentFilters.search;

  // Wire overview filter events
  ['overview-filter-status', 'overview-filter-category', 'overview-filter-year', 'overview-filter-search'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', () => {
      currentFilters.status   = document.getElementById('overview-filter-status')?.value || '';
      currentFilters.category = document.getElementById('overview-filter-category')?.value || '';
      currentFilters.year     = document.getElementById('overview-filter-year')?.value || '';
      currentFilters.search   = document.getElementById('overview-filter-search')?.value || '';
      showOverview();
    });
  });

  loadChartJS().then(() => buildOverviewCharts(filtered));
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

function buildOverviewCharts(projects) {
  const dataset = projects || allProjects;
  const BLUE = '#1a3a5c';
  const COLORS = ['#1a3a5c','#2196f3','#4caf50','#ff9800','#9c27b0','#f44336','#059669','#d97706'];

  // 1. Funding by year
  const yearMap = {};
  dataset.forEach(p => {
    const y = p.start_year;
    if (!y) return;
    yearMap[y] = (yearMap[y] || 0) + (Number(p.amount) || 0);
  });
  const years = Object.keys(yearMap).sort();
  const amounts = years.map(y => yearMap[y]);

  const yearEl = document.getElementById('chart-by-year');
  if (yearEl) {
    new Chart(yearEl, {
      type: 'bar',
      data: {
        labels: years.length ? years : ['No Data'],
        datasets: [{ label: 'Grant Amount', data: amounts.length ? amounts : [0], backgroundColor: BLUE }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { ticks: { callback: v => '$' + (v/1000).toFixed(0) + 'k' } } }
      }
    });
  }

  // 2. Portfolio by category
  const catMap = {};
  dataset.forEach(p => {
    const c = p.category || 'General';
    catMap[c] = (catMap[c] || 0) + (Number(p.amount) || 0);
  });
  const cats = Object.keys(catMap);
  const catAmts = cats.map(c => catMap[c]);

  const catEl = document.getElementById('chart-by-cat');
  if (catEl) {
    new Chart(catEl, {
      type: 'doughnut',
      data: {
        labels: cats.length ? cats : ['No Data'],
        datasets: [{ data: catAmts.length ? catAmts : [1], backgroundColor: cats.length ? COLORS : ['#cbd5e1'] }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } }
      }
    });
  }
}

// ============================================================
// VIEW: PROJECT LIST
// ============================================================
function showList() {
  currentView = 'list';
  setActiveNav('list');
  renderList();
}

function wireListFilters() {
  ['filter-status', 'filter-category', 'filter-year', 'filter-search'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', renderListRows);
    }
  });

  // Column header sorting
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

function renderList() {
  const rp = document.getElementById('right-pane');
  const statuses   = [...new Set(allProjects.map(p => p.status).filter(Boolean))].sort();
  const categories = [...new Set(allProjects.map(p => p.category).filter(Boolean))].sort();
  const years      = [...new Set(allProjects.map(p => p.start_year).filter(Boolean))].sort();

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
        <input id="filter-search" type="text" placeholder="Search…" style="flex:1;min-width:120px;">
      </div>
      <table id="project-table">
        <thead>
          <tr>
            <th style="width:36px;">#</th>
            <th data-col="id">ID</th>
            <th data-col="title">Project</th>
            <th data-col="category">Category</th>
            <th data-col="start_year">Year</th>
            <th data-col="status">Status</th>
            <th data-col="amount" style="text-align:right">Budget</th>
          </tr>
        </thead>
        <tbody id="project-tbody"></tbody>
      </table>
    </div>
  `;

  // Restore saved filter selections into the newly created inputs
  if (document.getElementById('filter-status'))   document.getElementById('filter-status').value = currentFilters.status;
  if (document.getElementById('filter-category')) document.getElementById('filter-category').value = currentFilters.category;
  if (document.getElementById('filter-year'))     document.getElementById('filter-year').value = currentFilters.year;
  if (document.getElementById('filter-search'))   document.getElementById('filter-search').value = currentFilters.search;

  wireListFilters();
  renderListRows();
}

function renderListRows() {
  currentFilters.status   = document.getElementById('filter-status')?.value || '';
  currentFilters.category = document.getElementById('filter-category')?.value || '';
  currentFilters.year     = document.getElementById('filter-year')?.value || '';
  currentFilters.search   = document.getElementById('filter-search')?.value || '';

  let filtered = getFilteredProjects();

  // Apply sorting
  filtered.sort((a, b) => {
    let av = a[listSort.col] ?? '';
    let bv = b[listSort.col] ?? '';
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av < bv) return listSort.dir === 'asc' ? -1 : 1;
    if (av > bv) return listSort.dir === 'asc' ?  1 : -1;
    return 0;
  });

  // Synchronize Map Markers with Filtered Set
  const filteredSet = new Set(filtered);
  const bounds = new google.maps.LatLngBounds();
  let visibleCount = 0;

  allProjects.forEach((p, idx) => {
    const marker = markers[idx];
    if (!marker) return;

    if (filteredSet.has(p)) {
      marker.setMap(map);
      if (typeof marker.getPosition === 'function' && marker.getPosition()) {
        bounds.extend(marker.getPosition());
        visibleCount++;
      }
    } else {
      marker.setMap(null);
    }
  });

  if (visibleCount > 0 && map && currentView === 'list') {
    map.fitBounds(bounds);
    if (visibleCount === 1 && map.getZoom() > 14) {
      map.setZoom(14);
    }
  }

  // Render Table Rows
  const tbody = document.getElementById('project-tbody');
  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#888;padding:20px;font-style:italic;">No projects match the selected filters.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map((p, rowNum) => {
    const idx = allProjects.indexOf(p);
    const amt = p.amount ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(p.amount) : '—';
    return `
      <tr data-idx="${idx}">
        <td style="color:#aaa;font-size:11px;text-align:center;">${rowNum + 1}</td>
        <td style="font-size:11px;color:#888;white-space:nowrap;">${p.id}</td>
        <td>${p.title}</td>
        <td>${p.category || '—'}</td>
        <td>${p.start_year || '—'}</td>
        <td><span class="badge badge-${p.status}">${p.status}</span></td>
        <td class="amount">${amt}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('tr[data-idx]').forEach(row => {
    row.addEventListener('click', () => showDetail(Number(row.dataset.idx)));
  });
}

// ============================================================
// DETAIL VIEW & INLINE RIGHT-PANE EDITOR
// ============================================================
function showDetail(idx) {
  cancelEditCleanup();

  currentView  = 'detail';
  currentIndex = Number(idx);
  setActiveNav('');
  highlightMarker(currentIndex);

  const project = allProjects[currentIndex];
  if (!project) return;

  const rp = document.getElementById('right-pane');
  const amt = project.amount ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(project.amount) : '—';
  const period = project.start_year === project.end_year ? String(project.start_year) : `${project.start_year}–${project.end_year}`;

  const editBtn = isMaintenanceMode
    ? `<button onclick="openEditForm(${currentIndex})" style="background:#d97706;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">✏️ Edit Project</button>`
    : '';

  rp.innerHTML = `
    <div class="panel" id="detail-panel">
      <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
        <div style="flex:1">
          <h2 style="border:none;padding:0;margin-bottom:4px;">${project.title}</h2>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <span class="badge badge-${project.status}">${project.status}</span>
            <span style="color:#888;font-size:12px;">${project.id}</span>
            <span style="color:#888;font-size:12px;">${period}</span>
            <span style="color:#555;font-size:12px;font-weight:500;">${project.category || ''}</span>
          </div>
        </div>
        <div style="display:flex;gap:6px;">
          ${editBtn}
          <button onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;white-space:nowrap;">← All Projects</button>
        </div>
      </div>

      <div id="photo-area"></div>

      <h3>Summary</h3>
      <div class="narrative" id="narrative-body" data-raw="${encodeURIComponent(project.narrative || '')}">
        ${project.narrative ? '' : (project.description || 'No narrative available yet.')}
      </div>

      <h3>Project Details</h3>
      <div class="meta-grid">
        <div class="meta-item"><label>Project Budget</label><span>${amt}</span></div>
        <div class="meta-item"><label>Shepherd</label><span>${project.shepard || '—'}</span></div>
        <div class="meta-item"><label>Category</label><span>${project.category || '—'}</span></div>
        <div class="meta-item"><label>Key Partner</label><span>${project.partner || '—'}</span></div>
      </div>

      <div id="files-area"></div>

      <div class="detail-nav">
        <button id="btn-prev" ${currentIndex === 0 ? 'disabled' : ''} onclick="showDetail(${currentIndex - 1})">← Previous</button>
        <button id="btn-next" ${currentIndex === allProjects.length - 1 ? 'disabled' : ''} onclick="showDetail(${currentIndex + 1})">Next →</button>
      </div>
    </div>
  `;

  setTimeout(() => loadProjectFiles(project.id), 0);
  renderMarkdown();
}

window.openEditForm = async function (idx) {
  activeEditIdx = Number(idx);
  const p = allProjects[activeEditIdx];
  if (!p) return;

  const coords = getProjectCoords(p) || { lat: 14.703454, lng: -91.191623 };
  const rp = document.getElementById('right-pane');

  rp.innerHTML = `
    <div class="panel" id="edit-panel">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:2px solid #d97706;padding-bottom:6px;">
        <h2 style="border:none;padding:0;margin:0;color:#d97706;">✏️ Edit: ${p.id}</h2>
        <div style="display:flex;gap:6px;">
          <button type="button" onclick="cancelEdit()" style="padding:5px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>
          <button type="button" id="btn-save-project" onclick="saveProjectEdits()" style="padding:5px 14px;border:none;background:#059669;color:white;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">Save Changes</button>
        </div>
      </div>

      <div style="background:#eff6ff;border:1px solid #bfdbfe;padding:8px 12px;border-radius:6px;font-size:12px;color:#1e40af;margin-bottom:12px;">
        📍 <strong>Map Positioning Active:</strong> Drag the marker on the map or click anywhere on the map to set exact coordinates.
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
        <div><label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Title</label><input type="text" id="modal-title" value="${p.title || ''}" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
        <div><label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Status</label><input type="text" id="modal-status" value="${p.status || ''}" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
        <div><label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Shepherd</label><input type="text" id="modal-shepard" value="${p.shepard || ''}" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
        <div><label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Budget / Amount</label><input type="text" id="modal-amount" value="${p.amount || ''}" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
        <div><label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Latitude</label><input type="text" id="modal-lat" value="${coords.lat.toFixed(6)}" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
        <div><label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Longitude</label><input type="text" id="modal-lng" value="${coords.lng.toFixed(6)}" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;"></div>
      </div>

      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Markdown Narrative</label>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px;">
        <textarea id="modal-narrative" style="width:100%;height:160px;font-family:monospace;font-size:12px;padding:8px;border:1px solid #cbd5e1;border-radius:4px;" oninput="updateEditPreview(this.value)">${p.narrative || ''}</textarea>
        <div style="font-size:11px;font-weight:bold;color:#64748b;">Live Preview:</div>
        <div class="preview" id="modal-preview" style="border:1px solid #cbd5e1;border-radius:4px;padding:10px;background:#f8fafc;min-height:80px;line-height:1.6;"></div>
      </div>

      <div style="margin-bottom:14px;">
        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Web Links</label>
        <div id="modal-links-list"></div>
        <button type="button" onclick="addLinkInput()" style="margin-top:4px;padding:4px 8px;font-size:11px;cursor:pointer;background:#e2e8f0;border:none;border-radius:4px;">+ Add Link</button>
      </div>

      <div style="margin-bottom:20px;">
        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Upload Files / Photos</label>
        <input type="file" id="modal-file-upload" multiple style="display:block;margin-top:4px;font-size:12px;">
      </div>
    </div>
  `;

  updateEditPreview(p.narrative || '');

  try {
    const res = await fetch(`projects/${p.id}/files.json`);
    const data = await res.json();
    (data.links || []).forEach(l => addLinkInput(l.label, l.url));
  } catch {
    addLinkInput();
  }

  if (map && window.google && google.maps) {
    if (editMarker) editMarker.setMap(null);
    editMarker = new google.maps.Marker({
      position: coords,
      map: map,
      draggable: true,
      animation: google.maps.Animation.DROP,
      zIndex: 1000000
    });

    editMarker.addListener('drag', (e) => {
      document.getElementById('modal-lat').value = e.latLng.lat().toFixed(6);
      document.getElementById('modal-lng').value = e.latLng.lng().toFixed(6);
    });

    if (mapClickListener) google.maps.event.removeListener(mapClickListener);
    mapClickListener = map.addListener('click', (e) => {
      if (editMarker) editMarker.setPosition(e.latLng);
      document.getElementById('modal-lat').value = e.latLng.lat().toFixed(6);
      document.getElementById('modal-lng').value = e.latLng.lng().toFixed(6);
    });
  }
};

window.cancelEdit = function () {
  cancelEditCleanup();
  showDetail(activeEditIdx);
};

function cancelEditCleanup() {
  if (editMarker) { editMarker.setMap(null); editMarker = null; }
  if (mapClickListener && window.google && google.maps) {
    google.maps.event.removeListener(mapClickListener);
    mapClickListener = null;
  }
}

function updateEditPreview(text) {
  const preview = document.getElementById('modal-preview');
  if (!preview) return;
  loadMarked().then(() => { preview.innerHTML = marked.parse(text || ''); });
}

window.addLinkInput = function (label = '', url = '') {
  const container = document.getElementById('modal-links-list');
  if (!container) return;
  const div = document.createElement('div');
  div.className = 'link-row';
  div.style.cssText = 'display:flex;gap:8px;margin-bottom:6px;';
  div.innerHTML = `
    <input type="text" placeholder="Label" value="${label}" style="width:35%;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">
    <input type="text" placeholder="https://..." value="${url}" style="flex:1;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">
    <button type="button" onclick="this.parentElement.remove()" style="background:#ef4444;color:white;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;">✕</button>
  `;
  container.appendChild(div);
};

window.saveProjectEdits = async function () {
  const p = allProjects[activeEditIdx];
  if (!p) return;
  const btn = document.getElementById('btn-save-project');
  if (btn) { btn.textContent = 'Saving...'; btn.disabled = true; }

  try {
    const latVal = document.getElementById('modal-lat')?.value || '';
    const lngVal = document.getElementById('modal-lng')?.value || '';

    const updates = {
      title: document.getElementById('modal-title')?.value || '',
      status: document.getElementById('modal-status')?.value || '',
      shepard: document.getElementById('modal-shepard')?.value || '',
      amount: document.getElementById('modal-amount')?.value || '',
      narrative: document.getElementById('modal-narrative')?.value || '',
      position_lat: latVal,
      position_lng: lngVal
    };

    // 1. Send update to orchestrator backend to write to CSV
    await fetch(`${BACKEND_URL}/api/projects/${p.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });

    // 2. Update Manifest Links
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

    // 3. Upload staged files if any
    const fileInput = document.getElementById('modal-file-upload');
    if (fileInput && fileInput.files.length > 0) {
      for (const file of fileInput.files) {
        const fd = new FormData();
        fd.append('file', file);
        await fetch(`${BACKEND_URL}/api/projects/${p.id}/upload`, { method: 'POST', body: fd });
      }
    }

    // 4. Update the in-memory marker coordinates immediately
    const parsedLat = parseFloat(latVal);
    const parsedLng = parseFloat(lngVal);
    if (!isNaN(parsedLat) && !isNaN(parsedLng) && markers[activeEditIdx]) {
      const newPos = new google.maps.LatLng(parsedLat, parsedLng);
      markers[activeEditIdx].setPosition(newPos);
    }

    // 5. Clean up temporary edit marker/listeners and re-render the detail view
    cancelEditCleanup();
    loadData().then(projects => {
      allProjects = projects;
      showDetail(activeEditIdx);
    });
  } catch (err) {
    alert('Error updating project: ' + err.message);
  } finally {
    if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
  }
};

// ============================================================
// MAINTAINER LOG STREAM & CONTROLS
// ============================================================
function initMaintainerClient() {
  const evtSource = new EventSource(`${BACKEND_URL}/api/logs`);
  evtSource.onmessage = (event) => {
    const logDiv = document.getElementById('log-output');
    if (logDiv) {
      const newLine = document.createElement('div');
      newLine.className = 'log-line';
      newLine.textContent = event.data;
      logDiv.appendChild(newLine);
      logDiv.scrollTop = logDiv.scrollHeight;
    }
    pollMaintStatus();
  };

  evtSource.onerror = () => {
    isMaintenanceMode = false;
    const badge = document.getElementById('sync-status-badge');
    if (badge) { badge.textContent = 'Offline'; badge.style.background = '#64748b'; }
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
    if (badge) {
      badge.textContent = `Status: ${data.status.toUpperCase()}`;
      badge.style.background = data.status === 'running' ? '#d97706' : data.status === 'error' ? '#dc2626' : '#059669';
    }
  } catch {
    isMaintenanceMode = false;
    const badge = document.getElementById('sync-status-badge');
    if (badge) { badge.textContent = 'Offline'; badge.style.background = '#64748b'; }
  }
}

window.triggerSync = async function (dryRun = true) {
  window.toggleLogConsole(true);
  await fetch(`${BACKEND_URL}/api/sync?dry_run=${dryRun}`, { method: 'POST' });
};

window.publishChanges = async function () {
  const msg = prompt('Commit message:', 'chore(sync): automated grant sync');
  if (!msg) return;
  await fetch(`${BACKEND_URL}/api/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg })
  });
};

window.toggleLogConsole = function (forceOpen = false) {
  const drawer = document.getElementById('log-drawer');
  if (drawer) drawer.style.display = forceOpen || drawer.style.display === 'none' ? 'block' : 'none';
};

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
        ${images.map(f => `<img src="projects/${projectId}/${f}" alt="${f}" onclick="window.open('projects/${projectId}/${f}','_blank')">`).join('')}
      </div>
    `;
  }

  if (docs.length > 0 || links.length > 0) {
    filesArea.innerHTML = `<h3>Documents &amp; Links</h3><div class="files-section" id="files-list"></div>`;
    const list = document.getElementById('files-list');
    docs.forEach(f => {
      const a = document.createElement('a');
      a.href = `projects/${projectId}/${f}`;
      a.target = '_blank';
      a.innerHTML = `<span class="file-icon">📄</span> ${f}`;
      list.appendChild(a);
    });
    links.forEach(l => {
      const a = document.createElement('a');
      a.href = l.url;
      a.tart = '_blank';
      a.innerHTML = `<span class="file-icon">🔗</span> ${l.label || l.url}`;
      list.appendChild(a);
    });
  }
}

function renderMarkdown() {
  const el = document.getElementById('narrative-body');
  if (!el) return;
  const raw = el.dataset.raw ? decodeURIComponent(el.dataset.raw) : '';
  if (!raw.trim()) return;
  loadMarked().then(() => { el.innerHTML = marked.parse(raw); });
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

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

function initDivider() {
  const divider = document.getElementById('divider');
  const mapPane = document.getElementById('map-pane');
  const app = document.getElementById('app');
  let dragging = false, startX = 0, startWidth = 0;

  divider.addEventListener('mousedown', e => {
    dragging = true;
    startX = e.clientX;
    startWidth = mapPane.getBoundingClientRect().width;
    divider.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const appWidth = app.getBoundingClientRect().width;
    const newWidth = startWidth + (e.clientX - startX);
    const pct = Math.min(Math.max(newWidth / appWidth * 100, 15), 85);
    mapPane.style.flex = `0 0 ${pct}%`;
  });

  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    divider.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
}

// Fallback initialization if Google Maps was already loaded
if (window.google && window.google.maps) {
  window.initMap();
}
