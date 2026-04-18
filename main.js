// ============================================================
// RCLA Project Map — main.js
// Phase 1: Layout + Data loading + Map
// ============================================================

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
`;
document.head.appendChild(style);

// --- Rebuild the page structure ---
document.body.innerHTML = `
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
let allProjects   = [];
let map           = null;
let markers       = [];
let currentView   = 'overview';   // 'overview' | 'list' | 'detail'
let currentIndex  = 0;            // index into allProjects for detail view
let listSort      = { col: 'start_year', dir: 'asc' };

// ============================================================
// ENTRY POINT — called by Google Maps callback
// ============================================================
function initMap() {
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
    const lat = Number(project.position_lat);
    const lng = Number(project.position_lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;

    const marker = new google.maps.Marker({
      position: { lat, lng },
      map,
      title: project.title,
      icon: `https://maps.google.com/mapfiles/ms/icons/${markerColor(project.status)}-dot.png`,
    });

    marker.addListener('click', () => showDetail(idx));
    return marker;
  });
}

function markerColor(status) {
  switch (status) {
    case 'closed':             return 'orange';
    case 'approved':           return 'green';
    case 'proposed':           return 'blue';
    case 'approved/delinquent':return 'yellow';
    default:                   return 'red';
  }
}

function highlightMarker(idx) {
  resetMarkers();
  const active = markers[idx];
  if (active) {
    active.setIcon('https://maps.google.com/mapfiles/ms/icons/red-dot.png');
    active.setZIndex(999);
    active.setAnimation(google.maps.Animation.BOUNCE);
    setTimeout(() => active.setAnimation(null), 2100);
    map.panTo(active.getPosition());
  }
}

function resetMarkers() {
  markers.forEach((m, i) => {
    if (!m) return;
    m.setIcon(
      `https://maps.google.com/mapfiles/ms/icons/${markerColor(allProjects[i].status)}-dot.png`
    );
    m.setZIndex(1);
  });
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
        <p><em>Edit this narrative in the overview section of main.js as the club's story evolves.</em></p>
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

  // Load Chart.js then render
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

  // --- By year ---
  const yearMap = {};
  allProjects.forEach(p => {
    const y = p.start_year;
    if (!y) return;
    yearMap[y] = (yearMap[y] || 0) + (Number(p.amount) || 0);
  });
  const years  = Object.keys(yearMap).sort();
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

  // --- By category ---
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

  // --- Cumulative ---
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

  // Sort
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

  // Update budget total
  const total = filtered.reduce((sum, p) => sum + (Number(p.amount) || 0), 0);
  const totalEl = document.getElementById('budget-total');
  if (totalEl) {
    totalEl.textContent = total > 0
      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(total)
      : '—';
  }
}

// ============================================================
// VIEW: PROJECT DETAIL
// ============================================================
function showDetail(idx) {
  currentView  = 'detail';
  currentIndex = idx;
  setActiveNav('');   // no top nav button active in detail view
  highlightMarker(idx);

  const project = allProjects[idx];
  const rp = document.getElementById('right-pane');

  
  const rawAmt = project.amount;
  const amt = rawAmt
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(rawAmt)
    : '—';

  const period = project.start_year === project.end_year
    ? String(project.start_year)
    : `${project.start_year}–${project.end_year}`;

  const encodedNarrative = project.narrative ? encodeURIComponent(project.narrative) : '';

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
        <button onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;white-space:nowrap;">
          ← All Projects
        </button>
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
          <span>${project.shepard || '—'}</span>
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
        <button id="btn-prev" ${idx === 0 ? 'disabled' : ''} onclick="showDetail(${idx - 1})">
          ← Previous
        </button>
        <button id="btn-next" ${idx === allProjects.length - 1 ? 'disabled' : ''} onclick="showDetail(${idx + 1})">
          Next →
        </button>
      </div>
    </div>
  `;

  setTimeout(() => loadProjectFiles(project.id), 0);
  renderMarkdown();
}

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

  // Guard: panel may have been replaced before fetch resolved
  const photoArea = document.getElementById('photo-area');
  const filesArea = document.getElementById('files-area');
  if (!photoArea || !filesArea) return;

  // Photos
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

  // Docs + links
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
