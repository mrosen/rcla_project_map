// ============================================================
// RCLA Project Map — main.js
// Stable State: Deep-Linking (REST URLs) + Maintainer Mode
// ============================================================

const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://127.0.0.1:8000'
  : window.location.origin;
const CSV_PATH = 'RCLA_Projects_v2.csv';

// Supabase Cloud Configuration
const SUPABASE_URL = 'https://rqhmsincnmxrgtipvkif.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxaG1zaW5jbm14cmd0aXB2a2lmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk1MTgwMzUsImV4cCI6MjEwNTA5NDAzNX0.XJY9Q6akA4KF0Ei5Ri8blJ1yxfNM75l-oNK9nR1H40o';

let supabaseClient = null;
try {
  if (window.supabase && typeof window.supabase.createClient === 'function') {
    supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }
} catch (e) {
  console.warn('Supabase SDK initialization error:', e);
}

// App & Carousel Styles
(function injectStyles() {
  if (document.getElementById('rcla-dynamic-styles')) return;
  const style = document.createElement('style');
  style.id = 'rcla-dynamic-styles';
  style.textContent = `
    .photo-carousel {
      display: flex;
      gap: 10px;
      overflow-x: auto;
      margin-bottom: 14px;
      padding-bottom: 6px;
      min-height: 140px;
      align-items: center;
    }
    .photo-carousel img {
      height: 140px;
      min-width: 140px;
      max-width: 220px;
      border-radius: 6px;
      cursor: pointer;
      object-fit: cover;
      border: 1px solid #cbd5e1;
      background: #f1f5f9;
      display: block;
      transition: transform 0.15s ease;
    }
    .photo-carousel img:hover {
      transform: scale(1.02);
      border-color: #3b82f6;
    }
    .narrative img {
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      margin: 10px 0;
      border: 1px solid #cbd5e1;
      display: block;
    }
    .filters {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .filters select, .filters input {
      padding: 5px 8px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 13px;
      background: white;
    }
    .paste-drop-zone {
      border: 2px dashed #94a3b8;
      border-radius: 6px;
      padding: 10px;
      text-align: center;
      background: #f8fafc;
      color: #475569;
      font-size: 12px;
      margin: 10px 0;
      cursor: pointer;
    }
    .paste-drop-zone:hover {
      border-color: #3b82f6;
      background: #eff6ff;
      color: #1d4ed8;
    }
  `;
  document.head.appendChild(style);
})();

let allProjects       = [];
let map               = null;
let markers           = [];
let searchMarker      = null;
let currentView       = 'overview';
let currentIndex      = 0;
let isMaintenanceMode = false;
let activeEditIdx     = null;
let editMarker        = null;
let mapClickListener  = null;
let overviewChart     = null;
let isUploadingImage  = false;
let globalPasteAbortCtrl = null;

let currentFilters = {
  type: '',
  status: '',
  category: '',
  year: '',
  search: ''
};

function getProjectType(p) {
  if (p.project_type && String(p.project_type).trim()) return p.project_type;
  var id = (p.id || p.grant_id || '').toUpperCase();
  if (id.startsWith('GG')) return 'Global Grant';
  if (id.startsWith('DG')) return 'District Grant';
  if (id.startsWith('C2C') || id.startsWith('CLUB-TO-CLUB')) return 'Club-to-Club Grant';
  return 'Club Direct / Donation';
}

function getProjectSummaryText(p) {
  if (!p) return '';
  return p.narrative || p.description || p.notes || '';
}

function getProjectCoords(project) {
  if (!project) return null;
  var latVal = project.position_lat !== undefined ? project.position_lat : project.lat;
  var lngVal = project.position_lng !== undefined ? project.position_lng : project.lng;

  if (typeof latVal === 'string' && latVal.includes(',')) {
    var parts = latVal.split(',');
    latVal = parts[0].trim();
    lngVal = parts[1].trim();
  }
  var lat = Number(latVal);
  var lng = Number(lngVal);
  return (Number.isFinite(lat) && Number.isFinite(lng)) ? { lat: lat, lng: lng } : null;
}

window.initMap = function () {
  initMaintainerClient();
  wireNavButtons();
  initDivider();

  loadData()
    .then(function (projects) {
      allProjects = projects;
      buildMap();

      // --- Deep-link handler ---
      const params = new URLSearchParams(window.location.search);
      const targetId = params.get('project') || params.get('id');

      if (targetId) {
        const foundIdx = allProjects.findIndex(p => {
          const pid = String(p.id || p.grant_id || '').trim().toLowerCase();
          return pid === targetId.trim().toLowerCase();
        });

        if (foundIdx !== -1) {
          const isEditMode = params.get('edit') === 'true' || params.get('mode') === 'edit';
          if (isEditMode) {
            openEditForm(foundIdx);
          } else {
            showDetail(foundIdx);
          }
          return;
        }
      }

      showOverview();
    })
    .catch(function (err) {
      var rp = document.getElementById('right-pane');
      if (rp) rp.innerHTML = '<div style="padding:20px;color:red;">Error loading CSV: ' + err.message + '</div>';
    });
};

function updateBackendStatus(type, count) {
  var indicator = document.getElementById('backend-status-indicator');
  var text = document.getElementById('backend-status-text');
  var dbBadge = document.getElementById('db-status-badge');
  if (type === 'supabase') {
    if (indicator) {
      indicator.style.background = 'rgba(16, 185, 129, 0.2)';
      indicator.style.borderColor = '#10b981';
      indicator.style.color = '#34d399';
      indicator.title = 'Live connection to Supabase Cloud Database & Storage (' + count + ' projects loaded)';
    }
    if (text) text.textContent = '⚡ Supabase Cloud (' + count + ')';
    if (dbBadge) {
      dbBadge.textContent = '⚡ DB: Supabase (Live)';
      dbBadge.style.background = '#059669';
    }
  } else {
    if (indicator) {
      indicator.style.background = 'rgba(245, 158, 11, 0.2)';
      indicator.style.borderColor = '#f59e0b';
      indicator.style.color = '#fbbf24';
      indicator.title = 'Loaded from local CSV backup';
    }
    if (text) text.textContent = '📁 CSV Backup (' + (count || 0) + ')';
    if (dbBadge) {
      dbBadge.textContent = 'DB: CSV Fallback';
      dbBadge.style.background = '#d97706';
    }
  }
}

function loadData() {
  if (supabaseClient) {
    return supabaseClient
      .from('projects')
      .select('*, project_links(*), project_assets(*)')
      .order('id')
      .then(function (res) {
        if (res.error) {
          console.warn('Supabase query failed, falling back to CSV:', res.error);
          return loadCsvFallback().then(function (data) {
            updateBackendStatus('csv', data.length);
            return data;
          });
        }
        if (res.data && res.data.length > 0) {
          console.log('Loaded ' + res.data.length + ' projects live from Supabase.');
          updateBackendStatus('supabase', res.data.length);
          return res.data;
        }
        return loadCsvFallback().then(function (data) {
          updateBackendStatus('csv', data.length);
          return data;
        });
      })
      .catch(function (err) {
        console.warn('Supabase offline/error, falling back to CSV:', err);
        return loadCsvFallback().then(function (data) {
          updateBackendStatus('csv', data.length);
          return data;
        });
      });
  }
  return loadCsvFallback().then(function (data) {
    updateBackendStatus('csv', data.length);
    return data;
  });
}

function loadCsvFallback() {
  return fetch(CSV_PATH)
    .then(function (r) {
      if (!r.ok) throw new Error('Could not fetch ' + CSV_PATH);
      return r.text();
    })
    .then(function (csv) {
      return new Promise(function (resolve, reject) {
        Papa.parse(csv, {
          header: true,
          skipEmptyLines: true,
          dynamicTyping: true,
          complete: function (res) { resolve(res.data.filter(function (p) { return p.id || p.grant_id; })); },
          error: function (err) { reject(err); }
        });
      });
    });
}

function buildMap() {
  var mapElement = document.getElementById('map');
  if (!mapElement || !window.google || !google.maps) return;

  map = new google.maps.Map(mapElement, {
    zoom: 10,
    center: { lat: 14.703454, lng: -91.191623 },
    mapTypeId: 'roadmap',
    mapTypeControl: true,
    fullscreenControl: true
  });
  rebuildMarkers();
}

function rebuildMarkers() {
  if (!map || !window.google || !google.maps) return;
  markers.forEach(function (m) { if (m) m.setMap(null); });
  markers = allProjects.map(function (project, idx) {
    var coords = getProjectCoords(project);
    if (!coords) return null;

    var marker = new google.maps.Marker({
      position: coords,
      map: map,
      title: project.title,
      icon: 'https://maps.google.com/mapfiles/ms/icons/' + markerColor(project.status) + '-dot.png'
    });
    marker.addListener('click', function () { showDetail(idx); });
    return marker;
  });
}

function markerColor(status) {
  switch (String(status).toLowerCase()) {
    case 'closed':   return 'orange';
    case 'approved': return 'green';
    case 'proposed': return 'blue';
    default:         return 'red';
  }
}

function highlightMarker(idx) {
  resetMarkers();
  var active = markers[idx];
  if (active && map) {
    active.setIcon('https://maps.google.com/mapfiles/ms/icons/red-dot.png');
    active.setZIndex(999);
    map.panTo(active.getPosition());
    map.setZoom(15);
  }
}

function resetMarkers() {
  markers.forEach(function (m, i) {
    if (!m || !allProjects[i]) return;
    m.setIcon('https://maps.google.com/mapfiles/ms/icons/' + markerColor(allProjects[i].status) + '-dot.png');
    m.setZIndex(1);
  });
}

function wireNavButtons() {
  document.getElementById('btn-overview').addEventListener('click', showOverview);
  document.getElementById('btn-list').addEventListener('click', showList);
}

function setActiveNav(view) {
  document.getElementById('btn-overview').classList.toggle('active', view === 'overview');
  document.getElementById('btn-list').classList.toggle('active', view === 'list');
}

function getFilteredProjects() {
  var t = (currentFilters.type || '').trim().toLowerCase();
  var s = (currentFilters.status || '').trim().toLowerCase();
  var c = (currentFilters.category || '').trim().toLowerCase();
  var y = (currentFilters.year || '').trim();
  var q = (currentFilters.search || '').trim().toLowerCase();

  return allProjects.filter(function (p) {
    if (t && getProjectType(p).toLowerCase() !== t) return false;
    if (s && String(p.status || '').trim().toLowerCase() !== s) return false;
    if (c && String(p.category || '').trim().toLowerCase() !== c) return false;
    if (y && String(p.start_year || '').trim() !== y) return false;
    if (q) {
      var match = (p.title && p.title.toLowerCase().includes(q)) ||
                  (p.id && String(p.id).toLowerCase().includes(q)) ||
                  (p.grant_id && String(p.grant_id).toLowerCase().includes(q)) ||
                  (p.partner && p.partner.toLowerCase().includes(q)) ||
                  (p.shepard && p.shepard.toLowerCase().includes(q)) ||
                  (p.shepherd && p.shepherd.toLowerCase().includes(q)) ||
                  (p.narrative && p.narrative.toLowerCase().includes(q)) ||
                  (p.description && p.description.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });
}

function syncMapMarkers(filteredProjects) {
  if (!markers.length) return;
  var filteredSet = new Set(filteredProjects);
  allProjects.forEach(function (p, idx) {
    var marker = markers[idx];
    if (marker) marker.setVisible(filteredSet.has(p));
  });
}

function renderFilterBar() {
  var types = Array.from(new Set(allProjects.map(function (p) { return getProjectType(p); }).filter(Boolean))).sort();
  var statuses = Array.from(new Set(allProjects.map(function (p) { return p.status; }).filter(Boolean))).sort();
  var categories = Array.from(new Set(allProjects.map(function (p) { return p.category; }).filter(Boolean))).sort();
  var years = Array.from(new Set(allProjects.map(function (p) { return p.start_year; }).filter(Boolean))).sort();

  var typeOptions = types.map(function (t) { return '<option value="' + t + '" ' + (currentFilters.type === t ? 'selected' : '') + '>' + t + '</option>'; }).join('');
  var statusOptions = statuses.map(function (s) { return '<option value="' + s + '" ' + (currentFilters.status === s ? 'selected' : '') + '>' + capitalize(s) + '</option>'; }).join('');
  var catOptions = categories.map(function (c) { return '<option value="' + c + '" ' + (currentFilters.category === c ? 'selected' : '') + '>' + c + '</option>'; }).join('');
  var yearOptions = years.map(function (y) { return '<option value="' + y + '" ' + (currentFilters.year === String(y) ? 'selected' : '') + '>' + y + '</option>'; }).join('');

  return ''
    + '<div class="filters">'
    + '  <select id="filter-type"><option value="">All Grant / Project Types</option>' + typeOptions + '</select>'
    + '  <select id="filter-status"><option value="">All statuses</option>' + statusOptions + '</select>'
    + '  <select id="filter-category"><option value="">All categories</option>' + catOptions + '</select>'
    + '  <select id="filter-year"><option value="">All years</option>' + yearOptions + '</select>'
    + '  <input id="filter-search" type="text" placeholder="Search title, ID, partner…" value="' + escapeHtml(currentFilters.search) + '" style="flex:1;min-width:120px;">'
    + '</div>';
}

function attachFilterListeners() {
  ['filter-type', 'filter-status', 'filter-category', 'filter-year', 'filter-search'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', function (e) {
      if (id === 'filter-type') currentFilters.type = e.target.value;
      if (id === 'filter-status') currentFilters.status = e.target.value;
      if (id === 'filter-category') currentFilters.category = e.target.value;
      if (id === 'filter-year') currentFilters.year = e.target.value;
      if (id === 'filter-search') currentFilters.search = e.target.value;

      if (currentView === 'overview') showOverview();
      else if (currentView === 'list') renderListRows();
    });
  });
}

function showOverview() {
  cancelEditCleanup();
  currentView = 'overview';
  setActiveNav('overview');

  var newUrl = new URL(window.location);
  newUrl.searchParams.delete('project');
  newUrl.searchParams.delete('id');
  window.history.replaceState({}, '', newUrl);

  var filtered = getFilteredProjects();
  syncMapMarkers(filtered);

  var totalFunding = filtered.reduce(function (s, p) { return s + (Number(p.amount) || Number(p.budget) || 0); }, 0);
  var ggCount = filtered.filter(function (p) { return getProjectType(p) === 'Global Grant'; }).length;
  var directCount = filtered.filter(function (p) { return getProjectType(p) !== 'Global Grant'; }).length;

  var isFiltered = currentFilters.type || currentFilters.status || currentFilters.category || currentFilters.year || currentFilters.search;
  var filterNotice = isFiltered ? '<span style="font-size:12px;color:#d97706;font-weight:normal;"> (Filtered: ' + filtered.length + ' of ' + allProjects.length + ')</span>' : '';

  var rp = document.getElementById('right-pane');
  rp.innerHTML = ''
    + '<div class="panel" id="overview-panel">'
    + '  <h2>Club Projects Overview ' + filterNotice + '</h2>'
    +    renderFilterBar()
    + '  <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:14px;line-height:1.7;margin-bottom:16px;">'
    + '    <p>The Rotary Club of Lake Atitlán funds community development projects across Guatemala through Global Grants, District Grants, Club-to-Club collaborations, and direct club donations.</p>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:10px;margin-bottom:16px;">'
    + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
    + '      <div id="ov-total-count" style="font-size:22px;font-weight:bold;color:#1a3a5c;">' + filtered.length + '</div>'
    + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Projects in View</div>'
    + '    </div>'
    + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
    + '      <div id="ov-total-funding" style="font-size:22px;font-weight:bold;color:#1a3a5c;">$' + (totalFunding / 1e6).toFixed(2) + 'M</div>'
    + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Funding in View</div>'
    + '    </div>'
    + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
    + '      <div id="ov-split-count" style="font-size:22px;font-weight:bold;color:#1a3a5c;">' + ggCount + ' / ' + directCount + '</div>'
    + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Global Grants / Direct & Other</div>'
    + '    </div>'
    + '  </div>'
    + '  <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:14px;margin-bottom:14px;">'
    + '    <h3 style="margin-top:0;">Project Types Breakdown</h3>'
    + '    <div style="position:relative;height:220px;"><canvas id="chart-types"></canvas></div>'
    + '  </div>'
    + '</div>';

  attachFilterListeners();
  loadChartJS().then(function () { renderTypeChart(filtered); });
}

function loadChartJS() {
  return new Promise(function (resolve) {
    if (window.Chart) { resolve(); return; }
    var s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';
    s.onload = resolve;
    document.head.appendChild(s);
  });
}

function renderTypeChart(filteredProjects) {
  var dataset = filteredProjects || getFilteredProjects();
  var typeMap = {};
  dataset.forEach(function (p) {
    var t = getProjectType(p);
    typeMap[t] = (typeMap[t] || 0) + 1;
  });

  var canvas = document.getElementById('chart-types');
  if (!canvas || !window.Chart) return;

  if (overviewChart) overviewChart.destroy();

  var labels = Object.keys(typeMap);
  var counts = Object.values(typeMap);

  overviewChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels.length ? labels : ['No Data'],
      datasets: [{
        data: counts.length ? counts : [1],
        backgroundColor: counts.length ? ['#1a3a5c', '#8b5cf6', '#059669', '#f59e0b', '#dc2626'] : ['#cbd5e1']
      }]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

function showList() {
  cancelEditCleanup();
  currentView = 'list';
  setActiveNav('list');

  var newUrl = new URL(window.location);
  newUrl.searchParams.delete('project');
  newUrl.searchParams.delete('id');
  window.history.replaceState({}, '', newUrl);

  var rp = document.getElementById('right-pane');
  rp.innerHTML = ''
    + '<div class="panel" id="list-panel">'
    + '  <h2>All Projects</h2>'
    +    renderFilterBar()
    + '  <table id="project-table">'
    + '    <thead>'
    + '      <tr>'
    + '        <th data-col="id">ID</th>'
    + '        <th data-col="title">Project</th>'
    + '        <th data-col="project_type">Type</th>'
    + '        <th data-col="category">Category</th>'
    + '        <th data-col="start_year">Year</th>'
    + '        <th data-col="status">Status</th>'
    + '        <th data-col="amount" style="text-align:right">Budget</th>'
    + '      </tr>'
    + '    </thead>'
    + '    <tbody id="project-tbody"></tbody>'
    + '  </table>'
    + '</div>';

  attachFilterListeners();
  renderListRows();
}

function renderListRows() {
  var filtered = getFilteredProjects();
  syncMapMarkers(filtered);
  var tbody = document.getElementById('project-tbody');
  if (!tbody) return;

  var rowsHtml = '';
  filtered.forEach(function (p) {
    var idx = allProjects.indexOf(p);
    var amt = p.amount ? '$' + Number(p.amount).toLocaleString() : (p.budget ? '$' + Number(p.budget).toLocaleString() : '—');
    var pStatus = (p.status || '').toLowerCase();
    rowsHtml += '<tr onclick="showDetail(' + idx + ')">'
      + '<td style="font-size:11px;color:#888;white-space:nowrap;"><strong>' + (p.id || p.grant_id) + '</strong></td>'
      + '<td>' + (p.title || 'Untitled') + '</td>'
      + '<td><span class="badge badge-type">' + getProjectType(p) + '</span></td>'
      + '<td>' + (p.category || '—') + '</td>'
      + '<td>' + (p.start_year || '—') + '</td>'
      + '<td><span class="badge badge-' + pStatus + '">' + (p.status || '—') + '</span></td>'
      + '<td style="text-align:right">' + amt + '</td>'
      + '</tr>';
  });
  tbody.innerHTML = rowsHtml;
}

function showDetail(idx) {
  cancelEditCleanup();
  currentView = 'detail';
  currentIndex = idx;
  setActiveNav('');
  highlightMarker(idx);

  var project = allProjects[idx];
  var gid = String(project.id || project.grant_id || '').trim();

  // Sync browser URL for deep-linking
  var newUrl = new URL(window.location);
  newUrl.searchParams.set('project', gid);
  newUrl.searchParams.delete('edit');
  newUrl.searchParams.delete('mode');
  window.history.replaceState({ projectId: gid }, '', newUrl);

  var pType = getProjectType(project);
  var rp = document.getElementById('right-pane');
  var amt = project.amount ? '$' + Number(project.amount).toLocaleString() : (project.budget ? '$' + Number(project.budget).toLocaleString() : '—');
  var rawText = getProjectSummaryText(project);
  var pStatus = (project.status || '').toLowerCase();

  var editBtn = isMaintenanceMode
    ? '<button type="button" onclick="openEditForm(' + idx + ')" style="background:#d97706;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">✏️ Edit Project</button>'
    : '';

  rp.innerHTML = ''
    + '<div class="panel" id="detail-panel" tabindex="0" style="outline:none;">'
    + '  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">'
    + '    <div style="flex:1">'
    + '      <h2 style="border:none;padding:0;margin-bottom:4px;">' + (project.title || 'Untitled') + '</h2>'
    + '      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
    + '        <span class="badge badge-type">' + pType + '</span>'
    + '        <span class="badge badge-' + pStatus + '">' + (project.status || '—') + '</span>'
    + '        <span style="color:#888;font-size:12px;">' + gid + '</span>'
    + '        <span style="color:#888;font-size:12px;">' + (project.start_year || '') + '</span>'
    + '      </div>'
    + '    </div>'
    + '    <div style="display:flex;gap:6px;">'
    +        editBtn
    + '      <button type="button" onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;">← All Projects</button>'
    + '    </div>'
    + '  </div>'
    + '  <div id="photo-area"></div>'
    + '  <h3 style="margin-top:16px;margin-bottom:6px;">Summary & Narrative</h3>'
    + '  <div class="narrative" id="narrative-body" data-raw="' + encodeURIComponent(rawText) + '" style="padding:10px;background:#fff;border:1px solid #ddd;border-radius:6px;line-height:1.6;">'
    +      (rawText || 'No narrative available yet.')
    + '  </div>'
    + '  <h3>Project Details & Financials</h3>'
    + '  <div class="meta-grid">'
    + '    <div class="meta-item"><label>Budget / Amount</label><span>' + amt + '</span></div>'
    + '    <div class="meta-item"><label>Project Type</label><span>' + pType + '</span></div>'
    + '    <div class="meta-item"><label>Category</label><span>' + (project.category || '—') + '</span></div>'
    + '    <div class="meta-item"><label>Shepherd</label><span>' + (project.shepard || project.shepherd || '—') + '</span></div>'
    + '    <div class="meta-item"><label>Key Partner</label><span>' + (project.partner || '—') + '</span></div>'
    + '    <div class="meta-item"><label>Beneficiaries</label><span>' + (project.beneficiaries || '—') + '</span></div>'
    + '  </div>'
    + '  <div id="files-area"></div>'
    + '</div>';

  setTimeout(function () { loadProjectFiles(gid, 'photo-area', 'files-area'); }, 0);
  renderMarkdown();
}

function loadProjectFiles(projectId, photoContainerId, docContainerId) {
  if (!projectId) return;

  var p = allProjects.find(function (item) {
    return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
  });

  if (p && (p.project_assets !== undefined || p.project_links !== undefined)) {
    renderFilesAndLinksFromProject(p, photoContainerId, docContainerId);
    return;
  }

  fetch('projects/' + encodeURIComponent(projectId) + '/files.json')
    .then(function (r) {
      if (r.ok) return r.json();
      return fetch(BACKEND_URL + '/projects/' + encodeURIComponent(projectId) + '/files.json').then(function (b) {
        return b.ok ? b.json() : { files: [], links: [] };
      });
    })
    .catch(function () { return { files: [], links: [] }; })
    .then(function (manifest) { renderFilesAndLinks(manifest, projectId, photoContainerId, docContainerId); });
}

function renderFilesAndLinksFromProject(project, photoContainerId, docContainerId) {
  var assets = project.project_assets || [];
  var links = project.project_links || [];

  var images = assets.filter(function (a) {
    return a.file_type === 'image' || /\.(jpg|jpeg|png|gif|webp)$/i.test(a.filename);
  });
  var docs = assets.filter(function (a) {
    return a.file_type !== 'image' && !/\.(jpg|jpeg|png|gif|webp)$/i.test(a.filename);
  });

  var photoArea = photoContainerId ? document.getElementById(photoContainerId) : null;
  var filesArea = docContainerId ? document.getElementById(docContainerId) : null;

  if (photoArea) {
    if (images.length > 0) {
      photoArea.innerHTML = '<div class="photo-carousel">' +
        images.map(function (a) {
          var src = a.public_url || ('projects/' + encodeURIComponent(project.id) + '/' + encodeURIComponent(a.filename));
          return '<img src="' + src + '" alt="' + escapeHtml(a.filename) + '" '
               + 'onclick="window.open(this.src,\'_blank\')">';
        }).join('') +
        '</div>';
    } else {
      photoArea.innerHTML = '';
    }
  }

  if (filesArea) {
    if (docs.length > 0 || links.length > 0) {
      filesArea.innerHTML = '<h3>Attached Documents & Web Links</h3><div class="files-section" id="files-list-' + docContainerId + '"></div>';
      var list = document.getElementById('files-list-' + docContainerId);
      docs.forEach(function (a) {
        var link = document.createElement('a');
        link.href = a.public_url || ('projects/' + encodeURIComponent(project.id) + '/' + encodeURIComponent(a.filename));
        link.target = '_blank';
        var icon = a.file_type === 'video' ? '🎬' : '📄';
        link.innerHTML = '<span class="file-icon">' + icon + '</span> ' + escapeHtml(a.filename);
        list.appendChild(link);
      });
      links.forEach(function (l) {
        var a = document.createElement('a');
        a.href = l.url;
        a.target = '_blank';
        a.innerHTML = '<span class="file-icon">🔗</span> ' + escapeHtml(l.label || l.url);
        list.appendChild(a);
      });
    } else {
      filesArea.innerHTML = '';
    }
  }
}

function renderFilesAndLinks(manifest, projectId, photoContainerId, docContainerId) {
  var rawFiles = manifest.files || [];
  var links = manifest.links || [];

  var files = rawFiles.map(function (f) {
    if (typeof f === 'string') return f;
    if (f && typeof f === 'object') return f.filename || f.name || '';
    return '';
  }).filter(Boolean);

  var images = files.filter(function (f) { return /\.(jpg|jpeg|png|gif|webp)$/i.test(f); });
  var docs   = files.filter(function (f) { return !/\.(jpg|jpeg|png|gif|webp)$/i.test(f); });

  var photoArea = photoContainerId ? document.getElementById(photoContainerId) : null;
  var filesArea = docContainerId ? document.getElementById(docContainerId) : null;

  if (photoArea) {
    if (images.length > 0) {
      photoArea.innerHTML = '<div class="photo-carousel">' +
        images.map(function (f) {
          var src = 'projects/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(f);
          return '<img src="' + src + '" alt="' + escapeHtml(f) + '" '
               + 'onerror="this.src=\'' + BACKEND_URL + '/' + src + '\'; this.onerror=null;" '
               + 'onclick="window.open(this.src,\'_blank\')">';
        }).join('') +
        '</div>';
    } else {
      photoArea.innerHTML = '';
    }
  }

  if (filesArea) {
    if (docs.length > 0 || links.length > 0) {
      filesArea.innerHTML = '<h3>Attached Documents & Web Links</h3><div class="files-section" id="files-list-' + docContainerId + '"></div>';
      var list = document.getElementById('files-list-' + docContainerId);
      docs.forEach(function (f) {
        var a = document.createElement('a');
        a.href = 'projects/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(f);
        a.target = '_blank';
        a.innerHTML = '<span class="file-icon">📄</span> ' + escapeHtml(f);
        list.appendChild(a);
      });
      links.forEach(function (l) {
        var a = document.createElement('a');
        a.href = l.url;
        a.target = '_blank';
        a.innerHTML = '<span class="file-icon">🔗</span> ' + escapeHtml(l.label || l.url);
        list.appendChild(a);
      });
    } else {
      filesArea.innerHTML = '';
    }
  }
}

function renderMarkdown() {
  var el = document.getElementById('narrative-body');
  if (!el) return;
  var raw = el.dataset.raw ? decodeURIComponent(el.dataset.raw) : '';
  if (!raw.trim()) {
    el.innerHTML = '<span style="color:#94a3b8;font-style:italic;">No narrative available yet.</span>';
    return;
  }
  loadMarked().then(function () { el.innerHTML = marked.parse(raw); });
}

function loadMarked() {
  return new Promise(function (resolve) {
    if (window.marked) { resolve(); return; }
    var s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js';
    s.onload = resolve;
    document.head.appendChild(s);
  });
}

// ============================================================
// EDIT PROJECT FORM & INTERACTIVE ASSET MANAGEMENT
// ============================================================
window.openEditForm = function (idx) {
  cancelEditCleanup();
  activeEditIdx = Number(idx);
  var p = allProjects[activeEditIdx];
  if (!p) return;

  var gid = String(p.id || p.grant_id || '').trim();
  var coords = getProjectCoords(p) || { lat: 14.703454, lng: -91.191623 };
  var rp = document.getElementById('right-pane');
  var pType = getProjectType(p);
  var initialText = getProjectSummaryText(p);

  // Sync URL for direct link to edit
  var newUrl = new URL(window.location);
  newUrl.searchParams.set('project', gid);
  newUrl.searchParams.set('edit', 'true');
  window.history.replaceState({ projectId: gid, edit: true }, '', newUrl);

  var optDirect = pType === 'Club Direct / Donation' ? 'selected' : '';
  var optDG = pType === 'District Grant' ? 'selected' : '';
  var optC2C = pType === 'Club-to-Club Grant' ? 'selected' : '';
  var optGG = pType === 'Global Grant' ? 'selected' : '';

  rp.innerHTML = ''
    + '<div class="panel" id="edit-panel">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:2px solid #d97706;padding-bottom:6px;">'
    + '    <h2 style="border:none;padding:0;margin:0;color:#d97706;">✏️ Edit Project & Media</h2>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" onclick="showDetail(' + activeEditIdx + ')" style="padding:5px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>'
    + '      <button type="button" id="btn-save-project" onclick="saveProjectEdits()" style="padding:5px 14px;border:none;background:#059669;color:white;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">Save Changes</button>'
    + '    </div>'
    + '  </div>'
    + '  <div style="background:#eff6ff;border:1px solid #bfdbfe;padding:8px 12px;border-radius:6px;font-size:12px;color:#1e40af;margin-bottom:12px;">'
    + '    📍 <strong>Map Pinning Active:</strong> Drag the marker on the map or click anywhere on the map to set coordinates.'
    + '  </div>'
    + '  <div id="edit-photo-area"></div>'
    + '  <div style="margin-bottom:12px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Manage Staged Photos & Files</label>'
    + '    <div id="modal-existing-files">Loading assets…</div>'
    + '  </div>'
    + '  <div id="paste-status-banner" style="display:none;background:#fef3c7;border:1px solid #fde047;padding:8px 12px;border-radius:4px;font-size:12px;color:#854d0e;margin-bottom:10px;"></div>'
    + '  <div class="paste-drop-zone" onclick="document.getElementById(\'modal-file-upload\').click()">'
    + '    📋 <strong>Paste Images (Ctrl+V) or Click to Upload:</strong> Press <code>Ctrl+V</code> anywhere on this page to paste, or click here to browse files.'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project ID / Grant Number *</label>'
    + '      <input type="text" id="edit-id" value="' + escapeHtml(gid) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-weight:bold;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project Type</label>'
    + '      <select id="edit-type" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:white;">'
    + '        <option value="Club Direct / Donation" ' + optDirect + '>Club Direct / Donation</option>'
    + '        <option value="District Grant" ' + optDG + '>District Grant</option>'
    + '        <option value="Club-to-Club Grant" ' + optC2C + '>Club-to-Club Grant</option>'
    + '        <option value="Global Grant" ' + optGG + '>Global Grant</option>'
    + '      </select>'
    + '    </div>'
    + '  </div>'
    + '  <div style="margin-bottom:10px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project Title</label>'
    + '    <input type="text" id="edit-title" value="' + escapeHtml(p.title || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Budget / Amount ($)</label>'
    + '      <input type="number" id="edit-amount" value="' + escapeHtml(p.amount || p.budget || 0) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Start Year</label>'
    + '      <input type="text" id="edit-year" value="' + escapeHtml(p.start_year || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Status</label>'
    + '      <input type="text" id="edit-status" value="' + escapeHtml(p.status || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Category</label>'
    + '      <input type="text" id="edit-category" value="' + escapeHtml(p.category || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Latitude</label>'
    + '      <input type="text" id="edit-lat" value="' + coords.lat.toFixed(6) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Longitude</label>'
    + '      <input type="text" id="edit-lng" value="' + coords.lng.toFixed(6) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Shepherd</label>'
    + '      <input type="text" id="edit-shepard" value="' + escapeHtml(p.shepard || p.shepherd || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Key Partner</label>'
    + '      <input type="text" id="edit-partner" value="' + escapeHtml(p.partner || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Narrative & Field Notes</label>'
    + '  <textarea id="edit-narrative" style="width:100%;height:200px;font-family:monospace;padding:8px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;line-height:1.5;">' + escapeHtml(initialText) + '</textarea>'
    + '  <div style="margin-top:14px;margin-bottom:14px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Web Links</label>'
    + '    <div id="modal-links-list"></div>'
    + '    <button type="button" onclick="addLinkInput()" style="margin-top:4px;padding:4px 8px;font-size:11px;cursor:pointer;background:#e2e8f0;border:none;border-radius:4px;">+ Add Link</button>'
    + '  </div>'
    + '  <div style="margin-bottom:20px;">'
    + '    <input type="file" id="modal-file-upload" multiple style="display:none;" onchange="handleFileInputUpload(event, \'' + gid + '\')">'
    + '  </div>'
    + '</div>';

  loadProjectFiles(gid, 'edit-photo-area', null);
  loadEditFiles(gid);
  attachActiveWindowPaste(gid);

  var linksLoaded = false;
  if (p.project_links && p.project_links.length > 0) {
    p.project_links.forEach(function (l) { addLinkInput(l.label, l.url); });
    linksLoaded = true;
  } else if (supabaseClient) {
    supabaseClient
      .from('project_links')
      .select('*')
      .eq('project_id', gid)
      .order('display_order', { ascending: true })
      .then(function (res) {
        if (!res.error && res.data && res.data.length > 0) {
          res.data.forEach(function (l) { addLinkInput(l.label, l.url); });
        } else {
          addLinkInput();
        }
      })
      .catch(function () { addLinkInput(); });
    linksLoaded = true;
  }

  if (!linksLoaded) {
    fetch('projects/' + encodeURIComponent(gid) + '/files.json')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.links && data.links.length > 0) {
          data.links.forEach(function (l) { addLinkInput(l.label, l.url); });
        } else {
          addLinkInput();
        }
      })
      .catch(function () { addLinkInput(); });
  }

  setupLocationPicker(coords);
};

// Global active paste listener while edit view is mounted
function attachActiveWindowPaste(projectId) {
  if (globalPasteAbortCtrl) {
    globalPasteAbortCtrl.abort();
  }
  globalPasteAbortCtrl = new AbortController();

  window.addEventListener('paste', function (e) {
    var clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData || !clipboardData.items) return;

    for (var i = 0; i < clipboardData.items.length; i++) {
      var item = clipboardData.items[i];
      if (item.type && item.type.startsWith('image/')) {
        var blob = item.getAsFile();
        if (blob) {
          e.preventDefault();
          uploadImageBlobInEdit(blob, projectId);
          return;
        }
      }
    }
  }, { signal: globalPasteAbortCtrl.signal });
}

function uploadImageBlobInEdit(blob, projectId) {
  if (isUploadingImage) return;
  isUploadingImage = true;

  var timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  var ext = (blob.type && blob.type.split('/')[1]) || 'png';
  if (ext === 'jpeg') ext = 'jpg';
  var filename = 'paste_' + timestamp + '.' + ext;
  var file = new File([blob], filename, { type: blob.type || 'image/png' });

  var banner = document.getElementById('paste-status-banner');
  if (banner) {
    banner.style.display = 'block';
    banner.textContent = '⏳ Uploading image: ' + filename + '...';
  }

  function handleSuccess(insertedUrl) {
    var textarea = document.getElementById('edit-narrative');
    if (textarea) {
      var tag = '\n\n![' + filename + '](' + insertedUrl + ')\n\n';
      var start = textarea.selectionStart || textarea.value.length;
      var end = textarea.selectionEnd || textarea.value.length;
      textarea.value = textarea.value.substring(0, start) + tag + textarea.value.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + tag.length;
    }

    if (banner) {
      banner.textContent = '✅ Image uploaded and inserted into narrative!';
      setTimeout(function () { banner.style.display = 'none'; }, 3000);
    }
    loadProjectFiles(projectId, 'edit-photo-area', null);
    loadEditFiles(projectId);
    isUploadingImage = false;
  }

  if (supabaseClient) {
    var storagePath = projectId + '/' + filename;
    supabaseClient.storage
      .from('project-media')
      .upload(storagePath, file, { upsert: true, contentType: file.type || 'image/png' })
      .then(function (upRes) {
        if (upRes.error) throw upRes.error;
        var pubData = supabaseClient.storage.from('project-media').getPublicUrl(storagePath);
        var publicUrl = (pubData && pubData.data && pubData.data.publicUrl) || '';

        return supabaseClient
          .from('project_assets')
          .insert({
            project_id: projectId,
            filename: filename,
            file_type: 'image',
            mime_type: file.type || 'image/png',
            storage_path: storagePath,
            public_url: publicUrl
          })
          .select()
          .then(function (assetRes) {
            var p = allProjects.find(function (item) {
              return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
            });
            if (p) {
              if (!p.project_assets) p.project_assets = [];
              if (assetRes && assetRes.data && assetRes.data[0]) {
                p.project_assets.push(assetRes.data[0]);
              } else {
                p.project_assets.push({ filename: filename, public_url: publicUrl, file_type: 'image' });
              }
            }
            handleSuccess(publicUrl);
          });
      })
      .catch(function (err) {
        console.warn('Supabase image upload failed, falling back to local backend:', err);
        uploadViaBackend();
      });
  } else {
    uploadViaBackend();
  }

  function uploadViaBackend() {
    var fd = new FormData();
    fd.append('file', file);
    fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/upload', {
      method: 'POST',
      body: fd
    })
    .then(function (res) {
      if (!res.ok) throw new Error('Server returned ' + res.status);
      return res.json();
    })
    .then(function () {
      handleSuccess('projects/' + projectId + '/' + filename);
    })
    .catch(function (err) {
      if (banner) banner.textContent = '❌ Upload failed: ' + err.message;
      isUploadingImage = false;
    });
  }
}

async function loadEditFiles(projectId) {
  var container = document.getElementById('modal-existing-files');
  if (!container) return;

  var assets = [];

  if (supabaseClient) {
    try {
      var dbRes = await supabaseClient
        .from('project_assets')
        .select('*')
        .eq('project_id', projectId)
        .order('created_at', { ascending: true });
      if (!dbRes.error && dbRes.data && dbRes.data.length > 0) {
        assets = dbRes.data;
      }
    } catch (e) {
      console.warn('Could not query project_assets from Supabase:', e);
    }
  }

  if (assets.length === 0) {
    var p = allProjects.find(function (item) {
      return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
    });
    if (p && p.project_assets && p.project_assets.length > 0) {
      assets = p.project_assets;
    }
  }

  if (assets.length === 0) {
    try {
      var res = await fetch('projects/' + encodeURIComponent(projectId) + '/files.json');
      if (!res.ok) {
        res = await fetch(BACKEND_URL + '/projects/' + encodeURIComponent(projectId) + '/files.json');
      }
      var data = await res.json();
      var rawFiles = data.files || [];
      assets = rawFiles.map(function (f) {
        var fn = typeof f === 'string' ? f : (f.filename || f.name || '');
        return { filename: fn };
      }).filter(function (a) { return Boolean(a.filename); });
    } catch (e) {}
  }

  if (assets.length === 0) {
    container.innerHTML = '<div style="color:#888;font-size:12px;font-style:italic;">No files or photos uploaded yet.</div>';
    return;
  }

  var html = '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:4px;">';
  assets.forEach(function (a, i) {
    var fn = a.filename || '';
    var isImg = a.file_type === 'image' || /\.(jpg|jpeg|png|gif|webp)$/i.test(fn);
    var isVid = a.file_type === 'video' || /\.(mp4|mov|webm)$/i.test(fn);
    var elemId = 'file-thumb-' + i;
    var src = a.public_url || ('projects/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(fn));

    var mediaTag = isImg
      ? '<img src="' + src + '" onerror="this.src=\'' + BACKEND_URL + '/' + src + '\'; this.onerror=null;" style="width:100%;height:60px;object-fit:cover;border-radius:2px;">'
      : isVid
        ? '<div style="font-size:28px;line-height:60px;">🎬</div>'
        : '<div style="font-size:28px;line-height:60px;">📄</div>';

    html += '<div id="' + elemId + '" style="position:relative;border:1px solid #cbd5e1;border-radius:4px;padding:4px;background:#fff;width:90px;text-align:center;">'
          + mediaTag
          + '<div style="font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px;" title="' + escapeHtml(fn) + '">' + escapeHtml(fn) + '</div>'
          + '<button type="button" onclick="deleteProjectAsset(\'' + projectId + '\', \'' + escapeHtml(fn) + '\', \'' + elemId + '\')" style="position:absolute;top:-6px;right:-6px;background:#ef4444;color:white;border:none;border-radius:50%;width:18px;height:18px;font-size:10px;cursor:pointer;line-height:18px;text-align:center;padding:0;" title="Delete file">✕</button>'
          + '</div>';
  });
  html += '</div>';

  container.innerHTML = html;
}

window.deleteProjectAsset = async function (projectId, filename, elementId) {
  if (!confirm('Are you sure you want to delete "' + filename + '"?')) return;

  var success = false;
  if (supabaseClient) {
    try {
      var storagePath = projectId + '/' + filename;
      var removeRes = await supabaseClient.storage.from('project-media').remove([storagePath]);
      if (removeRes.error) console.warn('Supabase storage remove warning:', removeRes.error);

      var delRes = await supabaseClient
        .from('project_assets')
        .delete()
        .match({ project_id: projectId, filename: filename });
      if (delRes.error) console.warn('Supabase project_assets delete warning:', delRes.error);

      var p = allProjects.find(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
      });
      if (p && p.project_assets) {
        p.project_assets = p.project_assets.filter(function (a) { return a.filename !== filename; });
      }
      success = true;
    } catch (err) {
      console.warn('Supabase asset delete failed, trying backend fallback:', err);
    }
  }

  if (!success) {
    try {
      var res = await fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/files/' + encodeURIComponent(filename), {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Server returned ' + res.status);
      success = true;
    } catch (err) {
      alert('Error deleting file: ' + err.message);
      return;
    }
  }

  var el = document.getElementById(elementId);
  if (el) el.remove();
  loadProjectFiles(projectId, 'edit-photo-area', null);
};

function handleFileInputUpload(event, projectId) {
  var files = event.target.files;
  if (!files || files.length === 0) return;

  var banner = document.getElementById('paste-status-banner');
  if (banner) {
    banner.style.display = 'block';
    banner.textContent = '⏳ Uploading ' + files.length + ' file(s)...';
  }

  var fileList = Array.from(files);

  if (supabaseClient) {
    var uploads = fileList.map(function (file) {
      var filename = file.name;
      var storagePath = projectId + '/' + filename;
      var ext = (filename.split('.').pop() || '').toLowerCase();
      var fileType = 'image';
      if (['mp4', 'mov', 'webm'].indexOf(ext) !== -1) fileType = 'video';
      else if (['pdf', 'doc', 'docx', 'txt'].indexOf(ext) !== -1) fileType = 'document';

      return supabaseClient.storage
        .from('project-media')
        .upload(storagePath, file, { upsert: true, contentType: file.type || 'application/octet-stream' })
        .then(function (upRes) {
          if (upRes.error) throw upRes.error;
          var pubData = supabaseClient.storage.from('project-media').getPublicUrl(storagePath);
          var publicUrl = (pubData && pubData.data && pubData.data.publicUrl) || '';

          return supabaseClient
            .from('project_assets')
            .delete()
            .match({ project_id: projectId, filename: filename })
            .then(function () {
              return supabaseClient
                .from('project_assets')
                .insert({
                  project_id: projectId,
                  filename: filename,
                  file_type: fileType,
                  mime_type: file.type || 'application/octet-stream',
                  storage_path: storagePath,
                  public_url: publicUrl
                })
                .select();
            })
            .then(function (assetRes) {
              var p = allProjects.find(function (item) {
                return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
              });
              if (p) {
                if (!p.project_assets) p.project_assets = [];
                p.project_assets = p.project_assets.filter(function (a) { return a.filename !== filename; });
                if (assetRes && assetRes.data && assetRes.data[0]) {
                  p.project_assets.push(assetRes.data[0]);
                } else {
                  p.project_assets.push({
                    filename: filename,
                    public_url: publicUrl,
                    file_type: fileType
                  });
                }
              }
            });
        });
    });

    Promise.all(uploads)
      .then(function () {
        if (banner) {
          banner.textContent = '✅ Files uploaded successfully!';
          setTimeout(function () { banner.style.display = 'none'; }, 3000);
        }
        loadProjectFiles(projectId, 'edit-photo-area', null);
        loadEditFiles(projectId);
      })
      .catch(function (err) {
        console.warn('Supabase multi-upload failed, trying backend fallback:', err);
        fallbackBackendUpload();
      });
  } else {
    fallbackBackendUpload();
  }

  function fallbackBackendUpload() {
    var backendUploads = fileList.map(function (file) {
      var fd = new FormData();
      fd.append('file', file);
      return fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/upload', {
        method: 'POST',
        body: fd
      });
    });

    Promise.all(backendUploads)
      .then(function () {
        if (banner) {
          banner.textContent = '✅ Files uploaded successfully!';
          setTimeout(function () { banner.style.display = 'none'; }, 3000);
        }
        loadProjectFiles(projectId, 'edit-photo-area', null);
        loadEditFiles(projectId);
      })
      .catch(function (err) {
        if (banner) banner.textContent = '❌ Upload failed: ' + err.message;
      });
  }
}

function setupLocationPicker(initialCoords) {
  if (map && window.google && google.maps) {
    if (editMarker) editMarker.setMap(null);
    editMarker = new google.maps.Marker({
      position: initialCoords,
      map: map,
      draggable: true,
      animation: google.maps.Animation.DROP,
      zIndex: 1000000
    });

    editMarker.addListener('drag', function (e) {
      var latEl = document.getElementById('edit-lat');
      var lngEl = document.getElementById('edit-lng');
      if (latEl) latEl.value = e.latLng.lat().toFixed(6);
      if (lngEl) lngEl.value = e.latLng.lng().toFixed(6);
    });

    if (mapClickListener) google.maps.event.removeListener(mapClickListener);
    mapClickListener = map.addListener('click', function (e) {
      if (editMarker) editMarker.setPosition(e.latLng);
      var latEl = document.getElementById('edit-lat');
      var lngEl = document.getElementById('edit-lng');
      if (latEl) latEl.value = e.latLng.lat().toFixed(6);
      if (lngEl) lngEl.value = e.latLng.lng().toFixed(6);
    });

    map.panTo(initialCoords);
  }
}

function cancelEditCleanup() {
  if (globalPasteAbortCtrl) {
    globalPasteAbortCtrl.abort();
    globalPasteAbortCtrl = null;
  }
  if (editMarker) {
    editMarker.setMap(null);
    editMarker = null;
  }
  if (searchMarker) {
    searchMarker.setMap(null);
    searchMarker = null;
  }
  if (mapClickListener && window.google && google.maps) {
    google.maps.event.removeListener(mapClickListener);
    mapClickListener = null;
  }
}

window.addLinkInput = function (label, url) {
  label = label || '';
  url = url || '';
  var container = document.getElementById('modal-links-list');
  if (!container) return;
  var div = document.createElement('div');
  div.className = 'link-row';
  div.style.cssText = 'display:flex;gap:8px;margin-bottom:6px;';
  div.innerHTML = ''
    + '<input type="text" placeholder="Label" value="' + escapeHtml(label) + '" style="width:35%;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
    + '<input type="text" placeholder="https://..." value="' + escapeHtml(url) + '" style="flex:1;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
    + '<button type="button" onclick="this.parentElement.remove()" style="background:#ef4444;color:white;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;">✕</button>';
  container.appendChild(div);
};

function saveProjectEdits() {
  var p = allProjects[activeEditIdx];
  if (!p) return;
  var oldGid = String(p.id || p.grant_id || '').trim();
  var btn = document.getElementById('btn-save-project');
  if (btn) { btn.textContent = 'Saving...'; btn.disabled = true; }

  var latVal = (document.getElementById('edit-lat') && document.getElementById('edit-lat').value) || '';
  var lngVal = (document.getElementById('edit-lng') && document.getElementById('edit-lng').value) || '';
  var newGid = (document.getElementById('edit-id') && document.getElementById('edit-id').value.trim()) || oldGid;
  var newAmt = (document.getElementById('edit-amount') && document.getElementById('edit-amount').value) || '0';
  var newYear = (document.getElementById('edit-year') && document.getElementById('edit-year').value) || '';
  var parsedLat = parseFloat(latVal);
  var parsedLng = parseFloat(lngVal);
  var numAmt = parseFloat(newAmt) || 0;
  var intYear = parseInt(newYear, 10) || null;
  var shepherdVal = (document.getElementById('edit-shepard') && document.getElementById('edit-shepard').value) || '';

  var links = [];
  document.querySelectorAll('#modal-links-list .link-row').forEach(function (r) {
    var inputs = r.querySelectorAll('input');
    if (inputs[0].value.trim() && inputs[1].value.trim()) {
      links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
    }
  });

  if (supabaseClient) {
    var supabasePayload = {
      id: newGid,
      title: (document.getElementById('edit-title') && document.getElementById('edit-title').value) || '',
      project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
      status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || '',
      category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || '',
      budget: numAmt,
      start_year: intYear,
      shepherd: shepherdVal,
      partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
      narrative: (document.getElementById('edit-narrative') && document.getElementById('edit-narrative').value) || '',
      position_lat: !isNaN(parsedLat) ? parsedLat : null,
      position_lng: !isNaN(parsedLng) ? parsedLng : null
    };

    var promise;
    if (newGid !== oldGid) {
      promise = supabaseClient.from('projects').insert(supabasePayload).then(function (res) {
        if (res.error) throw res.error;
        return supabaseClient.from('projects').delete().eq('id', oldGid);
      });
    } else {
      promise = supabaseClient.from('projects').upsert(supabasePayload);
    }

    promise
      .then(function (res) {
        if (res && res.error) throw res.error;
        return supabaseClient.from('project_links').delete().eq('project_id', newGid);
      })
      .then(function () {
        if (links.length > 0) {
          var linksPayload = links.map(function (l, idx) {
            return {
              project_id: newGid,
              label: l.label,
              url: l.url,
              display_order: idx
            };
          });
          return supabaseClient.from('project_links').insert(linksPayload);
        }
      })
      .then(function () {
        cancelEditCleanup();
        return loadData();
      })
      .then(function (projects) {
        allProjects = projects;
        rebuildMarkers();
        var targetIdx = allProjects.findIndex(function (item) {
          return String(item.id || item.grant_id || '').trim().toLowerCase() === newGid.toLowerCase();
        });
        showDetail(targetIdx !== -1 ? targetIdx : (activeEditIdx >= 0 ? activeEditIdx : 0));
      })
      .catch(function (err) {
        console.warn('Supabase save error, attempting backend fallback:', err);
        saveViaBackendFallback();
      })
      .finally(function () {
        if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
      });
  } else {
    saveViaBackendFallback();
  }

  function saveViaBackendFallback() {
    var updates = {
      id: newGid,
      title: (document.getElementById('edit-title') && document.getElementById('edit-title').value) || '',
      project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
      status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || '',
      shepard: shepherdVal,
      shepherd: shepherdVal,
      category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || '',
      amount: newAmt,
      budget: newAmt,
      start_year: newYear,
      partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
      narrative: (document.getElementById('edit-narrative') && document.getElementById('edit-narrative').value) || '',
      position_lat: latVal,
      position_lng: lngVal
    };

    fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(oldGid), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    })
    .then(function (res) {
      if (!res.ok) return res.json().then(function (err) { throw new Error(err.detail || 'Server error'); });
      return fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(newGid) + '/links', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ links: links })
      });
    })
    .then(function () {
      cancelEditCleanup();
      return loadData();
    })
    .then(function (projects) {
      allProjects = projects;
      rebuildMarkers();
      var targetIdx = allProjects.findIndex(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === newGid.toLowerCase();
      });
      showDetail(targetIdx !== -1 ? targetIdx : (activeEditIdx >= 0 ? activeEditIdx : 0));
    })
    .catch(function (err) { alert('Error updating project: ' + err.message); })
    .finally(function () {
      if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
    });
  }
}

window.openCreateForm = function () {
  cancelEditCleanup();
  activeEditIdx = -1;

  var currentYear = new Date().getFullYear();
  var defaultGid = 'CLUB_' + currentYear + '_NewProject';
  var defaultCoords = { lat: 14.703454, lng: -91.191623 };
  var rp = document.getElementById('right-pane');

  var newUrl = new URL(window.location);
  newUrl.searchParams.delete('project');
  newUrl.searchParams.delete('id');
  newUrl.searchParams.set('new', 'true');
  window.history.replaceState({}, '', newUrl);

  rp.innerHTML = ''
    + '<div class="panel" id="edit-panel">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:2px solid #8b5cf6;padding-bottom:6px;">'
    + '    <h2 style="border:none;padding:0;margin:0;color:#8b5cf6;">➕ Create New Project</h2>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" onclick="showOverview()" style="padding:5px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>'
    + '      <button type="button" id="btn-save-project" onclick="saveNewProject()" style="padding:5px 14px;border:none;background:#059669;color:white;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">Create Project</button>'
    + '    </div>'
    + '  </div>'
    + '  <div style="background:#eff6ff;border:1px solid #bfdbfe;padding:8px 12px;border-radius:6px;font-size:12px;color:#1e40af;margin-bottom:12px;">'
    + '    📍 <strong>Map Pinning Active:</strong> Drag the marker on the map or click anywhere on the map to set coordinates.'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project ID / Grant Number *</label>'
    + '      <input type="text" id="edit-id" value="' + escapeHtml(defaultGid) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-weight:bold;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project Type</label>'
    + '      <select id="edit-type" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:white;">'
    + '        <option value="Club Direct / Donation" selected>Club Direct / Donation</option>'
    + '        <option value="District Grant">District Grant</option>'
    + '        <option value="Club-to-Club Grant">Club-to-Club Grant</option>'
    + '        <option value="Global Grant">Global Grant</option>'
    + '      </select>'
    + '    </div>'
    + '  </div>'
    + '  <div style="margin-bottom:10px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project Title *</label>'
    + '    <input type="text" id="edit-title" placeholder="Project Title" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Budget / Amount ($)</label>'
    + '      <input type="number" id="edit-amount" value="0" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Start Year</label>'
    + '      <input type="text" id="edit-year" value="' + currentYear + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Status</label>'
    + '      <input type="text" id="edit-status" value="proposed" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Category</label>'
    + '      <input type="text" id="edit-category" value="Community Service" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Latitude</label>'
    + '      <input type="text" id="edit-lat" value="' + defaultCoords.lat.toFixed(6) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Longitude</label>'
    + '      <input type="text" id="edit-lng" value="' + defaultCoords.lng.toFixed(6) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Shepherd</label>'
    + '      <input type="text" id="edit-shepard" placeholder="Rotarian Shepherd" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Key Partner</label>'
    + '      <input type="text" id="edit-partner" placeholder="Partner organization" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Narrative & Field Notes</label>'
    + '  <textarea id="edit-narrative" style="width:100%;height:180px;font-family:monospace;padding:8px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;line-height:1.5;" placeholder="Enter narrative or project summary..."></textarea>'
    + '  <div style="margin-top:14px;margin-bottom:14px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Web Links</label>'
    + '    <div id="modal-links-list"></div>'
    + '    <button type="button" onclick="addLinkInput()" style="margin-top:4px;padding:4px 8px;font-size:11px;cursor:pointer;background:#e2e8f0;border:none;border-radius:4px;">+ Add Link</button>'
    + '  </div>'
    + '</div>';

  addLinkInput();
  setupLocationPicker(defaultCoords);
};

window.saveNewProject = function () {
  var btn = document.getElementById('btn-save-project');
  if (btn) { btn.textContent = 'Creating...'; btn.disabled = true; }

  var gid = (document.getElementById('edit-id') && document.getElementById('edit-id').value.trim());
  if (!gid) {
    alert('Please enter a Project ID / Grant Number.');
    if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
    return;
  }

  var title = (document.getElementById('edit-title') && document.getElementById('edit-title').value.trim()) || 'Untitled Project';
  var latVal = (document.getElementById('edit-lat') && document.getElementById('edit-lat').value) || '';
  var lngVal = (document.getElementById('edit-lng') && document.getElementById('edit-lng').value) || '';
  var newAmt = (document.getElementById('edit-amount') && document.getElementById('edit-amount').value) || '0';
  var newYear = (document.getElementById('edit-year') && document.getElementById('edit-year').value) || '';
  var parsedLat = parseFloat(latVal);
  var parsedLng = parseFloat(lngVal);
  var numAmt = parseFloat(newAmt) || 0;
  var intYear = parseInt(newYear, 10) || null;
  var shepherdVal = (document.getElementById('edit-shepard') && document.getElementById('edit-shepard').value) || '';

  var links = [];
  document.querySelectorAll('#modal-links-list .link-row').forEach(function (r) {
    var inputs = r.querySelectorAll('input');
    if (inputs[0].value.trim() && inputs[1].value.trim()) {
      links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
    }
  });

  if (supabaseClient) {
    var supabasePayload = {
      id: gid,
      title: title,
      project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
      status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || 'proposed',
      category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || 'Community Service',
      budget: numAmt,
      start_year: intYear,
      shepherd: shepherdVal,
      partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
      narrative: (document.getElementById('edit-narrative') && document.getElementById('edit-narrative').value) || '',
      position_lat: !isNaN(parsedLat) ? parsedLat : null,
      position_lng: !isNaN(parsedLng) ? parsedLng : null
    };

    supabaseClient
      .from('projects')
      .insert(supabasePayload)
      .then(function (res) {
        if (res.error) throw res.error;
        if (links.length > 0) {
          var linksPayload = links.map(function (l, idx) {
            return { project_id: gid, label: l.label, url: l.url, display_order: idx };
          });
          return supabaseClient.from('project_links').insert(linksPayload);
        }
      })
      .then(function () {
        cancelEditCleanup();
        return loadData();
      })
      .then(function (projects) {
        allProjects = projects;
        rebuildMarkers();
        var targetIdx = allProjects.findIndex(function (item) {
          return String(item.id || item.grant_id || '').trim().toLowerCase() === gid.toLowerCase();
        });
        showDetail(targetIdx !== -1 ? targetIdx : 0);
      })
      .catch(function (err) {
        alert('Error creating project: ' + err.message);
      })
      .finally(function () {
        if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
      });
  } else {
    var updates = {
      id: gid,
      title: title,
      project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
      status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || '',
      shepard: shepherdVal,
      shepherd: shepherdVal,
      category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || '',
      amount: newAmt,
      budget: newAmt,
      start_year: newYear,
      partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
      narrative: (document.getElementById('edit-narrative') && document.getElementById('edit-narrative').value) || '',
      position_lat: latVal,
      position_lng: lngVal
    };

    fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(gid), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    })
    .then(function (res) {
      if (!res.ok) return res.json().then(function (err) { throw new Error(err.detail || 'Server error'); });
      cancelEditCleanup();
      return loadData();
    })
    .then(function (projects) {
      allProjects = projects;
      rebuildMarkers();
      var targetIdx = allProjects.findIndex(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === gid.toLowerCase();
      });
      showDetail(targetIdx !== -1 ? targetIdx : 0);
    })
    .catch(function (err) { alert('Error creating project: ' + err.message); })
    .finally(function () {
      if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
    });
  }
};

window.showDiffModal = function () {
  var modal = document.getElementById('diff-modal');
  var container = document.getElementById('diff-output-container');
  var countLabel = document.getElementById('diff-file-count');
  if (!modal) return;
  modal.style.display = 'flex';
  if (container) container.innerHTML = 'Fetching repository diff...';

  fetch(BACKEND_URL + '/api/diff')
    .then(function (res) {
      if (!res.ok) throw new Error('Failed to retrieve diff');
      return res.json();
    })
    .then(function (data) {
      if (!container) return;
      if (data.status === 'clean') {
        container.innerHTML = '<span style="color:#94a3b8;">✔ Working tree is clean. No uncommitted modifications.</span>';
        if (countLabel) countLabel.textContent = '0 files changed';
        return;
      }

      var out = '';
      if (data.untracked && data.untracked.length > 0) {
        out += '<span style="color:#f59e0b;font-weight:bold;">Untracked New Files:</span>\n';
        data.untracked.forEach(function (f) {
          out += '<span class="diff-line-add">? ' + escapeHtml(f) + '</span>\n';
        });
        out += '\n';
      }

      var diffLines = (data.diff || '').split('\n');
      diffLines.forEach(function (line) {
        var escaped = escapeHtml(line);
        if (line.startsWith('+++') || line.startsWith('---')) {
          out += '<span style="color:#38bdf8;font-weight:bold;">' + escaped + '</span>\n';
        } else if (line.startsWith('+')) {
          out += '<span class="diff-line-add">' + escaped + '</span>\n';
        } else if (line.startsWith('-')) {
          out += '<span class="diff-line-del">' + escaped + '</span>\n';
        } else if (line.startsWith('@@')) {
          out += '<span class="diff-line-hunk">' + escaped + '</span>\n';
        } else {
          out += escaped + '\n';
        }
      });

      container.innerHTML = out || '<span style="color:#94a3b8;">No textual diff available.</span>';
      if (countLabel) countLabel.textContent = 'Status: ' + data.status;
    })
    .catch(function () {
      if (container) container.innerHTML = '<span style="color:#059669;">✔ Connected to Supabase Cloud. All edits are saved directly to PostgreSQL and Cloud Storage in real-time.</span>';
      if (countLabel) countLabel.textContent = 'Supabase Online';
    });
};

window.closeDiffModal = function () {
  var modal = document.getElementById('diff-modal');
  if (modal) modal.style.display = 'none';
};

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

function initMaintainerClient() {
  if (supabaseClient || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    isMaintenanceMode = true;
  }

  try {
    var evtSource = new EventSource(BACKEND_URL + '/api/logs');
    evtSource.onmessage = function (event) {
      var logDiv = document.getElementById('log-output');
      if (logDiv) {
        var newLine = document.createElement('div');
        newLine.className = 'log-line';
        newLine.textContent = event.data;
        logDiv.appendChild(newLine);
        logDiv.scrollTop = logDiv.scrollHeight;
      }
      pollMaintStatus();
    };

    evtSource.onerror = function () {
      if (!supabaseClient && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        isMaintenanceMode = false;
      }
      var badge = document.getElementById('sync-status-badge');
      if (badge) {
        badge.textContent = 'Sync: Local Offline';
        badge.style.background = '#64748b';
      }
    };
  } catch (e) {}

  setInterval(pollMaintStatus, 5000);
  pollMaintStatus();
}

function pollMaintStatus() {
  fetch(BACKEND_URL + '/api/status')
    .then(function (res) {
      if (!res.ok) throw new Error();
      return res.json();
    })
    .then(function (data) {
      isMaintenanceMode = true;
      var badge = document.getElementById('sync-status-badge');
      if (badge) {
        badge.textContent = 'Sync: ' + data.status.toUpperCase();
        badge.style.background = data.status === 'running' ? '#d97706' : data.status === 'error' ? '#dc2626' : '#059669';
      }
    })
    .catch(function () {
      var badge = document.getElementById('sync-status-badge');
      if (badge) {
        badge.textContent = 'Sync: Local Offline';
        badge.style.background = '#64748b';
      }
      if (supabaseClient) {
        isMaintenanceMode = true;
      } else if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        isMaintenanceMode = false;
      }
    });
}

window.triggerSync = function (dryRun) {
  if (dryRun === undefined) dryRun = true;
  window.toggleLogConsole(true);
  fetch(BACKEND_URL + '/api/sync?dry_run=' + dryRun, { method: 'POST' });
};

window.publishChanges = function () {
  var msg = prompt('Commit message:', 'chore(sync): automated grant update');
  if (!msg) return;
  fetch(BACKEND_URL + '/api/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg })
  })
  .then(function (res) { return res.json(); })
  .then(function (data) {
    alert(data.message || 'Published commit: ' + data.commit);
  })
  .catch(function () {
    alert('Publish failed. Check orchestrator logs.');
  });
};

window.toggleLogConsole = function (forceOpen) {
  var drawer = document.getElementById('log-drawer');
  if (drawer) drawer.style.display = forceOpen || drawer.style.display === 'none' ? 'block' : 'none';
};

function initDivider() {
  var divider = document.getElementById('divider');
  var mapPane = document.getElementById('map-pane');
  var app = document.getElementById('app');
  var dragging = false, startX = 0, startWidth = 0;

  divider.addEventListener('mousedown', function (e) {
    dragging = true;
    startX = e.clientX;
    startWidth = mapPane.getBoundingClientRect().width;
    divider.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', function (e) {
    if (!dragging) return;
    var appWidth = app.getBoundingClientRect().width;
    var newWidth = startWidth + (e.clientX - startX);
    var pct = Math.min(Math.max(newWidth / appWidth * 100, 15), 85);
    mapPane.style.flex = '0 0 ' + pct + '%';
  });

  document.addEventListener('mouseup', function () {
    if (!dragging) return;
    dragging = false;
    divider.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
}

if (window.google && window.google.maps) {
  window.initMap();
}
