const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://127.0.0.1:8000'
  : window.location.origin;
const CSV_PATH = 'RCLA_Projects_v2.csv';

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
let easyMDEInstance   = null;
let overviewChartInstance = null;

let currentFilters = {
  type: '',
  status: '',
  category: '',
  search: ''
};

function getProjectType(p) {
  if (p.project_type && String(p.project_type).trim()) return p.project_type;
  const id = (p.id || p.grant_id || '').toUpperCase();
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
  let latVal = project.position_lat !== undefined ? project.position_lat : project.lat;
  let lngVal = project.position_lng !== undefined ? project.position_lng : project.lng;

  if (typeof latVal === 'string' && latVal.includes(',')) {
    const parts = latVal.split(',');
    latVal = parts[0].trim();
    lngVal = parts[1].trim();
  }
  const lat = Number(latVal);
  const lng = Number(lngVal);
  return (Number.isFinite(lat) && Number.isFinite(lng)) ? { lat, lng } : null;
}

window.initMap = function () {
  initMaintainerClient();
  wireNavButtons();
  initDivider();

  loadData()
    .then(function(projects) {
      allProjects = projects;
      buildMap();
      showOverview();
    })
    .catch(function(err) {
      const rp = document.getElementById('right-pane');
      if (rp) rp.innerHTML = '<div style="padding:20px;color:red;">Error loading CSV: ' + err.message + '</div>';
    });
};

function loadData() {
  return fetch(CSV_PATH)
    .then(function(r) {
      if (!r.ok) throw new Error('Could not fetch ' + CSV_PATH);
      return r.text();
    })
    .then(function(csv) {
      return new Promise(function(resolve, reject) {
        Papa.parse(csv, {
          header: true,
          skipEmptyLines: true,
          dynamicTyping: true,
          complete: function(res) { resolve(res.data.filter(function(p) { return p.id || p.grant_id; })); },
          error: function(err) { reject(err); }
        });
      });
    });
}

function buildMap() {
  const mapElement = document.getElementById('map');
  if (!mapElement || !window.google || !google.maps) return;

  map = new google.maps.Map(mapElement, {
    zoom: 10,
    center: { lat: 14.703454, lng: -91.191623 },
    mapTypeId: 'roadmap',
    mapTypeControl: true,
    mapTypeControlOptions: {
      style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
      position: google.maps.ControlPosition.TOP_RIGHT,
      mapTypeIds: ['roadmap', 'satellite', 'hybrid', 'terrain']
    },
    rotateControl: true,
    fullscreenControl: true
  });

  initMapPlacesSearch();

  markers = allProjects.map(function(project, idx) {
    const coords = getProjectCoords(project);
    if (!coords) return null;

    const marker = new google.maps.Marker({
      position: coords,
      map: map,
      title: project.title,
      icon: 'https://maps.google.com/mapfiles/ms/icons/' + markerColor(project.status) + '-dot.png'
    });
    marker.addListener('click', function() { showDetail(idx); });
    return marker;
  });
}

function initMapPlacesSearch() {
  const searchInput = document.getElementById('map-search-input');
  if (!searchInput || !window.google || !google.maps.places) return;

  const atitlanBounds = new google.maps.LatLngBounds(
    new google.maps.LatLng(14.55, -91.35),
    new google.maps.LatLng(14.85, -91.05)
  );

  const autocomplete = new google.maps.places.Autocomplete(searchInput, {
    bounds: atitlanBounds,
    strictBounds: false,
    fields: ['geometry', 'name', 'formatted_address']
  });

  autocomplete.bindTo('bounds', map);

  autocomplete.addListener('place_changed', function() {
    const place = autocomplete.getPlace();
    if (!place.geometry || !place.geometry.location) return;

    if (searchMarker) searchMarker.setMap(null);
    searchMarker = new google.maps.Marker({
      map: map,
      position: place.geometry.location,
      title: place.name || 'Searched Location',
      icon: 'https://maps.google.com/mapfiles/ms/icons/purple-dot.png',
      zIndex: 9999
    });

    if (place.geometry.viewport) {
      map.fitBounds(place.geometry.viewport);
    } else {
      map.setCenter(place.geometry.location);
      map.setZoom(16);
    }

    const editLatEl = document.getElementById('edit-lat');
    const editLngEl = document.getElementById('edit-lng');
    if (editLatEl && editLngEl) {
      editLatEl.value = place.geometry.location.lat().toFixed(6);
      editLngEl.value = place.geometry.location.lng().toFixed(6);
      if (editMarker) editMarker.setPosition(place.geometry.location);
    }
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
  const active = markers[idx];
  if (active) {
    active.setIcon('https://maps.google.com/mapfiles/ms/icons/red-dot.png');
    active.setZIndex(999);
    map.panTo(active.getPosition());
  }
}

function resetMarkers() {
  markers.forEach(function(m, i) {
    if (!m || !allProjects[i]) return;
    m.setIcon('https://maps.google.com/mapfiles/ms/icons/' + markerColor(allProjects[i].status) + '-dot.png');
    m.setZIndex(1);
    m.setVisible(true);
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
  return allProjects.filter(function(p) {
    const pType = getProjectType(p);
    if (currentFilters.type && pType !== currentFilters.type) return false;
    if (currentFilters.status && p.status !== currentFilters.status) return false;
    if (currentFilters.category && p.category !== currentFilters.category) return false;
    if (currentFilters.search) {
      const q = currentFilters.search.toLowerCase();
      const match = (p.title && p.title.toLowerCase().includes(q)) ||
                    (p.id && String(p.id).toLowerCase().includes(q)) ||
                    (p.partner && p.partner.toLowerCase().includes(q)) ||
                    (p.narrative && p.narrative.toLowerCase().includes(q)) ||
                    (p.description && p.description.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });
}

function syncFilterInputs() {
  const typeEl = document.getElementById('filter-type');
  const statusEl = document.getElementById('filter-status');
  const catEl = document.getElementById('filter-category');
  const searchEl = document.getElementById('filter-search');

  if (typeEl) typeEl.value = currentFilters.type;
  if (statusEl) statusEl.value = currentFilters.status;
  if (catEl) catEl.value = currentFilters.category;
  if (searchEl) searchEl.value = currentFilters.search;
}

function handleFilterInput(e) {
  const val = e.target.value;
  const id = e.target.id;

  if (id === 'filter-type') currentFilters.type = val;
  else if (id === 'filter-status') currentFilters.status = val;
  else if (id === 'filter-category') currentFilters.category = val;
  else if (id === 'filter-search') currentFilters.search = val;

  syncFilterInputs();

  if (currentView === 'overview') {
    updateOverviewMetricsAndChart();
  } else if (currentView === 'list') {
    renderListRows();
  }
}

function renderFilterBar(types, statuses, categories) {
  const typeOptions = types.map(function(t) { return '<option value="' + t + '" ' + (currentFilters.type === t ? 'selected' : '') + '>' + t + '</option>'; }).join('');
  const statusOptions = statuses.map(function(s) { return '<option value="' + s + '" ' + (currentFilters.status === s ? 'selected' : '') + '>' + capitalize(s) + '</option>'; }).join('');
  const catOptions = categories.map(function(c) { return '<option value="' + c + '" ' + (currentFilters.category === c ? 'selected' : '') + '>' + c + '</option>'; }).join('');

  return ''
    + '<div class="filters">'
    + '  <select id="filter-type"><option value="">All Grant / Project Types</option>' + typeOptions + '</select>'
    + '  <select id="filter-status"><option value="">All statuses</option>' + statusOptions + '</select>'
    + '  <select id="filter-category"><option value="">All categories</option>' + catOptions + '</select>'
    + '  <input id="filter-search" type="text" placeholder="Search title, ID, partner…" value="' + escapeHtml(currentFilters.search) + '" style="flex:1;min-width:120px;">'
    + '</div>';
}

function attachFilterListeners() {
  ['filter-type', 'filter-status', 'filter-category', 'filter-search'].forEach(function(id) {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', handleFilterInput);
  });
}

function showOverview() {
  cancelEditCleanup();
  currentView = 'overview';
  setActiveNav('overview');

  const rp = document.getElementById('right-pane');
  const types = Array.from(new Set(allProjects.map(function(p) { return getProjectType(p); }))).sort();
  const statuses = Array.from(new Set(allProjects.map(function(p) { return p.status; }).filter(Boolean))).sort();
  const categories = Array.from(new Set(allProjects.map(function(p) { return p.category; }).filter(Boolean))).sort();

  rp.innerHTML = ''
    + '<div class="panel" id="overview-panel">'
    + '  <h2>Club Projects Overview</h2>'
    +    renderFilterBar(types, statuses, categories)
    + '  <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:14px;line-height:1.7;margin-bottom:16px;">'
    + '    <p>The Rotary Club of Lake Atitlán funds community development projects across Guatemala through Global Grants, District Grants, Club-to-Club collaborations, and direct club donations.</p>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:10px;margin-bottom:16px;">'
    + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
    + '      <div id="ov-total-count" style="font-size:22px;font-weight:bold;color:#1a3a5c;">0</div>'
    + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Total Projects</div>'
    + '    </div>'
    + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
    + '      <div id="ov-total-funding" style="font-size:22px;font-weight:bold;color:#1a3a5c;">$0.00M</div>'
    + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Total Deployed</div>'
    + '    </div>'
    + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
    + '      <div id="ov-split-count" style="font-size:22px;font-weight:bold;color:#1a3a5c;">0 / 0</div>'
    + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Global Grants / Direct & Other</div>'
    + '    </div>'
    + '  </div>'
    + '  <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:14px;margin-bottom:14px;">'
    + '    <h3 style="margin-top:0;">Project Types Breakdown</h3>'
    + '    <div style="position:relative;height:220px;"><canvas id="chart-types"></canvas></div>'
    + '  </div>'
    + '</div>';

  attachFilterListeners();
  updateOverviewMetricsAndChart();
}

function updateOverviewMetricsAndChart() {
  const filtered = getFilteredProjects();

  if (markers.length) {
    allProjects.forEach(function(p, idx) {
      const marker = markers[idx];
      if (marker) {
        marker.setVisible(filtered.includes(p));
      }
    });
  }

  const totalFunding = filtered.reduce(function(s, p) { return s + (Number(p.amount) || Number(p.budget) || 0); }, 0);
  const ggCount = filtered.filter(function(p) { return getProjectType(p) === 'Global Grant'; }).length;
  const directCount = filtered.filter(function(p) { return getProjectType(p) !== 'Global Grant'; }).length;

  const countEl = document.getElementById('ov-total-count');
  const fundingEl = document.getElementById('ov-total-funding');
  const splitEl = document.getElementById('ov-split-count');

  if (countEl) countEl.textContent = filtered.length;
  if (fundingEl) fundingEl.textContent = '$' + (totalFunding / 1e6).toFixed(2) + 'M';
  if (splitEl) splitEl.textContent = ggCount + ' / ' + directCount;

  renderTypeChart(filtered);
}

function renderTypeChart(filteredProjects) {
  const projectsToUse = filteredProjects || getFilteredProjects();
  const typeMap = {};
  projectsToUse.forEach(function(p) {
    const t = getProjectType(p);
    typeMap[t] = (typeMap[t] || 0) + 1;
  });

  const canvas = document.getElementById('chart-types');
  if (!canvas || !window.Chart) return;

  if (overviewChartInstance) {
    overviewChartInstance.destroy();
  }

  overviewChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: Object.keys(typeMap),
      datasets: [{ data: Object.values(typeMap), backgroundColor: ['#1a3a5c', '#8b5cf6', '#059669', '#f59e0b'] }]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

function showList() {
  cancelEditCleanup();
  currentView = 'list';
  setActiveNav('list');

  const rp = document.getElementById('right-pane');
  const types = Array.from(new Set(allProjects.map(function(p) { return getProjectType(p); }))).sort();
  const statuses = Array.from(new Set(allProjects.map(function(p) { return p.status; }).filter(Boolean))).sort();
  const categories = Array.from(new Set(allProjects.map(function(p) { return p.category; }).filter(Boolean))).sort();

  rp.innerHTML = ''
    + '<div class="panel" id="list-panel">'
    + '  <h2>All Projects</h2>'
    +    renderFilterBar(types, statuses, categories)
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
  const filtered = getFilteredProjects();
  const tbody = document.getElementById('project-tbody');
  if (!tbody) return;

  if (markers.length) {
    allProjects.forEach(function(p, idx) {
      const marker = markers[idx];
      if (marker) {
        marker.setVisible(filtered.includes(p));
      }
    });
  }

  let rowsHtml = '';
  filtered.forEach(function(p) {
    const idx = allProjects.indexOf(p);
    const amt = p.amount ? '$' + Number(p.amount).toLocaleString() : (p.budget ? '$' + Number(p.budget).toLocaleString() : '—');
    const pStatus = (p.status || '').toLowerCase();
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

  const project = allProjects[idx];
  const pType = getProjectType(project);
  const rp = document.getElementById('right-pane');
  const amt = project.amount ? '$' + Number(project.amount).toLocaleString() : (project.budget ? '$' + Number(project.budget).toLocaleString() : '—');
  const rawText = getProjectSummaryText(project);
  const pStatus = (project.status || '').toLowerCase();

  const editBtn = isMaintenanceMode
    ? '<button onclick="openEditForm(' + idx + ')" style="background:#d97706;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">✏️ Edit Project</button>'
    : '';

  rp.innerHTML = ''
    + '<div class="panel" id="detail-panel">'
    + '  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">'
    + '    <div style="flex:1">'
    + '      <h2 style="border:none;padding:0;margin-bottom:4px;">' + project.title + '</h2>'
    + '      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
    + '        <span class="badge badge-type">' + pType + '</span>'
    + '        <span class="badge badge-' + pStatus + '">' + (project.status || '—') + '</span>'
    + '        <span style="color:#888;font-size:12px;">' + (project.id || project.grant_id) + '</span>'
    + '        <span style="color:#888;font-size:12px;">' + (project.start_year || '') + '</span>'
    + '      </div>'
    + '    </div>'
    + '    <div style="display:flex;gap:6px;">'
    +        editBtn
    + '      <button onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;">← All Projects</button>'
    + '    </div>'
    + '  </div>'
    + '  <div id="photo-area"></div>'
    + '  <h3>Summary & Narrative</h3>'
    + '  <div class="narrative" id="narrative-body" data-raw="' + encodeURIComponent(rawText) + '">'
    +      (rawText || 'No narrative available yet.')
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

  setTimeout(function() { loadProjectFiles(project.id || project.grant_id); }, 0);
  renderMarkdown();
}

function loadProjectFiles(projectId) {
  fetch('projects/' + projectId + '/files.json')
    .then(function(r) { return r.ok ? r.json() : { files: [], links: [] }; })
    .catch(function() { return { files: [], links: [] }; })
    .then(function(manifest) { renderFilesAndLinks(manifest, projectId); });
}

function renderFilesAndLinks(manifest, projectId) {
  const files = manifest.files || [];
  const links = manifest.links || [];
  const images = files.filter(function(f) { return /\.(jpg|jpeg|png|gif|webp)$/i.test(f); });
  const docs   = files.filter(function(f) { return !/\.(jpg|jpeg|png|gif|webp)$/i.test(f); });

  const photoArea = document.getElementById('photo-area');
  const filesArea = document.getElementById('files-area');
  if (!photoArea || !filesArea) return;

  if (images.length > 0) {
    photoArea.innerHTML = '<div class="photo-carousel">' +
      images.map(function(f) { return '<img src="projects/' + projectId + '/' + f + '" alt="' + f + '" onclick="window.open(\'projects/' + projectId + '/' + f + '\',\'_blank\')">'; }).join('') +
      '</div>';
  }

  if (docs.length > 0 || links.length > 0) {
    filesArea.innerHTML = '<h3>Attached Documents & Web Links</h3><div class="files-section" id="files-list"></div>';
    const list = document.getElementById('files-list');
    docs.forEach(function(f) {
      const a = document.createElement('a');
      a.href = 'projects/' + projectId + '/' + f;
      a.target = '_blank';
      a.innerHTML = '<span class="file-icon">📄</span> ' + f;
      list.appendChild(a);
    });
    links.forEach(function(l) {
      const a = document.createElement('a');
      a.href = l.url;
      a.target = '_blank';
      a.innerHTML = '<span class="file-icon">🔗</span> ' + (l.label || l.url);
      list.appendChild(a);
    });
  }
}

function uploadPastedImageBlob(blob, projectId) {
  const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const ext = blob.type.split('/')[1] || 'png';
  const filename = 'paste_' + timestamp + '.' + ext;
  const file = new File([blob], filename, { type: blob.type });

  const statusBanner = document.getElementById('paste-status-banner');
  if (statusBanner) {
    statusBanner.style.display = 'block';
    statusBanner.textContent = '⏳ Uploading pasted image (' + filename + ')...';
  }

  const fd = new FormData();
  fd.append('file', file);

  fetch(BACKEND_URL + '/api/projects/' + projectId + '/upload', {
    method: 'POST',
    body: fd
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Upload failed');
    if (easyMDEInstance) {
      const cm = easyMDEInstance.codemirror;
      const imgMarkdown = '\n![' + filename + '](projects/' + projectId + '/' + filename + ')\n';
      cm.replaceSelection(imgMarkdown);
    }
    if (statusBanner) {
      statusBanner.textContent = '✅ Image uploaded and inserted into narrative!';
      setTimeout(function() { statusBanner.style.display = 'none'; }, 3000);
    }
    loadEditFiles(projectId);
  })
  .catch(function(err) {
    if (statusBanner) statusBanner.textContent = '❌ Failed to upload image: ' + err.message;
  });
}

function wireClipboardPaste(projectId) {
  const turndownService = (window.TurndownService) ? new window.TurndownService({ headingStyle: 'atx', bulletListMarker: '*' }) : null;

  const handlePaste = function(e) {
    const clip = e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData);
    if (!clip) return;

    const items = clip.items;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          const blob = items[i].getAsFile();
          if (blob) {
            e.preventDefault();
            uploadPastedImageBlob(blob, projectId);
            return;
          }
        }
      }
    }

    const htmlData = clip.getData('text/html');
    if (htmlData && turndownService && easyMDEInstance) {
      e.preventDefault();
      const markdown = turndownService.turndown(htmlData);
      const cm = easyMDEInstance.codemirror;
      cm.replaceSelection(markdown);
    }
  };

  if (easyMDEInstance && easyMDEInstance.codemirror) {
    easyMDEInstance.codemirror.on('paste', function(cm, e) { handlePaste(e); });
  }

  const panel = document.getElementById('edit-panel');
  if (panel) {
    panel.addEventListener('paste', handlePaste);
  }
}

function loadEditFiles(projectId) {
  const container = document.getElementById('modal-existing-files');
  if (!container) return;

  fetch('projects/' + projectId + '/files.json')
    .then(function(res) { return res.json(); })
    .then(function(data) {
      const files = data.files || [];
      if (files.length === 0) {
        container.innerHTML = '<div style="color:#888;font-size:12px;font-style:italic;">No files or photos uploaded yet.</div>';
        return;
      }

      let fileCards = '';
      files.forEach(function(f, i) {
        const isImg = /\.(jpg|jpeg|png|gif|webp)$/i.test(f);
        const elemId = 'file-item-' + i;
        const mediaHtml = isImg
          ? '<img src="projects/' + projectId + '/' + f + '" style="width:100%;height:60px;object-fit:cover;border-radius:2px;">'
          : '<div style="font-size:32px;line-height:60px;">📄</div>';

        fileCards += '<div id="' + elemId + '" style="position:relative;border:1px solid #cbd5e1;border-radius:4px;padding:4px;background:#fff;width:90px;text-align:center;">'
          + mediaHtml
          + '<div style="font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px;" title="' + f + '">' + f + '</div>'
          + '<button type="button" onclick="deleteProjectAsset(\'' + projectId + '\', \'' + f + '\', \'' + elemId + '\')" style="position:absolute;top:-6px;right:-6px;background:#ef4444;color:white;border:none;border-radius:50%;width:18px;height:18px;font-size:10px;cursor:pointer;line-height:18px;text-align:center;padding:0;" title="Delete file">✕</button>'
          + '</div>';
      });

      container.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:6px;">' + fileCards + '</div>';
    })
    .catch(function() {
      container.innerHTML = '<div style="color:#888;font-size:12px;font-style:italic;">No files uploaded yet.</div>';
    });
};

window.deleteProjectAsset = function(projectId, filename, elementId) {
  if (!confirm('Are you sure you want to delete "' + filename + '"?')) return;

  fetch(BACKEND_URL + '/api/projects/' + projectId + '/files/' + encodeURIComponent(filename), {
    method: 'DELETE'
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Failed to delete asset from server');
    const el = document.getElementById(elementId);
    if (el) el.remove();
  })
  .catch(function(err) {
    alert('Error deleting file: ' + err.message);
  });
};

window.openCreateForm = function () {
  if (!isMaintenanceMode) {
    alert('Please start orchestrator.py locally to add new projects.');
    return;
  }
  cancelEditCleanup();
  activeEditIdx = null;

  const defaultCoords = { lat: 14.703454, lng: -91.191623 };
  const rp = document.getElementById('right-pane');
  const currentYear = new Date().getFullYear();

  rp.innerHTML = ''
    + '<div class="panel" id="edit-panel">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:2px solid #8b5cf6;padding-bottom:6px;">'
    + '    <h2 style="border:none;padding:0;margin:0;color:#8b5cf6;">➕ New Club Project</h2>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" onclick="showList()" style="padding:5px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>'
    + '      <button type="button" id="btn-save-project" onclick="submitCreateProject()" style="padding:5px 14px;border:none;background:#8b5cf6;color:white;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">Create Project</button>'
    + '    </div>'
    + '  </div>'
    + '  <div style="background:#f5f3ff;border:1px solid #ddd6fe;padding:8px 12px;border-radius:6px;font-size:12px;color:#5b21b6;margin-bottom:12px;">'
    + '    📍 <strong>Location Pinning:</strong> Drag the marker on the map, search a location in the search box, or click anywhere on the map.'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Title *</label>'
    + '      <input type="text" id="create-title" placeholder="e.g. Wheelchair Donation to Santiago Clinic" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Type</label>'
    + '      <select id="create-type" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:white;">'
    + '        <option value="Club Direct / Donation">Club Direct / Donation</option>'
    + '        <option value="District Grant">District Grant</option>'
    + '        <option value="Club-to-Club Grant">Club-to-Club Grant</option>'
    + '        <option value="Global Grant">Global Grant</option>'
    + '      </select>'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Year</label>'
    + '      <input type="text" id="create-year" value="' + currentYear + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Budget / Amount ($)</label>'
    + '      <input type="text" id="create-amount" placeholder="0" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Status</label>'
    + '      <select id="create-status" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:white;">'
    + '        <option value="approved">Approved / Active</option>'
    + '        <option value="closed">Closed</option>'
    + '        <option value="proposed">Proposed</option>'
    + '      </select>'
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
    + '      <input type="text" id="create-shepard" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Partner / Beneficiary</label>'
    + '      <input type="text" id="create-partner" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Description & Story (WYSIWYG)</label>'
    + '  <textarea id="create-narrative"></textarea>'
    + '</div>';

  easyMDEInstance = new EasyMDE({
    element: document.getElementById('create-narrative'),
    spellChecker: false,
    placeholder: 'Type narrative or paste rich text / images with Ctrl+V...',
    shortcuts: { toggleFullScreen: null },
    toolbar: ['bold', 'italic', 'heading', '|', 'quote', 'unordered-list', 'ordered-list', '|', 'link', 'table', '|', 'preview', 'guide']
  });

  wireClipboardPaste('NEW_PROJECT');
  setupLocationPicker(defaultCoords);
};

window.openEditForm = function (idx) {
  cancelEditCleanup();
  activeEditIdx = Number(idx);
  const p = allProjects[activeEditIdx];
  if (!p) return;

  const gid = p.id || p.grant_id;
  const coords = getProjectCoords(p) || { lat: 14.703454, lng: -91.191623 };
  const rp = document.getElementById('right-pane');
  const pType = getProjectType(p);
  const initialText = getProjectSummaryText(p);

  const optDirect = pType === 'Club Direct / Donation' ? 'selected' : '';
  const optDG = pType === 'District Grant' ? 'selected' : '';
  const optC2C = pType === 'Club-to-Club Grant' ? 'selected' : '';
  const optGG = pType === 'Global Grant' ? 'selected' : '';

  rp.innerHTML = ''
    + '<div class="panel" id="edit-panel">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:2px solid #d97706;padding-bottom:6px;">'
    + '    <h2 style="border:none;padding:0;margin:0;color:#d97706;">✏️ Edit: ' + gid + '</h2>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" onclick="showDetail(' + activeEditIdx + ')" style="padding:5px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>'
    + '      <button type="button" id="btn-save-project" onclick="saveProjectEdits()" style="padding:5px 14px;border:none;background:#059669;color:white;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">Save Changes</button>'
    + '    </div>'
    + '  </div>'
    + '  <div style="background:#eff6ff;border:1px solid #bfdbfe;padding:8px 12px;border-radius:6px;font-size:12px;color:#1e40af;margin-bottom:12px;">'
    + '    📍 <strong>Location Pinning:</strong> Drag the marker on the map, search a location in the search box, or click anywhere on the map.'
    + '  </div>'
    + '  <div id="paste-status-banner" style="display:none;background:#fef3c7;border:1px solid #fde047;padding:6px 12px;border-radius:4px;font-size:12px;color:#854d0e;margin-bottom:10px;"></div>'
    + '  <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Title</label>'
    + '      <input type="text" id="edit-title" value="' + (p.title || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Type</label>'
    + '      <select id="edit-type" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:white;">'
    + '        <option value="Club Direct / Donation" ' + optDirect + '>Club Direct / Donation</option>'
    + '        <option value="District Grant" ' + optDG + '>District Grant</option>'
    + '        <option value="Club-to-Club Grant" ' + optC2C + '>Club-to-Club Grant</option>'
    + '        <option value="Global Grant" ' + optGG + '>Global Grant</option>'
    + '      </select>'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Status</label>'
    + '      <input type="text" id="edit-status" value="' + (p.status || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Category</label>'
    + '      <input type="text" id="edit-category" value="' + (p.category || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Budget / Amount</label>'
    + '      <input type="text" id="edit-amount" value="' + (p.amount || p.budget || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
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
    + '      <input type="text" id="edit-shepard" value="' + (p.shepard || p.shepherd || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Partner</label>'
    + '      <input type="text" id="edit-partner" value="' + (p.partner || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Narrative & Field Notes (Formatted Paste Enabled)</label>'
    + '  <textarea id="edit-narrative"></textarea>'
    + '  <div class="paste-zone" onclick="document.getElementById(\'modal-file-upload\').click()">'
    + '    📋 <strong>Paste or Drop Images:</strong> You can paste (Ctrl+V / ⌘+V) text or images directly into the editor above, or click here to upload files.'
    + '  </div>'
    + '  <div style="margin-bottom:14px;margin-top:10px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Existing Uploaded Files & Photos</label>'
    + '    <div id="modal-existing-files"></div>'
    + '  </div>'
    + '  <div style="margin-bottom:14px;margin-top:10px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Web Links</label>'
    + '    <div id="modal-links-list"></div>'
    + '    <button type="button" onclick="addLinkInput()" style="margin-top:4px;padding:4px 8px;font-size:11px;cursor:pointer;background:#e2e8f0;border:none;border-radius:4px;">+ Add Link</button>'
    + '  </div>'
    + '  <div style="margin-bottom:20px;">'
    + '    <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Upload More Files / Photos</label>'
    + '    <input type="file" id="modal-file-upload" multiple style="display:block;margin-top:4px;font-size:12px;">'
    + '  </div>'
    + '</div>';

  easyMDEInstance = new EasyMDE({
    element: document.getElementById('edit-narrative'),
    initialValue: initialText,
    spellChecker: false,
    shortcuts: { toggleFullScreen: null },
    toolbar: ['bold', 'italic', 'heading', '|', 'quote', 'unordered-list', 'ordered-list', '|', 'link', 'table', '|', 'preview', 'guide']
  });

  wireClipboardPaste(gid);
  loadEditFiles(gid);

  fetch('projects/' + gid + '/files.json')
    .then(function(res) { return res.json(); })
    .then(function(data) {
      (data.links || []).forEach(function(l) { addLinkInput(l.label, l.url); });
    })
    .catch(function() {
      addLinkInput();
    });

  setupLocationPicker(coords);
};

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

    editMarker.addListener('drag', function(e) {
      const latEl = document.getElementById('edit-lat');
      const lngEl = document.getElementById('edit-lng');
      if (latEl) latEl.value = e.latLng.lat().toFixed(6);
      if (lngEl) lngEl.value = e.latLng.lng().toFixed(6);
    });

    if (mapClickListener) google.maps.event.removeListener(mapClickListener);
    mapClickListener = map.addListener('click', function(e) {
      if (editMarker) editMarker.setPosition(e.latLng);
      const latEl = document.getElementById('edit-lat');
      const lngEl = document.getElementById('edit-lng');
      if (latEl) latEl.value = e.latLng.lat().toFixed(6);
      if (lngEl) lngEl.value = e.latLng.lng().toFixed(6);
    });

    map.panTo(initialCoords);
  }
}

function cancelEditCleanup() {
  if (easyMDEInstance) {
    easyMDEInstance.toTextArea();
    easyMDEInstance = null;
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
  const container = document.getElementById('modal-links-list');
  if (!container) return;
  const div = document.createElement('div');
  div.className = 'link-row';
  div.style.cssText = 'display:flex;gap:8px;margin-bottom:6px;';
  div.innerHTML = ''
    + '<input type="text" placeholder="Label" value="' + label + '" style="width:35%;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
    + '<input type="text" placeholder="https://..." value="' + url + '" style="flex:1;padding:4px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
    + '<button type="button" onclick="this.parentElement.remove()" style="background:#ef4444;color:white;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;">✕</button>';
  container.appendChild(div);
};

function submitCreateProject() {
  const titleEl = document.getElementById('create-title');
  const titleVal = titleEl ? titleEl.value.trim() : '';

  if (!titleVal) {
    alert('Please enter a project title.');
    return;
  }

  const typeEl = document.getElementById('create-type');
  const yearEl = document.getElementById('create-year');
  const amountEl = document.getElementById('create-amount');
  const statusEl = document.getElementById('create-status');
  const latEl = document.getElementById('edit-lat');
  const lngEl = document.getElementById('edit-lng');
  const shepardEl = document.getElementById('create-shepard');
  const partnerEl = document.getElementById('create-partner');

  const payload = {
    title: titleVal,
    project_type: typeEl ? typeEl.value : 'Club Direct / Donation',
    start_year: yearEl ? yearEl.value.trim() : String(new Date().getFullYear()),
    amount: amountEl ? amountEl.value.trim() : '0',
    status: statusEl ? statusEl.value : 'approved',
    position_lat: latEl ? latEl.value.trim() : '14.703454',
    position_lng: lngEl ? lngEl.value.trim() : '-91.191623',
    shepard: shepardEl ? shepardEl.value.trim() : '',
    partner: partnerEl ? partnerEl.value.trim() : '',
    narrative: easyMDEInstance ? easyMDEInstance.value() : ''
  };

  const btn = document.getElementById('btn-save-project');
  if (btn) { btn.textContent = 'Creating...'; btn.disabled = true; }

  fetch(BACKEND_URL + '/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  })
  .then(function(data) {
    cancelEditCleanup();
    return loadData().then(function(projects) {
      allProjects = projects;
      buildMap();
      const newIdx = allProjects.findIndex(function(p) { return (p.id || p.grant_id) === data.id; });
      if (newIdx !== -1) showDetail(newIdx);
      else showList();
    });
  })
  .catch(function(err) {
    alert('Error: ' + err.message);
  })
  .finally(function() {
    if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
  });
}

function saveProjectEdits() {
  const p = allProjects[activeEditIdx];
  if (!p) return;
  const gid = p.id || p.grant_id;
  const btn = document.getElementById('btn-save-project');
  if (btn) { btn.textContent = 'Saving...'; btn.disabled = true; }

  const latVal = (document.getElementById('edit-lat') && document.getElementById('edit-lat').value) || '';
  const lngVal = (document.getElementById('edit-lng') && document.getElementById('edit-lng').value) || '';

  const updates = {
    title: (document.getElementById('edit-title') && document.getElementById('edit-title').value) || '',
    project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
    status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || '',
    shepard: (document.getElementById('edit-shepard') && document.getElementById('edit-shepard').value) || '',
    category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || '',
    amount: (document.getElementById('edit-amount') && document.getElementById('edit-amount').value) || '',
    partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
    narrative: easyMDEInstance ? easyMDEInstance.value() : '',
    position_lat: latVal,
    position_lng: lngVal
  };

  fetch(BACKEND_URL + '/api/projects/' + gid, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  })
  .then(function() {
    const links = [];
    document.querySelectorAll('#modal-links-list .link-row').forEach(function(r) {
      const inputs = r.querySelectorAll('input');
      if (inputs[0].value.trim() && inputs[1].value.trim()) {
        links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
      }
    });
    return fetch(BACKEND_URL + '/api/projects/' + gid + '/links', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ links: links })
    });
  })
  .then(function() {
    const fileInput = document.getElementById('modal-file-upload');
    if (fileInput && fileInput.files.length > 0) {
      const uploads = Array.from(fileInput.files).map(function(file) {
        const fd = new FormData();
        fd.append('file', file);
        return fetch(BACKEND_URL + '/api/projects/' + gid + '/upload', { method: 'POST', body: fd });
      });
      return Promise.all(uploads);
    }
  })
  .then(function() {
    const parsedLat = parseFloat(latVal);
    const parsedLng = parseFloat(lngVal);
    if (!isNaN(parsedLat) && !isNaN(parsedLng) && markers[activeEditIdx]) {
      markers[activeEditIdx].setPosition(new google.maps.LatLng(parsedLat, parsedLng));
    }
    cancelEditCleanup();
    return loadData();
  })
  .then(function(projects) {
    allProjects = projects;
    showDetail(activeEditIdx);
  })
  .catch(function(err) {
    alert('Error updating project: ' + err.message);
  })
  .finally(function() {
    if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
  });
}

window.showDiffModal = function () {
  const modal = document.getElementById('diff-modal');
  const container = document.getElementById('diff-output-container');
  const countLabel = document.getElementById('diff-file-count');
  modal.style.display = 'flex';
  container.innerHTML = 'Fetching repository diff from orchestrator...';
  countLabel.textContent = '';

  fetch(BACKEND_URL + '/api/diff')
    .then(function(res) {
      if (!res.ok) throw new Error('Failed to retrieve diff');
      return res.json();
    })
    .then(function(data) {
      if (data.status === 'clean') {
        container.innerHTML = '<span style="color:#94a3b8;">✔ Working tree is clean. No uncommitted modifications.</span>';
        countLabel.textContent = '0 files changed';
        return;
      }

      let out = '';
      if (data.untracked && data.untracked.length > 0) {       out += '<span style="color:#f59e0b;font-weight:bold;">Untracked New Files:</span>\n';
        data.untracked.forEach(function(f) {
          out += '<span class="diff-line-add">? ' + escapeHtml(f) + '</span>\n';
        });
        out += '\n';
      }

      const diffLines = (data.diff || '').split('\n');
      diffLines.forEach(function(line) {
        const escaped = escapeHtml(line);
        if (line.startsWith('+++') || line.startsWith('---')) {
          out += '<span style="color:#94a3b8;font-weight:bold;">' + escaped + '</span>\n';
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
      countLabel.textContent = 'Status: ' + data.status;
    })
    .catch(function(err) {
      container.innerHTML = '<span style="color:#ef4444;">Error loading diff: ' + escapeHtml(err.message) + '</span>';
    });
};

window.closeDiffModal = function () {
  document.getElementById('diff-modal').style.display = 'none';
};

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function initMaintainerClient() {
  return;
}

window.triggerSync = function (dryRun) {
  if (dryRun === undefined) dryRun = true;
  window.toggleLogConsole(true);
  fetch(BACKEND_URL + '/api/sync?dry_run=' + dryRun, { method: 'POST' });
};

window.publishChanges = function () {
  const msg = prompt('Commit message:', 'chore(sync): automated grant update');
  if (!msg) return;
  fetch(BACKEND_URL + '/api/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg })
  })
  .then(function(res) { return res.json(); })
  .then(function(data) {
    alert(data.message || 'Published commit: ' + data.commit);
  })
  .catch(function() {
    alert('Publish failed. Check orchestrator logs.');
  });
};

window.toggleLogConsole = function (forceOpen) {
  const drawer = document.getElementById('log-drawer');
  if (drawer) drawer.style.display = forceOpen || drawer.style.display === 'none' ? 'block' : 'none';
};

function renderMarkdown() {
  const el = document.getElementById('narrative-body');
  if (!el || !window.marked) return;
  const raw = el.dataset.raw ? decodeURIComponent(el.dataset.raw) : '';
  if (!raw.trim()) return;
  el.innerHTML = marked.parse(raw);
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

function initDivider() {
  const divider = document.getElementById('divider');
  const mapPane = document.getElementById('map-pane');
  const app = document.getElementById('app');
  let dragging = false, startX = 0, startWidth = 0;

  divider.addEventListener('mousedown', function(e) {
    dragging = true;
    startX = e.clientX;
    startWidth = mapPane.getBoundingClientRect().width;
    divider.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    const appWidth = app.getBoundingClientRect().width;
    const newWidth = startWidth + (e.clientX - startX);
    const pct = Math.min(Math.max(newWidth / appWidth * 100, 15), 85);
    mapPane.style.flex = '0 0 ' + pct + '%';
  });

  document.addEventListener('mouseup', function() {
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
