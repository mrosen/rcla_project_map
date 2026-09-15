// ============================================================
// RCLA Project Map — main.js
// Stable State: Deep-Linking (REST URLs) + Maintainer Mode
// ============================================================

const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://127.0.0.1:8000'
  : window.location.origin;
const CSV_PATH = 'RCLA_Projects_v2.csv';

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
          showDetail(foundIdx);
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
  window.history.replaceState({ projectId: gid }, '', newUrl);

  var pType = getProjectType(project);
  var rp = document.getElementById('right-pane');
  var amt = project.amount ? '$' + Number(project.amount).toLocaleString() : (project.budget ? '$' + Number(project.budget).toLocaleString() : '—');
  var rawText = getProjectSummaryText(project);
  var pStatus = (project.status || '').toLowerCase();

  var editBtn = isMaintenanceMode
    ? '<button onclick="openEditForm(' + idx + ')" style="background:#d97706;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">✏️ Edit Project</button>'
    : '';

  rp.innerHTML = ''
    + '<div class="panel" id="detail-panel" tabindex="0" style="outline:none;">'
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
    + '      <button onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;">← All Projects</button>'
    + '    </div>'
    + '  </div>'
    + '  <div id="photo-area"></div>'
    + '  <div id="paste-status-banner" style="display:none;background:#fef3c7;border:1px solid #fde047;padding:8px 12px;border-radius:4px;font-size:12px;color:#854d0e;margin-bottom:10px;"></div>'
    + '  <div class="paste-drop-zone" onclick="document.getElementById(\'hidden-photo-picker\').click()">'
    + '    📋 <strong>Paste Image Here:</strong> Press <code>Ctrl+V</code> / <code>Cmd+V</code> anywhere in this panel to paste an image, or click to browse.'
    + '    <input type="file" id="hidden-photo-picker" accept="image/*" style="display:none;" onchange="handleFilePickerUpload(event, \'' + gid + '\')">'
    + '  </div>'
    + '  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:16px;margin-bottom:6px;">'
    + '    <h3 style="margin:0;">Summary & Narrative</h3>'
    + '    <button onclick="enableNarrativeEdit(\'' + gid + '\')" style="background:none;border:none;color:#2563eb;font-size:12px;cursor:pointer;text-decoration:underline;">✏️ Edit Narrative</button>'
    + '  </div>'
    + '  <div class="narrative" id="narrative-body" '
    + '       ondblclick="enableNarrativeEdit(\'' + gid + '\')" '
    + '       data-raw="' + encodeURIComponent(rawText) + '" '
    + '       title="Double-click to edit narrative" '
    + '       style="cursor:pointer;border:1px solid transparent;border-radius:4px;padding:6px;">'
    +      (rawText || 'No narrative available yet. Double-click to write one.')
    + '  </div>'
    + '  <h3>Project Details</h3>'
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

  attachGlobalPasteHandler(gid);
  setTimeout(function () { loadProjectFiles(gid); }, 0);
  renderMarkdown();
}

function attachGlobalPasteHandler(projectId) {
  var panel = document.getElementById('detail-panel');
  if (!panel) return;

  panel.addEventListener('paste', function (e) {
    var clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData || !clipboardData.items) return;

    for (var i = 0; i < clipboardData.items.length; i++) {
      var item = clipboardData.items[i];
      if (item.type && item.type.startsWith('image/')) {
        var blob = item.getAsFile();
        if (blob) {
          e.preventDefault();
          uploadImageBlob(blob, projectId);
          return;
        }
      }
    }
  });
}

function handleFilePickerUpload(event, projectId) {
  var file = event.target.files && event.target.files[0];
  if (file) uploadImageBlob(file, projectId);
}

function uploadImageBlob(blob, projectId) {
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
    if (banner) {
      banner.textContent = '✅ Image successfully uploaded & saved to project!';
      setTimeout(function () { banner.style.display = 'none'; }, 3000);
    }
    loadProjectFiles(projectId);
  })
  .catch(function (err) {
    if (banner) banner.textContent = '❌ Upload failed: ' + err.message;
  })
  .finally(function () {
    isUploadingImage = false;
  });
}

function loadProjectFiles(projectId) {
  if (!projectId) return;

  fetch('projects/' + encodeURIComponent(projectId) + '/files.json')
    .then(function (r) {
      if (r.ok) return r.json();
      return fetch(BACKEND_URL + '/projects/' + encodeURIComponent(projectId) + '/files.json').then(function(b) {
        return b.ok ? b.json() : { files: [], links: [] };
      });
    })
    .catch(function () { return { files: [], links: [] }; })
    .then(function (manifest) { renderFilesAndLinks(manifest, projectId); });
}

function renderFilesAndLinks(manifest, projectId) {
  var rawFiles = manifest.files || [];
  var links = manifest.links || [];

  var files = rawFiles.map(function (f) {
    if (typeof f === 'string') return f;
    if (f && typeof f === 'object') return f.filename || f.name || '';
    return '';
  }).filter(Boolean);

  var images = files.filter(function (f) { return /\.(jpg|jpeg|png|gif|webp)$/i.test(f); });
  var docs   = files.filter(function (f) { return !/\.(jpg|jpeg|png|gif|webp)$/i.test(f); });

  var photoArea = document.getElementById('photo-area');
  var filesArea = document.getElementById('files-area');
  if (!photoArea || !filesArea) return;

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
    photoArea.innerHTML = '<div style="font-size:12px;color:#94a3b8;font-style:italic;margin-bottom:10px;">No images associated with this project yet. Paste or drop images above.</div>';
  }

  if (docs.length > 0 || links.length > 0) {
    filesArea.innerHTML = '<h3>Attached Documents & Web Links</h3><div class="files-section" id="files-list"></div>';
    var list = document.getElementById('files-list');
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

window.enableNarrativeEdit = function(projectId) {
  var el = document.getElementById('narrative-body');
  if (!el || el.dataset.isEditing === 'true') return;

  el.dataset.isEditing = 'true';
  var rawMarkdown = el.dataset.raw ? decodeURIComponent(el.dataset.raw) : '';

  el.innerHTML = ''
    + '<div style="display:flex;flex-direction:column;gap:8px;">'
    + '  <textarea id="narrative-inline-input" style="width:100%;height:320px;font-family:monospace;font-size:13px;line-height:1.5;padding:10px;border:1px solid #3b82f6;border-radius:4px;box-sizing:border-box;">' + escapeHtml(rawMarkdown) + '</textarea>'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;">'
    + '    <span style="font-size:11px;color:#64748b;">Markdown supported. Double enter between sections.</span>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" onclick="cancelNarrativeEdit()" style="padding:5px 12px;background:#94a3b8;color:white;border:none;border-radius:4px;font-size:12px;cursor:pointer;">Cancel</button>'
    + '      <button type="button" onclick="saveNarrativeInline(\'' + projectId + '\')" style="padding:5px 16px;background:#059669;color:white;border:none;border-radius:4px;font-weight:bold;font-size:12px;cursor:pointer;">Save</button>'
    + '    </div>'
    + '  </div>'
    + '</div>';

  var txt = document.getElementById('narrative-inline-input');
  if (txt) txt.focus();
};

window.cancelNarrativeEdit = function() {
  var el = document.getElementById('narrative-body');
  if (!el) return;
  el.dataset.isEditing = 'false';
  renderMarkdown();
};

window.saveNarrativeInline = function(projectId) {
  var input = document.getElementById('narrative-inline-input');
  if (!input) return;

  var newContent = input.value;
  var el = document.getElementById('narrative-body');
  el.dataset.raw = encodeURIComponent(newContent);
  el.dataset.isEditing = 'false';

  var p = allProjects.find(function(item) { return (item.id || item.grant_id) === projectId; });
  if (p) p.narrative = newContent;

  fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ narrative: newContent })
  })
  .then(function() { renderMarkdown(); })
  .catch(function(err) {
    console.warn('Could not persist narrative:', err);
    renderMarkdown();
  });
};

function renderMarkdown() {
  var el = document.getElementById('narrative-body');
  if (!el) return;
  var raw = el.dataset.raw ? decodeURIComponent(el.dataset.raw) : '';
  if (!raw.trim()) {
    el.innerHTML = '<span style="color:#94a3b8;font-style:italic;">No narrative available yet. Double-click to add.</span>';
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

function cancelEditCleanup() {
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
      pollMaintStatus();
    };

    evtSource.onerror = function () {
      isMaintenanceMode = false;
      var badge = document.getElementById('sync-status-badge');
      if (badge) { badge.textContent = 'Offline'; badge.style.background = '#64748b'; }
    };
  } catch (e) {}

  setInterval(pollMaintStatus, 4000);
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
        badge.textContent = 'Status: ' + data.status.toUpperCase();
        badge.style.background = data.status === 'running' ? '#d97706' : data.status === 'error' ? '#dc2626' : '#059669';
      }
    })
    .catch(function () {
      isMaintenanceMode = false;
      var badge = document.getElementById('sync-status-badge');
      if (badge) { badge.textContent = 'Offline'; badge.style.background = '#64748b'; }
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
