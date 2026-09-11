// ============================================================
// RCLA Project Map — main.js
// Window-Level Image Paste + Edit Mode Asset Management
// ============================================================

const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://127.0.0.1:8000'
  : window.location.origin;
const CSV_PATH = 'RCLA_Projects_v2.csv';

// App Styles
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
      padding: 12px;
      text-align: center;
      background: #f8fafc;
      color: #475569;
      font-size: 12px;
      margin: 10px 0;
      cursor: pointer;
      user-select: none;
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
let isMaintenanceMode = true;
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
  return (Number.isFinite(lat) && Number.isFinite(lng)) ? { lat, lng } : null;
}

window.initMap = function () {
  initMaintainerClient();
  wireNavButtons();
  initDivider();

  loadData()
    .then(function (projects) {
      allProjects = projects;
      buildMap();
      showOverview();
    })
    .catch(function (err) {
      var rp = document.getElementById('right-pane');
      if (rp) rp.innerHTML = '<div style="padding:20px;color:red;">Error loading CSV: ' + err.message + '</div>';
    });
};

function loadData() {
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
  if (active) {
    active.setIcon('https://maps.google.com/mapfiles/ms/icons/red-dot.png');
    active.setZIndex(999);
    map.panTo(active.getPosition());
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
    + '  <input id="filter-search" name="project_search_query" type="text" placeholder="Search title, ID, partner…" value="' + escapeHtml(currentFilters.search) + '" style="flex:1;min-width:120px;">'
    + '</div>';
}

function attachFilterListeners() {
  ['filter-type', 'filter-status', 'filter-category', 'filter-year'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', function (e) {
      if (id === 'filter-type') currentFilters.type = e.target.value;
      if (id === 'filter-status') currentFilters.status = e.target.value;
      if (id === 'filter-category') currentFilters.category = e.target.value;
      if (id === 'filter-year') currentFilters.year = e.target.value;

      if (currentView === 'overview') updateOverviewMetricsOnly();
      else if (currentView === 'list') renderListRows();
    });
  });

  var searchInput = document.getElementById('filter-search');
  if (searchInput) {
    searchInput.addEventListener('input', function (e) {
      currentFilters.search = e.target.value;
      if (currentView === 'overview') updateOverviewMetricsOnly();
      else if (currentView === 'list') renderListRows();
    });
  }
}

function updateOverviewMetricsOnly() {
  var filtered = getFilteredProjects();
  syncMapMarkers(filtered);

  var totalFunding = filtered.reduce(function (s, p) { return s + (Number(p.amount) || Number(p.budget) || 0); }, 0);
  var ggCount = filtered.filter(function (p) { return getProjectType(p) === 'Global Grant'; }).length;
  var directCount = filtered.filter(function (p) { return getProjectType(p) !== 'Global Grant'; }).length;

  var countEl = document.getElementById('ov-total-count');
  var fundingEl = document.getElementById('ov-total-funding');
  var splitEl = document.getElementById('ov-split-count');
  var noticeEl = document.getElementById('ov-filter-notice');

  if (countEl) countEl.textContent = filtered.length;
  if (fundingEl) fundingEl.textContent = '$' + (totalFunding / 1e6).toFixed(2) + 'M';
  if (splitEl) splitEl.textContent = ggCount + ' / ' + directCount;

  var isFiltered = currentFilters.type || currentFilters.status || currentFilters.category || currentFilters.year || currentFilters.search;
  if (noticeEl) {
    noticeEl.textContent = isFiltered ? ' (Filtered: ' + filtered.length + ' of ' + allProjects.length + ')' : '';
  }

  renderTypeChart(filtered);
}

function showOverview() {
  cancelEditCleanup();
  currentView = 'overview';
  setActiveNav('overview');

  var filtered = getFilteredProjects();
  syncMapMarkers(filtered);

  var totalFunding = filtered.reduce(function (s, p) { return s + (Number(p.amount) || Number(p.budget) || 0); }, 0);
  var ggCount = filtered.filter(function (p) { return getProjectType(p) === 'Global Grant'; }).length;
  var directCount = filtered.filter(function (p) { return getProjectType(p) !== 'Global Grant'; }).length;

  var isFiltered = currentFilters.type || currentFilters.status || currentFilters.category || currentFilters.year || currentFilters.search;
  var filterNoticeText = isFiltered ? ' (Filtered: ' + filtered.length + ' of ' + allProjects.length + ')' : '';

  var rp = document.getElementById('right-pane');
  rp.innerHTML = ''
    + '<div class="panel" id="overview-panel">'
    + '  <h2>Club Projects Overview <span id="ov-filter-notice" style="font-size:12px;color:#d97706;font-weight:normal;">' + filterNoticeText + '</span></h2>'
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

// ============================================================
// READ-ONLY DETAIL VIEW
// ============================================================
function showDetail(idx) {
  cancelEditCleanup();
  currentView = 'detail';
  currentIndex = idx;
  setActiveNav('');
  highlightMarker(idx);

  var project = allProjects[idx];
  var gid = String(project.id || project.grant_id || '').trim();
  var pType = getProjectType(project);
  var rp = document.getElementById('right-pane');
  var amt = project.amount ? '$' + Number(project.amount).toLocaleString() : (project.budget ? '$' + Number(project.budget).toLocaleString() : '—');
  var rawText = getProjectSummaryText(project);
  var pStatus = (project.status || '').toLowerCase();

  var editBtn = isMaintenanceMode
    ? '<button type="button" onclick="openEditForm(' + idx + ')" style="background:#d97706;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">✏️ Edit Project</button>'
    : '';

  rp.innerHTML = ''
    + '<div class="panel" id="detail-panel">'
    + '  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">'
    + '    <div style="flex:1">'
    + '      <h2 style="border:none;padding:0;margin-bottom:4px;">' + project.title + '</h2>'
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

  var photoArea = document.getElementById(photoContainerId);
  var filesArea = document.getElementById(docContainerId);

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
// EDIT PROJECT FORM & GLOBAL CLIPBOARD PASTE
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

  fetch('projects/' + encodeURIComponent(gid) + '/files.json')
    .then(function (res) { return res.json(); })
    .then(function (data) {
      (data.links || []).forEach(function (l) { addLinkInput(l.label, l.url); });
    })
    .catch(function () { addLinkInput(); });

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
    var textarea = document.getElementById('edit-narrative');
    if (textarea) {
      var tag = '\n\n![' + filename + '](projects/' + projectId + '/' + filename + ')\n\n';
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
  })
  .catch(function (err) {
    if (banner) banner.textContent = '❌ Upload failed: ' + err.message;
  })
  .finally(function () {
    isUploadingImage = false;
  });
}

async function loadEditFiles(projectId) {
  var container = document.getElementById('modal-existing-files');
  if (!container) return;

  try {
    var res = await fetch('projects/' + encodeURIComponent(projectId) + '/files.json');
    if (!res.ok) {
      res = await fetch(BACKEND_URL + '/projects/' + encodeURIComponent(projectId) + '/files.json');
    }
    var data = await res.json();
    var rawFiles = data.files || [];

    var files = rawFiles.map(function (f) {
      if (typeof f === 'string') return f;
      if (f && typeof f === 'object') return f.filename || f.name || '';
      return '';
    }).filter(Boolean);

    if (files.length === 0) {
      container.innerHTML = '<div style="color:#888;font-size:12px;font-style:italic;">No files or photos uploaded yet.</div>';
      return;
    }

    var html = '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:4px;">';
    files.forEach(function (f, i) {
      var isImg = /\.(jpg|jpeg|png|gif|webp)$/i.test(f);
      var elemId = 'file-thumb-' + i;
      var src = 'projects/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(f);

      var mediaTag = isImg
        ? '<img src="' + src + '" onerror="this.src=\'' + BACKEND_URL + '/' + src + '\'; this.onerror=null;" style="width:100%;height:60px;object-fit:cover;border-radius:2px;">'
        : '<div style="font-size:28px;line-height:60px;">📄</div>';

      html += '<div id="' + elemId + '" style="position:relative;border:1px solid #cbd5e1;border-radius:4px;padding:4px;background:#fff;width:90px;text-align:center;">'
            + mediaTag
            + '<div style="font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px;" title="' + escapeHtml(f) + '">' + escapeHtml(f) + '</div>'
            + '<button type="button" onclick="deleteProjectAsset(\'' + projectId + '\', \'' + escapeHtml(f) + '\', \'' + elemId + '\')" style="position:absolute;top:-6px;right:-6px;background:#ef4444;color:white;border:none;border-radius:50%;width:18px;height:18px;font-size:10px;cursor:pointer;line-height:18px;text-align:center;padding:0;" title="Delete file">✕</button>'
            + '</div>';
    });
    html += '</div>';

    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<div style="color:#888;font-size:12px;font-style:italic;">No photos uploaded yet.</div>';
  }
}

window.deleteProjectAsset = async function (projectId, filename, elementId) {
  if (!confirm('Are you sure you want to delete "' + filename + '"?')) return;

  try {
    var res = await fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/files/' + encodeURIComponent(filename), {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Server returned ' + res.status);

    var el = document.getElementById(elementId);
    if (el) el.remove();

    loadProjectFiles(projectId, 'edit-photo-area', null);
  } catch (err) {
    alert('Error deleting file: ' + err.message);
  }
};

function handleFileInputUpload(event, projectId) {
  var files = event.target.files;
  if (!files || files.length === 0) return;

  var banner = document.getElementById('paste-status-banner');
  if (banner) {
    banner.style.display = 'block';
    banner.textContent = '⏳ Uploading ' + files.length + ' file(s)...';
  }

  var uploads = Array.from(files).map(function (file) {
    var fd = new FormData();
    fd.append('file', file);
    return fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/upload', {
      method: 'POST',
      body: fd
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
      if (banner) banner.textContent = '❌ Upload failed: ' + err.message;
    });
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
    + '<input type="text" placeholder="Label" value="' + label + '" style="width:35%;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
    + '<input type="text" placeholder="https://..." value="' + url + '" style="flex:1;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
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

  var updates = {
    id: newGid,
    title: (document.getElementById('edit-title') && document.getElementById('edit-title').value) || '',
    project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
    status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || '',
    shepard: (document.getElementById('edit-shepard') && document.getElementById('edit-shepard').value) || '',
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
  .then(function () {
    var links = [];
    document.querySelectorAll('#modal-links-list .link-row').forEach(function (r) {
      var inputs = r.querySelectorAll('input');
      if (inputs[0].value.trim() && inputs[1].value.trim()) {
        links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
      }
    });
    return fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(newGid) + '/links', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ links: links })
    });
  })
  .then(function () {
    var parsedLat = parseFloat(latVal);
    var parsedLng = parseFloat(lngVal);
    if (!isNaN(parsedLat) && !isNaN(parsedLng) && markers[activeEditIdx]) {
      markers[activeEditIdx].setPosition(new google.maps.LatLng(parsedLat, parsedLng));
    }
    cancelEditCleanup();
    return loadData();
  })
  .then(function (projects) {
    allProjects = projects;
    showDetail(activeEditIdx);
  })
  .catch(function (err) { alert('Error updating project: ' + err.message); })
  .finally(function () {
    if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
  });
}

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
    };
  } catch (e) {}
}

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
