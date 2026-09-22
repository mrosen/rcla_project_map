// ============================================================
// RCLA Project Map — main.js
// Stable State: Deep-Linking (REST URLs) + Maintainer Mode
// ============================================================

const BACKEND_URL = (window.location.port === '8000')
  ? ''
  : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
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

function normalizeSpcUrl(url, guid) {
  if (url && typeof url === 'string') {
    return url.replace(/\/project\/detail\//g, '/project?guid=').trim();
  }
  if (guid) {
    return 'https://spc.rotary.org/project?guid=' + encodeURIComponent(guid);
  }
  return '';
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

// DataSource Mode: 'auto' (Supabase if available), 'supabase', or 'csv'
function getDataSourceMode() {
  var urlParams = new URLSearchParams(window.location.search);
  var param = urlParams.get('source') || urlParams.get('datasource') || urlParams.get('data');
  if (param) {
    if (param.toLowerCase() === 'csv') return 'csv';
    if (param.toLowerCase() === 'supabase' || param.toLowerCase() === 'cloud') return 'supabase';
  }
  return 'supabase';
}

function setDataSourceMode(mode) {
  sessionStorage.setItem('rcla_data_source', mode);
}

window.toggleDataSource = function () {
  var current = getDataSourceMode();
  var next = (current === 'csv') ? 'supabase' : 'csv';
  setDataSourceMode(next);

  var newUrl = new URL(window.location);
  newUrl.searchParams.set('source', next);
  window.history.replaceState({}, '', newUrl);

  var rp = document.getElementById('right-pane');
  if (rp) rp.innerHTML = '<div style="padding:20px;color:#1a3a5c;">Switching data source to ' + (next === 'csv' ? 'Legacy CSV' : 'Supabase Cloud') + '…</div>';

  loadData().then(function (projects) {
    allProjects = projects;
    rebuildMarkers();
    if (currentView === 'overview') showOverview();
    else if (currentView === 'list') renderListRows();
    else if (currentView === 'detail' && allProjects[currentIndex]) showDetail(currentIndex);
    else showOverview();
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
      indicator.title = 'Live connection to Supabase Cloud (' + count + ' projects). Click to toggle Maintainer Mode.';
    }
    if (text) text.textContent = '⚡ Supabase Cloud (' + count + ')';
    if (dbBadge) {
      dbBadge.textContent = '⚡ DB: Supabase (Live)';
      dbBadge.style.background = '#059669';
    }
  } else {
    if (indicator) {
      indicator.style.background = 'rgba(245, 158, 11, 0.25)';
      indicator.style.borderColor = '#f59e0b';
      indicator.style.color = '#fbbf24';
      indicator.title = 'Running on Legacy CSV backup (' + (count || 0) + ' projects). Click to toggle Maintainer Mode.';
    }
    if (text) text.textContent = '📁 Legacy CSV (' + (count || 0) + ')';
    if (dbBadge) {
      dbBadge.textContent = '📁 DB: Legacy CSV';
      dbBadge.style.background = '#d97706';
    }
  }
}

function loadData() {
  if (getDataSourceMode() === 'csv') {
    console.log('Loading project data from Legacy CSV (requested mode: CSV)...');
    return loadCsvFallback().then(function (data) {
      updateBackendStatus('csv', data.length);
      return data;
    });
  }

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
    mapTypeControlOptions: {
      style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
      position: google.maps.ControlPosition.TOP_LEFT,
      mapTypeIds: [
        'roadmap',
        'satellite',
        'hybrid',
        'terrain'
      ]
    },
    fullscreenControl: true
  });
  rebuildMarkers();
  initPlacesSearch();
}

function initPlacesSearch() {
  var input = document.getElementById('map-search-input');
  if (!input || !window.google || !google.maps || !google.maps.places) return;
  try {
    var autocomplete = new google.maps.places.Autocomplete(input);
    autocomplete.bindTo('bounds', map);
    autocomplete.addListener('place_changed', function () {
      var place = autocomplete.getPlace();
      if (!place || !place.geometry || !place.geometry.location) return;
      if (searchMarker) searchMarker.setMap(null);
      searchMarker = new google.maps.Marker({
        map: map,
        position: place.geometry.location,
        title: place.name || 'Searched location',
        icon: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png'
      });
      if (place.geometry.viewport) {
        map.fitBounds(place.geometry.viewport);
      } else {
        map.setCenter(place.geometry.location);
        map.setZoom(15);
      }
    });
  } catch (e) {
    console.warn('Could not initialize Google Places Autocomplete:', e);
  }
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
    var pos = active.getPosition();
    if (pos) {
      var bounds = map.getBounds();
      // If the marker is not currently within the visible viewport, pan to bring it into view
      if (!bounds || !bounds.contains(pos)) {
        map.panTo(pos);
      }
    }
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

      if (currentView === 'overview') updateOverviewContent();
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

  var rp = document.getElementById('right-pane');
  var panel = document.getElementById('overview-panel');

  if (!panel) {
    rp.innerHTML = ''
      + '<div class="panel" id="overview-panel">'
      + '  <h2>Club Projects Overview <span id="ov-filter-notice"></span></h2>'
      +    renderFilterBar()
      + '  <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:14px;line-height:1.7;margin-bottom:16px;">'
      + '    <p>The Rotary Club of Lake Atitlán funds community development projects across Guatemala through Global Grants, District Grants, Club-to-Club collaborations, and direct club donations.</p>'
      + '  </div>'
      + '  <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:10px;margin-bottom:16px;">'
      + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
      + '      <div id="ov-total-count" style="font-size:22px;font-weight:bold;color:#1a3a5c;">0</div>'
      + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Projects in View</div>'
      + '    </div>'
      + '    <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:12px;text-align:center;">'
      + '      <div id="ov-total-funding" style="font-size:22px;font-weight:bold;color:#1a3a5c;">$0.00M</div>'
      + '      <div style="font-size:11px;color:#888;text-transform:uppercase;">Funding in View</div>'
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
  }

  updateOverviewContent();
}

function updateOverviewContent() {
  var filtered = getFilteredProjects();
  syncMapMarkers(filtered);

  var totalFunding = filtered.reduce(function (s, p) { return s + (Number(p.amount) || Number(p.budget) || 0); }, 0);
  var ggCount = filtered.filter(function (p) { return getProjectType(p) === 'Global Grant'; }).length;
  var directCount = filtered.filter(function (p) { return getProjectType(p) !== 'Global Grant'; }).length;

  var isFiltered = currentFilters.type || currentFilters.status || currentFilters.category || currentFilters.year || currentFilters.search;
  var noticeEl = document.getElementById('ov-filter-notice');
  if (noticeEl) {
    noticeEl.innerHTML = isFiltered ? '<span style="font-size:12px;color:#d97706;font-weight:normal;"> (Filtered: ' + filtered.length + ' of ' + allProjects.length + ')</span>' : '';
  }

  var countEl = document.getElementById('ov-total-count');
  if (countEl) countEl.textContent = filtered.length;

  var fundingEl = document.getElementById('ov-total-funding');
  if (fundingEl) fundingEl.textContent = '$' + (totalFunding / 1e6).toFixed(2) + 'M';

  var splitEl = document.getElementById('ov-split-count');
  if (splitEl) splitEl.textContent = ggCount + ' / ' + directCount;

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

// --- Table Sorting & Marker Hover Animation ---
var activeHoverMarker = null;
var hoverPulseTimeout = null;

window.hoverMarkerStart = function (idx) {
  var m = markers[idx];
  if (!m || !window.google || !google.maps) return;

  // If this marker is already the active hover marker, let it continue
  if (activeHoverMarker === m && hoverPulseTimeout) return;

  window.hoverMarkerStop();

  activeHoverMarker = m;
  m.setZIndex(1000);
  m.setAnimation(google.maps.Animation.BOUNCE);

  // Stop animating after ~800ms (1-2 bounce cycles)
  hoverPulseTimeout = setTimeout(function () {
    if (activeHoverMarker === m) {
      m.setAnimation(null);
      m.setZIndex(idx === currentIndex && currentView === 'detail' ? 999 : 1);
      activeHoverMarker = null;
      hoverPulseTimeout = null;
    }
  }, 800);
};

window.hoverMarkerStop = function () {
  if (hoverPulseTimeout) {
    clearTimeout(hoverPulseTimeout);
    hoverPulseTimeout = null;
  }
  if (activeHoverMarker) {
    activeHoverMarker.setAnimation(null);
    var oldIdx = markers.indexOf(activeHoverMarker);
    activeHoverMarker.setZIndex(oldIdx === currentIndex && currentView === 'detail' ? 999 : 1);
    activeHoverMarker = null;
  }
};

let tableSort = {
  column: null,
  direction: 'asc'
};

function sortProjects(list, column, direction) {
  if (!column) return list;
  var factor = direction === 'desc' ? -1 : 1;
  return list.slice().sort(function (a, b) {
    var valA, valB;
    switch (column) {
      case 'id':
        valA = String(a.id || a.grant_id || '').toLowerCase();
        valB = String(b.id || b.grant_id || '').toLowerCase();
        return valA.localeCompare(valB, undefined, { numeric: true }) * factor;
      case 'title':
        valA = String(a.title || '').toLowerCase();
        valB = String(b.title || '').toLowerCase();
        return valA.localeCompare(valB) * factor;
      case 'project_type':
        valA = String(getProjectType(a) || '').toLowerCase();
        valB = String(getProjectType(b) || '').toLowerCase();
        return valA.localeCompare(valB) * factor;
      case 'category':
        valA = String(a.category || '').toLowerCase();
        valB = String(b.category || '').toLowerCase();
        return valA.localeCompare(valB) * factor;
      case 'start_year':
        valA = Number(a.start_year) || 0;
        valB = Number(b.start_year) || 0;
        return (valA - valB) * factor;
      case 'status':
        valA = String(a.status || '').toLowerCase();
        valB = String(b.status || '').toLowerCase();
        return valA.localeCompare(valB) * factor;
      case 'amount':
        valA = Number(a.amount) || Number(a.budget) || 0;
        valB = Number(b.amount) || Number(b.budget) || 0;
        return (valA - valB) * factor;
      default:
        return 0;
    }
  });
}

function attachTableSortListeners() {
  var table = document.getElementById('project-table');
  if (!table) return;
  var headers = table.querySelectorAll('th[data-col]');
  headers.forEach(function (th) {
    th.addEventListener('click', function () {
      var col = th.getAttribute('data-col');
      if (tableSort.column === col) {
        tableSort.direction = (tableSort.direction === 'asc') ? 'desc' : 'asc';
      } else {
        tableSort.column = col;
        tableSort.direction = (col === 'amount' || col === 'start_year') ? 'desc' : 'asc';
      }
      updateSortIndicators();
      renderListRows();
    });
  });
}

function updateSortIndicators() {
  var table = document.getElementById('project-table');
  if (!table) return;
  var headers = table.querySelectorAll('th[data-col]');
  headers.forEach(function (th) {
    var col = th.getAttribute('data-col');
    var baseTitle = th.getAttribute('data-label') || th.textContent.replace(/[▲▼↕\s]+$/, '');
    th.setAttribute('data-label', baseTitle);
    if (tableSort.column === col) {
      var icon = tableSort.direction === 'asc' ? ' ▲' : ' ▼';
      th.innerHTML = baseTitle + ' <span style="font-size:10px;display:inline-block;">' + icon + '</span>';
      th.style.background = '#0e253c';
    } else {
      th.innerHTML = baseTitle + ' <span style="opacity:0.35;font-size:9px;display:inline-block;">↕</span>';
      th.style.background = '#1a3a5c';
    }
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
  var panel = document.getElementById('list-panel');
  if (!panel) {
    rp.innerHTML = ''
      + '<div class="panel" id="list-panel">'
      + '  <h2>All Projects</h2>'
      +    renderFilterBar()
      + '  <table id="project-table">'
      + '    <thead>'
      + '      <tr>'
      + '        <th data-col="id" title="Click to sort by ID">ID</th>'
      + '        <th data-col="title" title="Click to sort by Project Title">Project</th>'
      + '        <th data-col="project_type" title="Click to sort by Type">Type</th>'
      + '        <th data-col="category" title="Click to sort by Category">Category</th>'
      + '        <th data-col="start_year" title="Click to sort by Year">Year</th>'
      + '        <th data-col="status" title="Click to sort by Status">Status</th>'
      + '        <th data-col="amount" style="text-align:right" title="Click to sort by Budget">Budget</th>'
      + '      </tr>'
      + '    </thead>'
      + '    <tbody id="project-tbody"></tbody>'
      + '  </table>'
      + '</div>';

    attachFilterListeners();
    attachTableSortListeners();
  }

  updateSortIndicators();
  renderListRows();
}

function renderListRows() {
  var filtered = getFilteredProjects();
  if (tableSort.column) {
    filtered = sortProjects(filtered, tableSort.column, tableSort.direction);
  }
  syncMapMarkers(filtered);
  var tbody = document.getElementById('project-tbody');
  if (!tbody) return;

  var rowsHtml = '';
  filtered.forEach(function (p) {
    var idx = allProjects.indexOf(p);
    var amt = p.amount ? '$' + Number(p.amount).toLocaleString() : (p.budget ? '$' + Number(p.budget).toLocaleString() : '—');
    var pStatus = (p.status || '').toLowerCase();
    rowsHtml += '<tr onclick="showDetail(' + idx + ')" onmouseenter="hoverMarkerStart(' + idx + ')" onmouseleave="hoverMarkerStop()">'
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
  window.hoverMarkerStop && window.hoverMarkerStop();
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

  // SPC Link Badge
  var spcBadge = '';
  var spcData = project.sync_status && project.sync_status.spc;
  var spcUrl = normalizeSpcUrl(spcData && (spcData.spc_url || spcData.spc_project_id), spcData && spcData.spc_project_id);
  if (!spcUrl && project.project_links) {
    var sLink = project.project_links.find(function (l) { return l.url && l.url.indexOf('spc.rotary.org') !== -1; });
    if (sLink) spcUrl = normalizeSpcUrl(sLink.url);
  }
  if (spcUrl) {
    spcBadge = '<a href="' + escapeHtml(spcUrl) + '" target="_blank" style="background:#2563eb;color:white;text-decoration:none;padding:5px 10px;border-radius:4px;font-size:12px;display:inline-flex;align-items:center;gap:4px;font-weight:bold;" title="View on Rotary Service Project Center">🌐 View on SPC</a>';
  }

  // Lead Brief Overview
  var briefLead = '';
  if (project.brief_overview && project.brief_overview.trim()) {
    briefLead = '<div style="font-size:14px;color:#1e3a8a;background:#eff6ff;border-left:4px solid #3b82f6;padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:14px;line-height:1.5;font-weight:500;">'
      + escapeHtml(project.brief_overview.trim())
      + '</div>';
  }

  // Timeline & Milestones section
  var timelineHtml = '';
  var tObj = project.timeline;
  if (tObj && (tObj.backstory || (tObj.milestones && tObj.milestones.length > 0))) {
    timelineHtml += '<h3>⏱️ Project Timeline & Milestones</h3>';
    if (tObj.backstory && tObj.backstory.trim()) {
      timelineHtml += '<div style="background:#fff;border:1px solid #ddd;border-radius:6px;padding:12px;margin-bottom:12px;line-height:1.6;font-size:13px;color:#334155;">'
        + '<div style="font-weight:bold;font-size:11px;color:#64748b;text-transform:uppercase;margin-bottom:4px;">Backstory & Origins</div>'
        + escapeHtml(tObj.backstory.trim())
        + '</div>';
    }
    if (tObj.milestones && tObj.milestones.length > 0) {
      timelineHtml += '<div class="timeline-container">';
      tObj.milestones.forEach(function (m) {
        timelineHtml += '<div class="timeline-step">'
          + (m.date ? '<div class="timeline-date">' + escapeHtml(m.date) + '</div>' : '')
          + '<div class="timeline-title">' + escapeHtml(m.name || '') + '</div>'
          + (m.notes ? '<div class="timeline-notes">' + escapeHtml(m.notes) + '</div>' : '')
          + '</div>';
      });
      timelineHtml += '</div>';
    }
  }

  // Details Breakdown section
  var detailsHtml = '';
  var dObj = project.details;
  if (dObj && (dObj.world_fund || dObj.district_ddf || dObj.club_contributions || dObj.host_club || dObj.international_club || (dObj.partner_clubs && dObj.partner_clubs.length) || (dObj.partner_districts && dObj.partner_districts.length) || (dObj.cooperating_organizations && dObj.cooperating_organizations.length))) {
    detailsHtml += '<h3>💰 Funding, Clubs & Partners</h3>'
      + '<div class="meta-grid" style="margin-bottom:10px;">';
    if (dObj.world_fund) {
      detailsHtml += '<div class="meta-item"><label>TRF World Fund</label><span>$' + Number(dObj.world_fund).toLocaleString() + '</span></div>';
    }
    if (dObj.district_ddf) {
      detailsHtml += '<div class="meta-item"><label>District DDF</label><span>$' + Number(dObj.district_ddf).toLocaleString() + '</span></div>';
    }
    if (dObj.club_contributions) {
      detailsHtml += '<div class="meta-item"><label>Club Contributions</label><span>$' + Number(dObj.club_contributions).toLocaleString() + '</span></div>';
    }
    if (dObj.host_club) {
      var hLabel = escapeHtml(dObj.host_club) + (dObj.host_district ? ' (D' + escapeHtml(dObj.host_district) + ')' : '');
      detailsHtml += '<div class="meta-item"><label>Host Club</label><span>' + hLabel + '</span></div>';
    }
    if (dObj.international_club) {
      var iLabel = escapeHtml(dObj.international_club) + (dObj.international_district ? ' (D' + escapeHtml(dObj.international_district) + ')' : '');
      detailsHtml += '<div class="meta-item"><label>International Sponsor</label><span>' + iLabel + '</span></div>';
    }
    detailsHtml += '</div>';

    // Partner Clubs
    var pClubs = dObj.partner_clubs || [];
    if (typeof pClubs === 'string') pClubs = pClubs.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    if (pClubs.length > 0) {
      detailsHtml += '<div style="margin-bottom:8px;font-size:12px;">'
        + '<strong style="color:#475569;">Contributing / Partner Clubs:</strong> '
        + pClubs.map(function (c) {
            return '<span class="badge" style="background:#e0f2fe;color:#0369a1;font-size:11px;margin:2px 3px;display:inline-block;">' + escapeHtml(c) + '</span>';
          }).join('')
        + '</div>';
    }

    // Partner Districts
    var pDists = dObj.partner_districts || [];
    if (typeof pDists === 'string') pDists = pDists.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    if (pDists.length > 0) {
      detailsHtml += '<div style="margin-bottom:8px;font-size:12px;">'
        + '<strong style="color:#475569;">Partner Districts:</strong> '
        + pDists.map(function (d) {
            var label = d.toString().toLowerCase().indexOf('d') === 0 || d.toString().toLowerCase().indexOf('district') === 0 ? d : 'District ' + d;
            return '<span class="badge" style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;font-size:11px;margin:2px 3px;display:inline-block;">' + escapeHtml(label) + '</span>';
          }).join('')
        + '</div>';
    }

    // Cooperating Organizations / NGOs
    var pOrgs = dObj.cooperating_organizations || [];
    if (typeof pOrgs === 'string') pOrgs = pOrgs.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    if (pOrgs.length > 0) {
      detailsHtml += '<div style="margin-bottom:12px;font-size:12px;">'
        + '<strong style="color:#475569;">Partner Organizations / NGOs:</strong> '
        + pOrgs.map(function (o) {
            return '<span class="badge" style="background:#fef3c7;color:#92400e;font-size:11px;margin:2px 3px;display:inline-block;">' + escapeHtml(o) + '</span>';
          }).join('')
        + '</div>';
    }
  }

  // Complete Overview (if set and distinct from narrative)
  var completeOverviewHtml = '';
  if (project.complete_overview && project.complete_overview.trim() && project.complete_overview.trim() !== rawText.trim()) {
    completeOverviewHtml = '<div style="background:#fff;border:1px solid #ddd;border-radius:6px;padding:12px;line-height:1.6;color:#334155;margin-bottom:12px;">'
      + '<div style="font-weight:bold;font-size:11px;color:#64748b;text-transform:uppercase;margin-bottom:4px;">Complete Overview (SPC)</div>'
      + escapeHtml(project.complete_overview.trim())
      + '</div>';
  }

  rp.innerHTML = ''
    + '<div class="panel" id="detail-panel" tabindex="0" style="outline:none;">'
    + '  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">'
    + '    <div style="flex:1">'
    + '      <h2 style="border:none;padding:0;margin-bottom:4px;">' + (project.title || 'Untitled') + '</h2>'
    + '      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
    + '        <span class="badge badge-type">' + pType + '</span>'
    + '        <span class="badge badge-' + pStatus + '">' + (project.status || '—') + '</span>'
    + '        <span style="color:#888;font-size:12px;">' + gid + '</span>'
    + '        <span style="color:#888;font-size:12px;">' + (project.start_date || project.start_year || '') + (project.end_date ? ' → ' + project.end_date : '') + '</span>'
    + '      </div>'
    + '    </div>'
    + '    <div style="display:flex;gap:6px;">'
    +        spcBadge
    +        editBtn
    + '      <button type="button" onclick="showList()" style="background:#1a3a5c;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;">← All Projects</button>'
    + '    </div>'
    + '  </div>'
    +    briefLead
    + '  <div id="photo-area"></div>'
    +    completeOverviewHtml
    + '  <h3 style="margin-top:16px;margin-bottom:6px;">Summary & Narrative</h3>'
    + '  <div class="narrative" id="narrative-body" data-raw="' + encodeURIComponent(rawText) + '" style="padding:10px;background:#fff;border:1px solid #ddd;border-radius:6px;line-height:1.6;">'
    +      (rawText || 'No narrative available yet.')
    + '  </div>'
    +    timelineHtml
    +    detailsHtml
    + '  <h3>Project Details & Meta</h3>'
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

  if (getDataSourceMode() !== 'csv' && p && (p.project_assets !== undefined || p.project_links !== undefined)) {
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
  var rawAssets = project.project_assets || [];
  var rawLinks = project.project_links || [];

  // Deduplicate assets by filename
  var seenAssets = new Set();
  var assets = [];
  rawAssets.forEach(function (a) {
    var fn = (a.filename || '').trim();
    if (fn && !seenAssets.has(fn.toLowerCase())) {
      seenAssets.add(fn.toLowerCase());
      assets.push(a);
    }
  });

  // Deduplicate links by url
  var seenLinks = new Set();
  var links = [];
  rawLinks.forEach(function (l) {
    var u = (l.url || '').trim();
    if (u && !seenLinks.has(u.toLowerCase())) {
      seenLinks.add(u.toLowerCase());
      links.push(l);
    }
  });

  var images = assets.filter(function (a) {
    return a.file_type === 'image' || /\.(jpg|jpeg|png|gif|webp)$/i.test(a.filename);
  }).sort(function (a, b) {
    var da = (a.display_order !== undefined && a.display_order !== null) ? a.display_order : 99;
    var db = (b.display_order !== undefined && b.display_order !== null) ? b.display_order : 99;
    return da - db;
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
          var cap = a.caption || a.filename;
          return '<div style="display:flex;flex-direction:column;flex-shrink:0;align-items:center;">'
               + '  <img src="' + src + '" alt="' + escapeHtml(cap) + '" title="' + escapeHtml(cap) + '" onclick="window.open(this.src,\'_blank\')">'
               + (a.caption ? '<span style="font-size:11px;color:#64748b;margin-top:3px;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="' + escapeHtml(a.caption) + '">' + escapeHtml(a.caption) + '</span>' : '')
               + '</div>';
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
        var label = escapeHtml(a.caption || a.filename);
        if (a.caption && a.caption !== a.filename) {
          label += ' <span style="font-size:11px;color:#888;">(' + escapeHtml(a.filename) + ')</span>';
        }
        link.innerHTML = '<span class="file-icon">' + icon + '</span> ' + label;
        list.appendChild(link);
      });
      links.forEach(function (l) {
        var a = document.createElement('a');
        var linkUrl = (l.url && l.url.indexOf('spc.rotary.org') !== -1) ? normalizeSpcUrl(l.url) : (l.url || '');
        a.href = linkUrl;
        a.target = '_blank';
        a.innerHTML = '<span class="file-icon">🔗</span> ' + escapeHtml(l.label || linkUrl);
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
// EDIT PROJECT FORM, TIMELINE, AI SYNTHESIS & ASSET MANAGEMENT
// ============================================================

window.updateTitleCharCounter = function () {
  var inp = document.getElementById('edit-title');
  var badge = document.getElementById('counter-title');
  if (!inp || !badge) return;
  var len = inp.value.length;
  badge.textContent = len + ' / 50';
  if (len > 50) {
    badge.className = 'char-counter counter-limit';
  } else if (len >= 45) {
    badge.className = 'char-counter counter-warn';
  } else {
    badge.className = 'char-counter counter-normal';
  }
};

window.updateBriefCharCounter = function () {
  var inp = document.getElementById('edit-brief-overview');
  var badge = document.getElementById('counter-brief');
  if (!inp || !badge) return;
  var len = inp.value.length;
  badge.textContent = len + ' / 100 characters';
  if (len > 100) {
    badge.className = 'char-counter counter-limit';
  } else if (len >= 85) {
    badge.className = 'char-counter counter-warn';
  } else {
    badge.className = 'char-counter counter-normal';
  }
};

window.updateCompleteCharCounter = function () {
  var inp = document.getElementById('edit-complete-overview');
  var badge = document.getElementById('counter-complete');
  if (!inp || !badge) return;
  var len = inp.value.length;
  badge.textContent = len.toLocaleString() + ' / 1,000 characters';
  if (len > 1000) {
    badge.className = 'char-counter counter-limit';
  } else if (len >= 900) {
    badge.className = 'char-counter counter-warn';
  } else {
    badge.className = 'char-counter counter-normal';
  }
};

window.loadProjectSyncStatus = async function (projectId) {
  var badgesEl = document.getElementById('edit-sync-badges');
  var actionsEl = document.getElementById('edit-sync-actions');
  if (!badgesEl) return;

  var p = allProjects.find(function (item) {
    return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
  });

  function renderSyncChips(gc, spc) {
    var isGG = projectId.toUpperCase().startsWith('GG');
    var isDG = projectId.toUpperCase().startsWith('DG');
    var prefix = isGG ? 'GG' : (isDG ? 'DG' : 'Grant');
    var reportCount = gc.report_count || 0;
    var reportTxt = reportCount > 0 ? ' (+' + reportCount + ' status report PDF' + (reportCount > 1 ? 's' : '') + ')' : '';

    var gcHtml = gc.has_application_pdf
      ? '<span class="sync-chip chip-green" title="' + escapeHtml(gc.application_pdf_name || '') + '">📄 ' + prefix + ' Appl PDF on file' + reportTxt + '</span>'
      : '<span class="sync-chip chip-gray">📄 No ' + prefix + ' Appl PDF</span>';

    var spcUrl = normalizeSpcUrl(spc.spc_url || spc.spc_project_id, spc.spc_project_id);
    var spcHtml = spc.exported
      ? (spcUrl
          ? '<a href="' + escapeHtml(spcUrl) + '" target="_blank" class="sync-chip chip-green" style="text-decoration:none;display:inline-flex;align-items:center;gap:4px;" title="View on Rotary Service Project Center">✓ Synced to SPC ↗</a>'
          : '<span class="sync-chip chip-green">✓ Synced to SPC</span>')
      : '<span class="sync-chip chip-gray">Not exported to SPC</span>';

    badgesEl.innerHTML = gcHtml + spcHtml;
  }

  // 1. Initial optimistic render from local / Supabase project memory
  var localGc = (p && p.sync_status && p.sync_status.grant_center) ? Object.assign({}, p.sync_status.grant_center) : {};
  var localSpc = (p && p.sync_status && p.sync_status.spc) ? Object.assign({}, p.sync_status.spc) : {};

  if (p && p.project_assets && p.project_assets.length > 0) {
    var hasApp = p.project_assets.some(function (a) { return /application.*\.pdf$/i.test(a.filename || ''); });
    var repCount = p.project_assets.filter(function (a) { return /report.*\.pdf$/i.test(a.filename || ''); }).length;
    if (hasApp) localGc.has_application_pdf = true;
    if (repCount > 0 && !localGc.report_count) localGc.report_count = repCount;
  }
  if (p && p.project_links && !localSpc.exported) {
    var spcLink = p.project_links.find(function (l) { return l.url && l.url.indexOf('spc.rotary.org') !== -1; });
    if (spcLink) {
      localSpc.exported = true;
      localSpc.spc_url = normalizeSpcUrl(spcLink.url);
    }
  }

  // Render initial state immediately so badges appear without delay
  renderSyncChips(localGc, localSpc);

  // 2. Query live backend daemon if available
  try {
    var res = await fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/sync-status');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();
    var gc = data.grant_center || {};
    var spc = data.spc || {};

    renderSyncChips(gc, spc);

    // Update in-memory project so detail view and links list have the SPC link immediately!
    if (p) {
      if (!p.sync_status) p.sync_status = {};
      p.sync_status.grant_center = gc;
      p.sync_status.spc = spc;
      var liveSpcUrl = normalizeSpcUrl(spc.spc_url || spc.spc_project_id, spc.spc_project_id);
      if (spc.exported && liveSpcUrl) {
        p.sync_status.spc.spc_url = liveSpcUrl;
        if (!p.project_links) p.project_links = [];
        var existingSpcLink = p.project_links.find(function (l) {
          return (l.url && l.url.indexOf('spc.rotary.org') !== -1) || l.label === 'Rotary Service Project Center (SPC)';
        });
        if (existingSpcLink) {
          existingSpcLink.url = liveSpcUrl;
        } else {
          p.project_links.push({
            project_id: projectId,
            label: 'Rotary Service Project Center (SPC)',
            url: liveSpcUrl,
            display_order: p.project_links.length
          });
        }
      }
    }

    var actionsHtml = ''
      + '<button type="button" onclick="triggerProjectRiFetch(\'' + projectId + '\')" style="padding:4px 8px;font-size:11px;background:#e2e8f0;border:none;border-radius:4px;cursor:pointer;">📥 Re-check RI</button>'
      + '<button type="button" onclick="triggerProjectSpcExport(\'' + projectId + '\', true)" style="padding:4px 8px;font-size:11px;background:#2563eb;color:white;border:none;border-radius:4px;cursor:pointer;font-weight:bold;" title="Audit and validate payload for SPC without submitting">🧪 SPC Dry Run</button>'
      + '<button type="button" onclick="triggerProjectSpcExport(\'' + projectId + '\', false)" style="padding:4px 8px;font-size:11px;background:#1d4ed8;color:white;border:none;border-radius:4px;cursor:pointer;font-weight:bold;" title="Authenticate with My Rotary and create project in SPC">🚀 SPC Live Export</button>';
    if (actionsEl) actionsEl.innerHTML = actionsHtml;
  } catch (err) {
    // If backend daemon is offline (e.g. static hosting on GitHub Pages), retain the local sync chips!
    if (actionsEl) actionsEl.innerHTML = '';
  }
};

window.triggerProjectRiFetch = async function (projectId) {
  window.currentActiveProjectId = projectId;
  if (!confirm('Fetch files and reconcile attachments from Rotary Grant Center for ' + projectId + '?')) return;
  if (window.toggleLogConsole) window.toggleLogConsole(true);
  if (window.startLogPolling) window.startLogPolling(20000);
  try {
    var res = await fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/fetch-ri-files', { method: 'POST' });
    var data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Fetch failed');
  } catch (e) {
    alert('Error triggering RI fetch: ' + e.message);
  }
};

window.triggerProjectSpcExport = async function (projectId, dryRun) {
  window.currentActiveProjectId = projectId;
  if (dryRun === undefined) dryRun = true;
  if (!dryRun) {
    if (!confirm('Proceed with LIVE export to Rotary Service Project Center (SPC) for project ' + projectId + '?\n\nThis will launch the SPC automation, authenticate with My Rotary, and create the project entry in Rotary International.')) {
      return;
    }
  }

  // Immediately open the log console and print an instant status line
  if (window.toggleLogConsole) window.toggleLogConsole(true);
  var logDiv = document.getElementById('log-output');
  if (logDiv) {
    var startLine = document.createElement('div');
    startLine.className = 'log-line';
    startLine.style.color = '#38bdf8';
    startLine.textContent = '[' + new Date().toLocaleTimeString() + '] Initiating SPC export for ' + projectId + ' (' + (dryRun ? 'Dry Run' : 'Live') + ')...';
    logDiv.appendChild(startLine);
    var drawer = document.getElementById('log-drawer');
    if (drawer) drawer.scrollTop = drawer.scrollHeight;
  }

  // Start polling log history so the output appears in real-time
  if (window.startLogPolling) window.startLogPolling(20000);

  try {
    var res = await fetch(BACKEND_URL + '/api/projects/' + encodeURIComponent(projectId) + '/export-spc?dry_run=' + (dryRun ? 'true' : 'false'), { method: 'POST' });
    var data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Export failed');
  } catch (e) {
    if (logDiv) {
      var errLine = document.createElement('div');
      errLine.className = 'log-line';
      errLine.style.color = '#f87171';
      errLine.textContent = '❌ Error triggering SPC export: ' + e.message;
      logDiv.appendChild(errLine);
    }
  }
};

window.renderMilestonesBuilder = function (milestones, isGlobalGrant) {
  var container = document.getElementById('milestones-builder-container');
  if (!container) return;
  container.innerHTML = '';

  var list = milestones && Array.isArray(milestones) ? milestones.slice() : [];
  if (list.length === 0) {
    if (isGlobalGrant) {
      list = [
        { name: 'Submitted', date: '', notes: 'Formal grant submission' },
        { name: 'Approved', date: '', notes: 'Approved by The Rotary Foundation (TRF)' }
      ];
    } else {
      list = [
        { name: 'Project Initiated', date: '', notes: '' }
      ];
    }
  }

  list.forEach(function (m) {
    addMilestoneRow(m.name, m.date, m.notes);
  });
};

window.addMilestoneRow = function (name, date, notes) {
  var container = document.getElementById('milestones-builder-container');
  if (!container) return;
  var row = document.createElement('div');
  row.className = 'milestone-row';
  row.innerHTML = ''
    + '<input type="text" class="milestone-name" placeholder="Milestone (e.g. Submitted)" value="' + escapeHtml(name || '') + '">'
    + '<input type="text" class="milestone-date" placeholder="YYYY-MM-DD" value="' + escapeHtml(date || '') + '">'
    + '<input type="text" class="milestone-notes" placeholder="Notes or context..." value="' + escapeHtml(notes || '') + '">'
    + '<div style="display:flex;gap:2px;justify-content:flex-end;">'
    + '  <button type="button" onclick="moveMilestoneRow(this, -1)" style="border:none;background:#e2e8f0;padding:2px 5px;border-radius:2px;cursor:pointer;font-size:10px;">↑</button>'
    + '  <button type="button" onclick="moveMilestoneRow(this, 1)" style="border:none;background:#e2e8f0;padding:2px 5px;border-radius:2px;cursor:pointer;font-size:10px;">↓</button>'
    + '  <button type="button" onclick="this.closest(\'.milestone-row\').remove()" style="border:none;background:#fee2e2;color:#ef4444;padding:2px 5px;border-radius:2px;cursor:pointer;font-size:10px;">✕</button>'
    + '</div>';
  container.appendChild(row);
};

window.moveMilestoneRow = function (btn, dir) {
  var row = btn.closest('.milestone-row');
  if (!row) return;
  if (dir === -1 && row.previousElementSibling) {
    row.parentNode.insertBefore(row, row.previousElementSibling);
  } else if (dir === 1 && row.nextElementSibling) {
    row.parentNode.insertBefore(row.nextElementSibling, row);
  }
};

window.getTimelinePayload = function () {
  var backstory = (document.getElementById('edit-timeline-backstory') && document.getElementById('edit-timeline-backstory').value.trim()) || '';
  var milestones = [];
  document.querySelectorAll('#milestones-builder-container .milestone-row').forEach(function (r, idx) {
    var nameInp = r.querySelector('.milestone-name');
    var dateInp = r.querySelector('.milestone-date');
    var notesInp = r.querySelector('.milestone-notes');
    if (nameInp && nameInp.value.trim()) {
      milestones.push({
        id: 'm_' + (idx + 1),
        name: nameInp.value.trim(),
        date: dateInp ? dateInp.value.trim() : '',
        notes: notesInp ? notesInp.value.trim() : ''
      });
    }
  });
  return { backstory: backstory, milestones: milestones };
};

window.getDetailsPayload = function () {
  var wf = parseFloat((document.getElementById('edit-detail-world-fund') && document.getElementById('edit-detail-world-fund').value) || 0) || 0;
  var ddf = parseFloat((document.getElementById('edit-detail-ddf') && document.getElementById('edit-detail-ddf').value) || 0) || 0;
  var cash = parseFloat((document.getElementById('edit-detail-club-cash') && document.getElementById('edit-detail-club-cash').value) || 0) || 0;
  var host = (document.getElementById('edit-detail-host') && document.getElementById('edit-detail-host').value.trim()) || '';
  var intl = (document.getElementById('edit-detail-intl') && document.getElementById('edit-detail-intl').value.trim()) || '';
  var shep = (document.getElementById('edit-shepard') && document.getElementById('edit-shepard').value.trim()) || '';

  // Parse comma or newline separated partner clubs
  var rawClubs = (document.getElementById('edit-detail-partner-clubs') && document.getElementById('edit-detail-partner-clubs').value) || '';
  var partnerClubs = rawClubs.split(/[\n,]+/).map(function (s) { return s.trim(); }).filter(Boolean);

  // Parse comma or newline separated partner districts
  var rawDists = (document.getElementById('edit-detail-partner-districts') && document.getElementById('edit-detail-partner-districts').value) || '';
  var partnerDists = rawDists.split(/[\n,]+/).map(function (s) { return s.trim(); }).filter(Boolean);

  // Parse comma or newline separated cooperating organizations
  var rawOrgs = (document.getElementById('edit-detail-coop-orgs') && document.getElementById('edit-detail-coop-orgs').value) || '';
  var coopOrgs = rawOrgs.split(/[\n,]+/).map(function (s) { return s.trim(); }).filter(Boolean);

  var legacyPartner = (document.getElementById('edit-partner') && document.getElementById('edit-partner').value.trim()) || '';
  if (legacyPartner && coopOrgs.indexOf(legacyPartner) === -1) {
    coopOrgs.unshift(legacyPartner);
  }

  return {
    world_fund: wf,
    district_ddf: ddf,
    club_contributions: cash,
    host_club: host,
    international_club: intl,
    shepherd: shep,
    partner_clubs: partnerClubs,
    partner_districts: partnerDists,
    cooperating_organizations: coopOrgs
  };
};

window.synthesizeFromAi = async function (projectId, source, notesText, customApiKey) {
  var banner = document.getElementById('ai-status-banner');
  if (banner) {
    banner.style.display = 'block';
    banner.style.background = '#fef3c7';
    banner.style.borderColor = '#fde047';
    banner.style.color = '#854d0e';
    banner.textContent = '⏳ Google Gemini is analyzing project data and drafting structured fields...';
  }

  try {
    var payload = {
      source: source || 'pdf',
      notes_text: notesText || '',
      project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || ''
    };
    if (customApiKey) {
      payload.api_key = customApiKey.trim();
      sessionStorage.setItem('gemini_api_key', customApiKey.trim());
    }

    var data = null;

    // 1. If running locally or BACKEND_URL is available, try local orchestrator backend first
    var isLocalOrConfigured = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || (BACKEND_URL && !BACKEND_URL.includes('github.io')));
    if (isLocalOrConfigured) {
      try {
        var backendUrl = (BACKEND_URL || '') + '/api/projects/' + encodeURIComponent(projectId) + '/synthesize';
        var res = await fetch(backendUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        var contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          var jsonRes = await res.json();
          if (res.ok) {
            data = jsonRes;
          } else {
            var errDetail = jsonRes && jsonRes.detail;
            var errType = (errDetail && errDetail.error) || '';
            if (errType === 'GEMINI_API_KEY_REQUIRED' || errType === 'INVALID_API_KEY') {
              var userKey = prompt('Please enter your Google Gemini API key (obtain a free key at https://aistudio.google.com/app/apikey):');
              if (userKey && userKey.trim()) {
                sessionStorage.setItem('gemini_api_key', userKey.trim());
                return window.synthesizeFromAi(projectId, source, notesText, userKey.trim());
              }
              return;
            }
          }
        }
      } catch (backendErr) {
        console.warn('Backend orchestrator call failed, falling back to direct client-side synthesis:', backendErr);
      }
    }

    // 2. Direct client-side Gemini fallback (works on GitHub Pages or standalone static host)
    if (!data) {
      data = await synthesizeWithGeminiDirect(projectId, source, notesText, customApiKey);
    }

    if (data && data.draft) {
      applyAiDraftToForm(data.draft);
      if (banner) {
        banner.style.display = 'block';
        banner.style.background = '#dcfce7';
        banner.style.borderColor = '#86efac';
        banner.style.color = '#166534';
        banner.innerHTML = '✨ <strong>Gemini drafted project fields!</strong>'
          + (data.model_used ? ' <span style="font-size:11px;opacity:0.85;">(via ' + data.model_used + ')</span>' : '')
          + ' Review the overviews, timeline milestones, and details below before saving.';
      }
    }
  } catch (err) {
    if (banner) {
      banner.style.display = 'block';
      banner.style.background = '#fee2e2';
      banner.style.borderColor = '#fca5a5';
      banner.style.color = '#991b1b';
      banner.innerHTML = '❌ <strong>Gemini Error:</strong> ' + (err.message || err)
        + ' <button type="button" onclick="promptChangeGeminiKey(\'' + projectId + '\',\'' + (source || 'pdf') + '\')" style="margin-left:8px;padding:3px 8px;font-size:11px;font-weight:600;background:#dc2626;color:white;border:none;border-radius:4px;cursor:pointer;">🔑 Change API Key</button>'
        + ' <a href="https://aistudio.google.com/app/apikey" target="_blank" style="margin-left:6px;font-size:11px;text-decoration:underline;color:#991b1b;font-weight:600;">Get Key / Enable Billing</a>';
    }
  }
};

window.synthesizeWithGeminiDirect = async function (projectId, source, notesText, customApiKey) {
  var apiKey = customApiKey || sessionStorage.getItem('gemini_api_key') || localStorage.getItem('gemini_api_key');
  if (!apiKey) {
    var userKey = prompt('Please enter your Google Gemini API key (obtain a free key at https://aistudio.google.com/app/apikey):');
    if (!userKey || !userKey.trim()) {
      throw new Error('Gemini API key is required. Obtain a free key at https://aistudio.google.com/app/apikey');
    }
    apiKey = userKey.trim();
    sessionStorage.setItem('gemini_api_key', apiKey);
  }

  var isGlobalGrant = projectId.toUpperCase().startsWith('GG');
  var promptText = 'You are an expert archivist and project manager for the Rotary Club of Lake Atitlán (RCLA) in Guatemala.\n'
    + 'Analyze the following ' + (source === 'pdf' ? 'Rotary Foundation Grant Application' : 'project notes') + ' for project \'' + projectId + '\'.\n\n'
    + 'Extract and generate a clean, strictly formatted JSON response meeting these EXACT criteria:\n\n'
    + 'CRITICAL CONSTRAINTS:\n'
    + '1. "brief_overview": A punchy, compelling summary of what the project accomplished.\n'
    + '   STRICT MAXIMUM LENGTH: 100 CHARACTERS. Count every character carefully. Do not exceed 100 characters.\n'
    + '2. "complete_overview": A comprehensive description of the project purpose, community need, activities, and lasting impact.\n'
    + '   STRICT MAXIMUM LENGTH: 1,000 CHARACTERS. Count every character carefully. Do not exceed 1,000 characters.\n'
    + '3. "start_date": ISO date format (YYYY-MM-DD or YYYY-MM) for when the project was initiated or planned.\n'
    + '4. "end_date": ISO date format (YYYY-MM-DD or YYYY-MM) for when the project was completed (or null if ongoing).\n'
    + '5. "timeline":\n'
    + '   - "backstory": 1-2 paragraphs detailing the background, community relationship, and how the initiative started.\n'
    + '   - "milestones": A chronological list of milestones. Each milestone object must have:\n'
    + '     - "name": Milestone name\n'
    + '     - "date": ISO date (YYYY-MM-DD or YYYY-MM)\n'
    + '     - "notes": Brief note or context\n'
    + (isGlobalGrant ? '     CRITICAL: Since this is a Global Grant, you MUST include a milestone named "Submitted" and a milestone named "Approved", using dates extracted from the document.\n' : '     Include natural milestones such as Initiated, Fundraising, Distribution, Completed. Do NOT include formal RI approval steps unless stated.\n')
    + '6. "details":\n'
    + '   - "budget": Total numeric project budget in USD (numeric)\n'
    + '   - "world_fund": Rotary Foundation World Fund match in USD (numeric or 0)\n'
    + '   - "district_ddf": District Designated Fund (DDF) in USD (numeric or 0)\n'
    + '   - "club_contributions": Total club cash contributions in USD (numeric or 0)\n'
    + '   - "host_club": Name of the host Rotary club (e.g., "Club Rotario de Lake Atitlán")\n'
    + '   - "host_district": Host district number (e.g., "4250")\n'
    + '   - "international_club": International sponsor Rotary club name\n'
    + '   - "international_district": International district number\n'
    + '   - "partner_clubs": Array of strings of ALL contributing/partner Rotary clubs mentioned anywhere in the application or funding lists.\n'
    + '   - "partner_districts": Array of strings of ALL contributing/partner districts.\n'
    + '   - "cooperating_organizations": Array of strings of ALL partner NGOs, cooperating organizations, government entities, and community groups.\n'
    + '   - "key_personnel": Array of objects: [{"name": "...", "role": "..."}]\n\n'
    + 'Return ONLY valid JSON matching this schema.';

  var parts = [];

  if (source === 'pdf') {
    var pdfUrl = null;
    if (window.currentEditAssets && Array.isArray(window.currentEditAssets)) {
      var appAsset = window.currentEditAssets.find(function (a) {
        var fn = (a.filename || '').toLowerCase();
        return fn.includes('application') && fn.endsWith('.pdf');
      }) || window.currentEditAssets.find(function (a) {
        return (a.filename || '').toLowerCase().endsWith('.pdf');
      });
      if (appAsset) {
        pdfUrl = appAsset.public_url || (SUPABASE_URL + '/storage/v1/object/public/project-media/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(appAsset.filename));
      }
    }

    if (!pdfUrl) {
      pdfUrl = SUPABASE_URL + '/storage/v1/object/public/project-media/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(projectId) + '_Application.pdf';
    }

    var pdfRes = await fetch(pdfUrl);
    if (!pdfRes.ok && supabaseClient) {
      try {
        var sbRes = await supabaseClient.from('project_assets').select('*').eq('project_id', projectId).ilike('filename', '%application%.pdf');
        if (sbRes.data && sbRes.data.length > 0) {
          var matched = sbRes.data[0];
          var candidateUrl = matched.public_url || (SUPABASE_URL + '/storage/v1/object/public/project-media/' + matched.storage_path);
          pdfRes = await fetch(candidateUrl);
        }
      } catch (sbErr) {
        console.warn('Supabase asset query error:', sbErr);
      }
    }

    if (!pdfRes.ok) {
      throw new Error('Application PDF not found in storage for ' + projectId + '. Use "Draft from Notes" or upload the Application PDF.');
    }

    var pdfBuf = await pdfRes.arrayBuffer();
    var binary = '';
    var bytes = new Uint8Array(pdfBuf);
    var chunkSize = 8192;
    for (var i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    var base64Pdf = window.btoa(binary);

    parts.push({
      inline_data: {
        mime_type: 'application/pdf',
        data: base64Pdf
      }
    });
  } else if (source === 'notes') {
    if (!notesText || !notesText.trim()) {
      throw new Error('Please enter some project notes to synthesize.');
    }
    promptText += '\n\nPROJECT NOTES:\n"""\n' + notesText.trim() + '\n"""';
  }

  parts.push({ text: promptText });

  var candidateModels = [
    'gemini-3.1-flash-lite-preview',
    'gemini-flash-latest',
    'gemini-3.5-flash',
    'gemini-2.5-flash-lite'
  ];

  var lastError = null;
  var draft = null;
  var usedModel = null;

  for (var m = 0; m < candidateModels.length; m++) {
    var modelName = candidateModels[m];
    try {
      var gRes = await fetch('https://generativelanguage.googleapis.com/v1beta/models/' + modelName + ':generateContent?key=' + encodeURIComponent(apiKey), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: parts }],
          generationConfig: {
            response_mime_type: 'application/json',
            temperature: 0.2
          }
        })
      });

      if (!gRes.ok) {
        var errBody = await gRes.json().catch(function () { return {}; });
        var msg = (errBody.error && errBody.error.message) || ('HTTP ' + gRes.status);
        if (gRes.status === 400 && msg.includes('API_KEY_INVALID')) {
          sessionStorage.removeItem('gemini_api_key');
          throw new Error('The Gemini API key is invalid. Please click "Change API Key" and enter a valid key from Google AI Studio.');
        }
        if (gRes.status === 429) {
          throw new Error('Gemini API quota exceeded. Please wait a moment or use a Pay-As-You-Go key.');
        }
        lastError = new Error(msg);
        continue;
      }

      var gData = await gRes.json();
      var candidate = gData.candidates && gData.candidates[0];
      if (candidate && candidate.content && candidate.content.parts && candidate.content.parts[0]) {
        var rawText = candidate.content.parts[0].text;
        draft = JSON.parse(rawText);
        usedModel = modelName;
        break;
      }
    } catch (modelErr) {
      if (modelErr.message && (modelErr.message.includes('API key') || modelErr.message.includes('quota'))) {
        throw modelErr;
      }
      lastError = modelErr;
    }
  }

  if (!draft) {
    throw lastError || new Error('Failed to generate draft with Gemini.');
  }

  return { draft: draft, model_used: usedModel };
};

window.promptChangeGeminiKey = function (projectId, source) {
  var newKey = prompt('Enter your Google Gemini API key (obtain at https://aistudio.google.com/app/apikey):');
  if (newKey && newKey.trim()) {
    sessionStorage.setItem('gemini_api_key', newKey.trim());
    synthesizeFromAi(projectId, source, null, newKey.trim());
  }
};

window.applyAiDraftToForm = function (draft) {
  if (!draft) return;

  if (draft.brief_overview) {
    var bInp = document.getElementById('edit-brief-overview');
    if (bInp) { bInp.value = draft.brief_overview; updateBriefCharCounter(); }
  }
  if (draft.complete_overview) {
    var cInp = document.getElementById('edit-complete-overview');
    if (cInp) { cInp.value = draft.complete_overview; updateCompleteCharCounter(); }
  }
  if (draft.start_date) {
    var sInp = document.getElementById('edit-start-date');
    if (sInp) sInp.value = draft.start_date;
  }
  if (draft.end_date) {
    var eInp = document.getElementById('edit-end-date');
    if (eInp) eInp.value = draft.end_date;
  }
  if (draft.timeline) {
    if (draft.timeline.backstory) {
      var backInp = document.getElementById('edit-timeline-backstory');
      if (backInp) backInp.value = draft.timeline.backstory;
    }
    if (draft.timeline.milestones && Array.isArray(draft.timeline.milestones)) {
      var mContainer = document.getElementById('milestones-builder-container');
      if (mContainer) {
        mContainer.innerHTML = '';
        draft.timeline.milestones.forEach(function (m) {
          addMilestoneRow(m.name, m.date, m.notes);
        });
      }
    }
  }
  if (draft.details) {
    if (draft.details.budget !== undefined) {
      var amtInp = document.getElementById('edit-amount');
      if (amtInp && draft.details.budget > 0) amtInp.value = draft.details.budget;
    }
    if (draft.details.world_fund !== undefined) {
      var wfInp = document.getElementById('edit-detail-world-fund');
      if (wfInp) wfInp.value = draft.details.world_fund;
    }
    if (draft.details.district_ddf !== undefined) {
      var ddfInp = document.getElementById('edit-detail-ddf');
      if (ddfInp) ddfInp.value = draft.details.district_ddf;
    }
    if (draft.details.club_contributions !== undefined) {
      var cashInp = document.getElementById('edit-detail-club-cash');
      if (cashInp) cashInp.value = draft.details.club_contributions;
    }
    if (draft.details.host_club) {
      var hostInp = document.getElementById('edit-detail-host');
      if (hostInp) hostInp.value = draft.details.host_club + (draft.details.host_district ? ' (D' + draft.details.host_district + ')' : '');
    }
    if (draft.details.international_club) {
      var intlInp = document.getElementById('edit-detail-intl');
      if (intlInp) intlInp.value = draft.details.international_club + (draft.details.international_district ? ' (D' + draft.details.international_district + ')' : '');
    }
    if (draft.details.partner_clubs && Array.isArray(draft.details.partner_clubs) && draft.details.partner_clubs.length > 0) {
      var pClubsInp = document.getElementById('edit-detail-partner-clubs');
      if (pClubsInp) pClubsInp.value = draft.details.partner_clubs.join(', ');
    }
    if (draft.details.partner_districts && Array.isArray(draft.details.partner_districts) && draft.details.partner_districts.length > 0) {
      var pDistsInp = document.getElementById('edit-detail-partner-districts');
      if (pDistsInp) pDistsInp.value = draft.details.partner_districts.join(', ');
    }
    if (draft.details.cooperating_organizations && draft.details.cooperating_organizations.length > 0) {
      var orgsStr = Array.isArray(draft.details.cooperating_organizations) ? draft.details.cooperating_organizations.join(', ') : draft.details.cooperating_organizations;
      var coopInp = document.getElementById('edit-detail-coop-orgs');
      if (coopInp) coopInp.value = orgsStr;
      var partnerInp = document.getElementById('edit-partner');
      if (partnerInp) partnerInp.value = orgsStr;
    }
  }
};

window.openAiNotesModal = function (projectId) {
  var modal = document.getElementById('ai-notes-modal');
  var input = document.getElementById('ai-notes-input');
  var errorEl = document.getElementById('ai-notes-error');
  if (modal) {
    modal.style.display = 'flex';
    if (input) { input.value = ''; input.focus(); }
    if (errorEl) errorEl.style.display = 'none';
  }
};

window.closeAiNotesModal = function () {
  var modal = document.getElementById('ai-notes-modal');
  if (modal) modal.style.display = 'none';
};

window.executeAiDraftFromNotes = function () {
  var input = document.getElementById('ai-notes-input');
  var errorEl = document.getElementById('ai-notes-error');
  var text = (input && input.value.trim()) || '';
  if (!text) {
    if (errorEl) { errorEl.style.display = 'block'; errorEl.textContent = 'Please paste some notes or text first.'; }
    return;
  }
  var p = allProjects[activeEditIdx];
  var gid = String((p && (p.id || p.grant_id)) || '').trim();
  closeAiNotesModal();
  synthesizeFromAi(gid, 'notes', text);
};

window.setCoverPhoto = async function (projectId, filename) {
  if (getDataSourceMode() !== 'csv' && supabaseClient) {
    try {
      await supabaseClient.from('project_assets').update({ display_order: 1 }).eq('project_id', projectId);
      await supabaseClient.from('project_assets').update({ display_order: 0 }).match({ project_id: projectId, filename: filename });
      var p = allProjects.find(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
      });
      if (p && p.project_assets) {
        p.project_assets.forEach(function (a) {
          a.display_order = (a.filename === filename ? 0 : 1);
        });
      }
      loadEditFiles(projectId);
      loadProjectFiles(projectId, 'edit-photo-area', null);
    } catch (e) {
      console.warn('Error setting cover photo:', e);
    }
  }
};

window.saveAssetCaption = async function (projectId, filename, caption) {
  if (getDataSourceMode() !== 'csv' && supabaseClient) {
    try {
      var cap = (caption || '').trim();
      await supabaseClient
        .from('project_assets')
        .update({ caption: cap })
        .match({ project_id: projectId, filename: filename });
      var p = allProjects.find(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === projectId.toLowerCase();
      });
      if (p && p.project_assets) {
        var asset = p.project_assets.find(function (a) { return a.filename === filename; });
        if (asset) asset.caption = cap;
      }
    } catch (e) {
      console.warn('Error saving asset caption:', e);
    }
  }
};

window.openEditForm = function (idx) {
  if (!isMaintenanceMode) {
    window.toggleMaintenanceMode(true);
  }
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

  var briefVal = (p.brief_overview || p.description || '').trim();
  var completeVal = (p.complete_overview || p.narrative || '').trim();
  var startDateVal = p.start_date || (p.start_year ? p.start_year + '-01-01' : '');
  var endDateVal = p.end_date || '';
  var dObj = p.details || {};

  rp.innerHTML = ''
    + '<div class="panel" id="edit-panel">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:2px solid #d97706;padding-bottom:6px;">'
    + '    <h2 style="border:none;padding:0;margin:0;color:#d97706;">✏️ Edit Project & Media</h2>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" onclick="showDetail(' + activeEditIdx + ')" style="padding:5px 12px;border:none;background:#94a3b8;color:white;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>'
    + '      <button type="button" id="btn-save-project" onclick="saveProjectEdits()" style="padding:5px 14px;border:none;background:#059669;color:white;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">Save Changes</button>'
    + '    </div>'
    + '  </div>'
    + '  <div id="edit-sync-bar" style="display:flex;justify-content:space-between;align-items:center;background:#f8fafc;border:1px solid #e2e8f0;padding:8px 12px;border-radius:6px;margin-bottom:12px;font-size:12px;">'
    + '    <div id="edit-sync-badges" style="display:flex;gap:8px;align-items:center;">'
    + '      <span class="sync-chip chip-gray">Checking sync status…</span>'
    + '    </div>'
    + '    <div id="edit-sync-actions" style="display:flex;gap:6px;"></div>'
    + '  </div>'
    + '  <div style="display:flex;justify-content:space-between;align-items:center;background:#f5f3ff;border:1px solid #ddd6fe;padding:8px 12px;border-radius:6px;margin-bottom:12px;">'
    + '    <div style="font-size:12px;color:#5b21b6;font-weight:600;">'
    + '      ✨ <strong>Gemini AI Assistant:</strong> Auto-draft overviews, timeline & details'
    + '    </div>'
    + '    <div style="display:flex;gap:6px;">'
    + '      <button type="button" class="btn-ai" onclick="synthesizeFromAi(\'' + gid + '\', \'pdf\')">📄 Auto-fill from App PDF</button>'
    + '      <button type="button" class="btn-ai" onclick="openAiNotesModal(\'' + gid + '\')">📝 Auto-fill from Notes / Paste</button>'
    + '    </div>'
    + '  </div>'
    + '  <div id="ai-status-banner" style="display:none;padding:8px 12px;border-radius:6px;font-size:12px;margin-bottom:12px;"></div>'
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
    + '      <select id="edit-type" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;background:white;" onchange="renderMilestonesBuilder(null, this.value === \'Global Grant\')">'
    + '        <option value="Club Direct / Donation" ' + optDirect + '>Club Direct / Donation</option>'
    + '        <option value="District Grant" ' + optDG + '>District Grant</option>'
    + '        <option value="Club-to-Club Grant" ' + optC2C + '>Club-to-Club Grant</option>'
    + '        <option value="Global Grant" ' + optGG + '>Global Grant</option>'
    + '      </select>'
    + '    </div>'
    + '  </div>'
    + '  <div style="margin-bottom:12px;">'
    + '    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
    + '      <label style="font-size:11px;font-weight:bold;">Project Title * <span style="font-weight:normal;color:#64748b;">(SPC prjTitle max 50 chars)</span></label>'
    + '      <span id="counter-title" class="char-counter counter-normal">0 / 50</span>'
    + '    </div>'
    + '    <input type="text" id="edit-title" maxlength="60" oninput="updateTitleCharCounter()" value="' + escapeHtml(p.title || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project Start Date <span style="font-weight:normal;color:#64748b;">(YYYY-MM-DD or YYYY-MM)</span></label>'
    + '      <input type="text" id="edit-start-date" placeholder="YYYY-MM-DD" value="' + escapeHtml(startDateVal) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project End Date <span style="font-weight:normal;color:#64748b;">(YYYY-MM-DD or YYYY-MM)</span></label>'
    + '      <input type="text" id="edit-end-date" placeholder="YYYY-MM-DD" value="' + escapeHtml(endDateVal) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <div style="margin-bottom:12px;">'
    + '    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
    + '      <label style="font-size:11px;font-weight:bold;">Brief Overview <span style="font-weight:normal;color:#64748b;">(Exported to SPC prjOverview — max 100 chars)</span></label>'
    + '      <span id="counter-brief" class="char-counter counter-normal">0 / 100 characters</span>'
    + '    </div>'
    + '    <textarea id="edit-brief-overview" rows="2" maxlength="150" oninput="updateBriefCharCounter()" placeholder="Punchy 100-character overview for Service Project Center..." style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;line-height:1.4;box-sizing:border-box;">' + escapeHtml(briefVal) + '</textarea>'
    + '  </div>'
    + '  <div style="margin-bottom:12px;">'
    + '    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
    + '      <label style="font-size:11px;font-weight:bold;">Complete Overview <span style="font-weight:normal;color:#64748b;">(Exported to SPC prjDetailedDescription — max 1,000 chars)</span></label>'
    + '      <span id="counter-complete" class="char-counter counter-normal">0 / 1,000 characters</span>'
    + '    </div>'
    + '    <textarea id="edit-complete-overview" rows="4" maxlength="1200" oninput="updateCompleteCharCounter()" placeholder="Comprehensive 1,000-character overview of the project, community served, and impact..." style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;line-height:1.4;box-sizing:border-box;">' + escapeHtml(completeVal) + '</textarea>'
    + '  </div>'
    + '  <div style="background:#f8fafc;border:1px solid #e2e8f0;padding:12px;border-radius:6px;margin-bottom:14px;">'
    + '    <label style="font-size:12px;font-weight:bold;color:#1e293b;display:block;margin-bottom:4px;">⏱️ Project Timeline & Milestones</label>'
    + '    <div style="font-size:11px;color:#64748b;margin-bottom:8px;">'
    + '      Record the backstory of how the club started thinking about the project, plus chronological milestones.'
    + '    </div>'
    + '    <div style="margin-bottom:8px;">'
    + '      <label style="font-size:11px;font-weight:bold;color:#475569;display:block;margin-bottom:2px;">Backstory Narrative</label>'
    + '      <textarea id="edit-timeline-backstory" rows="2" placeholder="Describe the origin, relationship, and early discussions..." style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;box-sizing:border-box;">' + escapeHtml((p.timeline && p.timeline.backstory) || '') + '</textarea>'
    + '    </div>'
    + '    <label style="font-size:11px;font-weight:bold;color:#475569;display:block;margin-bottom:4px;">Milestones (e.g. Submitted, Approved, Implementation, Handover)</label>'
    + '    <div id="milestones-builder-container"></div>'
    + '    <button type="button" onclick="addMilestoneRow()" style="margin-top:6px;padding:4px 10px;font-size:11px;background:#e2e8f0;border:none;border-radius:4px;cursor:pointer;font-weight:600;">+ Add Milestone</button>'
    + '  </div>'
    + '  <div style="background:#f8fafc;border:1px solid #e2e8f0;padding:12px;border-radius:6px;margin-bottom:14px;">'
    + '    <label style="font-size:12px;font-weight:bold;color:#1e293b;display:block;margin-bottom:6px;">💰 Financial Breakdown & Partner Organizations</label>'
    + '    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '      <div>'
    + '        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">TRF World Fund ($)</label>'
    + '        <input type="number" id="edit-detail-world-fund" value="' + escapeHtml(dObj.world_fund || 0) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '      </div>'
    + '      <div>'
    + '        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">District DDF ($)</label>'
    + '        <input type="number" id="edit-detail-ddf" value="' + escapeHtml(dObj.district_ddf || 0) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '      </div>'
    + '      <div>'
    + '        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Club Contributions ($)</label>'
    + '        <input type="number" id="edit-detail-club-cash" value="' + escapeHtml(dObj.club_contributions || 0) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '      </div>'
    + '    </div>'
    + '    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '      <div>'
    + '        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Host Club & District</label>'
    + '        <input type="text" id="edit-detail-host" placeholder="e.g. Club Rotario de Lake Atitlán (D4250)" value="' + escapeHtml(dObj.host_club || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '      </div>'
    + '      <div>'
    + '        <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">International Sponsor Club & District</label>'
    + '        <input type="text" id="edit-detail-intl" placeholder="e.g. Upper Arlington Rotary (D6690)" value="' + escapeHtml(dObj.international_club || p.international_club_name || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '      </div>'
    + '    </div>'
    + '    <div style="margin-bottom:10px;">'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Contributing / Partner Rotary Clubs (comma-separated)</label>'
    + '      <input type="text" id="edit-detail-partner-clubs" placeholder="e.g. Baltimore, Carroll Creek, Petaluma Valley, Rockville, Lake Shore-Severna Park" value="' + escapeHtml(Array.isArray(dObj.partner_clubs) ? dObj.partner_clubs.join(', ') : (dObj.partner_clubs || '')) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;">'
    + '      <span style="font-size:10px;color:#64748b;">List all participating/contributing Rotary clubs. No need to break out individual amounts.</span>'
    + '    </div>'
    + '    <div style="margin-bottom:10px;">'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Contributing / Partner Districts (comma-separated)</label>'
    + '      <input type="text" id="edit-detail-partner-districts" placeholder="e.g. 7620, 6690, 5360" value="' + escapeHtml(Array.isArray(dObj.partner_districts) ? dObj.partner_districts.join(', ') : (dObj.partner_districts || '')) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;">'
    + '      <span style="font-size:10px;color:#64748b;">List all contributing DDF / partner districts.</span>'
    + '    </div>'
    + '    <div style="margin-bottom:4px;">'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Cooperating Partner Organizations / NGOs (comma-separated)</label>'
    + '      <input type="text" id="edit-detail-coop-orgs" placeholder="e.g. Mayan Families, Hospitalito Atitlán, Municipality of Santa Lucía Utatlán" value="' + escapeHtml(Array.isArray(dObj.cooperating_organizations) ? dObj.cooperating_organizations.join(', ') : (dObj.cooperating_organizations || (p.partner || ''))) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;">'
    + '      <span style="font-size:10px;color:#64748b;">Implementing partners, local NGOs, government entities, and community associations.</span>'
    + '    </div>'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Budget / Amount ($)</label>'
    + '      <input type="number" id="edit-amount" value="' + escapeHtml(p.amount || p.budget || 0) + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
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
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Shepherd / Lead Rotarian</label>'
    + '      <input type="text" id="edit-shepard" value="' + escapeHtml(p.shepard || p.shepherd || dObj.shepherd || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Key Partner / NGO</label>'
    + '      <input type="text" id="edit-partner" value="' + escapeHtml(p.partner || (dObj.cooperating_organizations && dObj.cooperating_organizations.join(', ')) || '') + '" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:4px;">Full Narrative & Historical Notes</label>'
    + '  <textarea id="edit-narrative" style="width:100%;height:180px;font-family:monospace;padding:8px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;line-height:1.5;">' + escapeHtml(initialText) + '</textarea>'
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
  loadProjectSyncStatus(gid);
  renderMilestonesBuilder(p.timeline && p.timeline.milestones, pType === 'Global Grant');
  updateTitleCharCounter();
  updateBriefCharCounter();
  updateCompleteCharCounter();

  var linksLoaded = false;
  if (getDataSourceMode() !== 'csv') {
    if (p.project_links && p.project_links.length > 0) {
      p.project_links.forEach(function (l) {
        var u = (l.url && l.url.indexOf('spc.rotary.org') !== -1) ? normalizeSpcUrl(l.url) : (l.url || '');
        addLinkInput(l.label, u);
      });
      linksLoaded = true;
    } else if (supabaseClient) {
      supabaseClient
        .from('project_links')
        .select('*')
        .eq('project_id', gid)
        .order('display_order', { ascending: true })
        .then(function (res) {
          if (!res.error && res.data && res.data.length > 0) {
            res.data.forEach(function (l) {
              var u = (l.url && l.url.indexOf('spc.rotary.org') !== -1) ? normalizeSpcUrl(l.url) : (l.url || '');
              addLinkInput(l.label, u);
            });
          } else {
            addLinkInput();
          }
        })
        .catch(function () { addLinkInput(); });
      linksLoaded = true;
    }
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

  if (getDataSourceMode() !== 'csv' && supabaseClient) {
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
          .delete()
          .match({ project_id: projectId, filename: filename })
          .then(function () {
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
                p.project_assets.push({ filename: filename, public_url: publicUrl, file_type: 'image' });
              }
            }
            handleSuccess(publicUrl);
          });
      })
      .catch(function (err) {
        console.error('Supabase image upload failed:', err);
        if (banner) banner.textContent = '❌ Upload failed: ' + (err.message || err);
        isUploadingImage = false;
      });
  } else {
    if (banner) banner.textContent = '❌ Supabase client not initialized.';
    isUploadingImage = false;
  }
}

async function loadEditFiles(projectId) {
  var container = document.getElementById('modal-existing-files');
  if (!container) return;

  var assets = [];

  if (getDataSourceMode() !== 'csv') {
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

  // Deduplicate assets by filename
  var seenEditAssets = new Set();
  assets = assets.filter(function (a) {
    var fn = (a.filename || '').trim();
    if (!fn || seenEditAssets.has(fn.toLowerCase())) return false;
    seenEditAssets.add(fn.toLowerCase());
    return true;
  });

  if (assets.length === 0) {
    container.innerHTML = '<div style="color:#888;font-size:12px;font-style:italic;">No files or photos uploaded yet.</div>';
    return;
  }

  var html = '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:6px;">';
  assets.forEach(function (a, i) {
    var fn = a.filename || '';
    var isImg = a.file_type === 'image' || /\.(jpg|jpeg|png|gif|webp)$/i.test(fn);
    var isVid = a.file_type === 'video' || /\.(mp4|mov|webm)$/i.test(fn);
    var isAppPdf = /application.*\.pdf$/i.test(fn);
    var isReportPdf = /report.*\.pdf$/i.test(fn);
    var isCover = isImg && a.display_order === 0;
    var elemId = 'file-thumb-' + i;
    var src = a.public_url || ('projects/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(fn));
    var caption = a.caption || '';

    var mediaTag = isImg
      ? '<img src="' + src + '" onerror="this.src=\'' + BACKEND_URL + '/' + src + '\'; this.onerror=null;" style="width:100%;height:80px;object-fit:cover;border-radius:4px;cursor:pointer;" onclick="window.open(\'' + src + '\', \'_blank\')">'
      : isVid
        ? '<div style="font-size:32px;line-height:80px;text-align:center;background:#f1f5f9;border-radius:4px;">🎬</div>'
        : '<div style="font-size:32px;line-height:80px;text-align:center;background:#f1f5f9;border-radius:4px;cursor:pointer;" onclick="window.open(\'' + src + '\', \'_blank\')">' + (isAppPdf ? '📋' : (isReportPdf ? '📊' : '📄')) + '</div>';

    var coverTag = '';
    if (isCover) {
      coverTag = '<div style="font-size:10px;color:#059669;font-weight:bold;margin-top:3px;text-align:center;">★ Cover Photo</div>';
    } else if (isImg) {
      coverTag = '<button type="button" onclick="setCoverPhoto(\'' + projectId + '\', \'' + escapeHtml(fn) + '\')" style="font-size:10px;padding:2px 6px;margin-top:3px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:3px;cursor:pointer;color:#475569;width:100%;">☆ Set Cover</button>';
    }

    var docBadge = '';
    if (isAppPdf) {
      var isGG = projectId.toUpperCase().startsWith('GG');
      var isDG = projectId.toUpperCase().startsWith('DG');
      var appLabel = isGG ? 'GG Application' : (isDG ? 'DG Application' : 'Grant Application');
      docBadge = '<div style="margin-top:4px;display:flex;flex-direction:column;gap:3px;align-items:stretch;">'
               + '  <span style="font-size:9px;background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;border-radius:3px;padding:2px 4px;font-weight:bold;text-align:center;">📋 ' + appLabel + '</span>'
               + '  <button type="button" onclick="synthesizeFromAi(\'' + projectId + '\', \'pdf\')" style="font-size:9px;background:#8b5cf6;color:white;border:none;border-radius:3px;padding:3px 6px;cursor:pointer;font-weight:600;display:flex;align-items:center;justify-content:center;gap:3px;" title="Use Gemini AI to extract project details and auto-fill form fields from this PDF">✨ AI Auto-fill</button>'
               + '</div>';
    } else if (isReportPdf) {
      var repNumMatch = fn.match(/report_?(\d+)/i);
      var repLabel = repNumMatch ? ('Status Report #' + parseInt(repNumMatch[1], 10)) : 'Status Report';
      docBadge = '<div style="margin-top:4px;display:flex;flex-direction:column;gap:3px;align-items:stretch;">'
               + '  <span style="font-size:9px;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;border-radius:3px;padding:2px 4px;font-weight:bold;text-align:center;">📊 ' + repLabel + '</span>'
               + '</div>';
    } else if (!isImg && !isVid) {
      docBadge = '<div style="margin-top:4px;display:flex;flex-direction:column;gap:3px;align-items:stretch;">'
               + '  <span style="font-size:9px;background:#f8fafc;color:#64748b;border:1px solid #e2e8f0;border-radius:3px;padding:2px 4px;font-weight:bold;text-align:center;">📄 Attachment</span>'
               + '</div>';
    }

    html += '<div id="' + elemId + '" style="position:relative;border:1px solid ' + (isCover ? '#10b981' : '#cbd5e1') + ';border-radius:6px;padding:6px;background:#fff;width:140px;box-sizing:border-box;display:flex;flex-direction:column;box-shadow:0 1px 2px rgba(0,0,0,0.05);">'
          + mediaTag
          + '<div style="font-size:11px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:4px;" title="' + escapeHtml(fn) + '">' + escapeHtml(fn) + '</div>'
          + coverTag
          + docBadge
          + '<input type="text" class="asset-caption-input" data-filename="' + escapeHtml(fn) + '" value="' + escapeHtml(caption) + '" onchange="saveAssetCaption(\'' + projectId + '\', \'' + escapeHtml(fn) + '\', this.value)" placeholder="Caption / description" style="width:100%;font-size:10px;padding:3px 4px;margin-top:4px;border:1px solid #e2e8f0;border-radius:3px;box-sizing:border-box;" title="File caption (auto-saved or saved with project)">'
          + '<button type="button" onclick="deleteProjectAsset(\'' + projectId + '\', \'' + escapeHtml(fn) + '\', \'' + elemId + '\')" style="position:absolute;top:-6px;right:-6px;background:#ef4444;color:white;border:none;border-radius:50%;width:18px;height:18px;font-size:10px;cursor:pointer;line-height:18px;text-align:center;padding:0;z-index:2;" title="Delete file">✕</button>'
          + '</div>';
  });
  html += '</div>';

  container.innerHTML = html;
}

window.deleteProjectAsset = async function (projectId, filename, elementId) {
  if (!confirm('Are you sure you want to delete "' + filename + '"?')) return;

  var success = false;
  if (getDataSourceMode() !== 'csv' && supabaseClient) {
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
      console.error('Supabase asset delete error:', err);
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

  var fileList = [];
  var seenUploadNames = new Set();
  Array.from(files).forEach(function (f) {
    var fn = (f.name || '').trim();
    if (fn && !seenUploadNames.has(fn.toLowerCase())) {
      seenUploadNames.add(fn.toLowerCase());
      fileList.push(f);
    }
  });

  if (getDataSourceMode() !== 'csv' && supabaseClient) {
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

async function saveProjectEdits() {
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

  var briefVal = (document.getElementById('edit-brief-overview') && document.getElementById('edit-brief-overview').value.trim()) || '';
  var completeVal = (document.getElementById('edit-complete-overview') && document.getElementById('edit-complete-overview').value.trim()) || '';
  var startDateVal = (document.getElementById('edit-start-date') && document.getElementById('edit-start-date').value.trim()) || '';
  var endDateVal = (document.getElementById('edit-end-date') && document.getElementById('edit-end-date').value.trim()) || '';
  var timelineVal = typeof window.getTimelinePayload === 'function' ? window.getTimelinePayload() : (p.timeline || { backstory: '', milestones: [] });
  var detailsVal = typeof window.getDetailsPayload === 'function' ? window.getDetailsPayload() : (p.details || {});

  var links = [];
  document.querySelectorAll('#modal-links-list .link-row').forEach(function (r) {
    var inputs = r.querySelectorAll('input');
    if (inputs[0].value.trim() && inputs[1].value.trim()) {
      links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
    }
  });

  // Collect asset captions
  var captionUpdates = [];
  document.querySelectorAll('#modal-existing-files .asset-caption-input').forEach(function (inp) {
    var fn = inp.getAttribute('data-filename');
    var cap = inp.value.trim();
    if (fn) {
      captionUpdates.push({ filename: fn, caption: cap });
    }
  });

  if (getDataSourceMode() !== 'csv' && supabaseClient) {
    var fullPayload = {
      id: newGid,
      title: (document.getElementById('edit-title') && document.getElementById('edit-title').value) || '',
      project_type: (document.getElementById('edit-type') && document.getElementById('edit-type').value) || '',
      status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || '',
      category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || '',
      budget: numAmt,
      start_year: intYear || (startDateVal ? (parseInt(startDateVal.slice(0, 4), 10) || p.start_year) : p.start_year),
      shepherd: shepherdVal,
      partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
      narrative: (document.getElementById('edit-narrative') && document.getElementById('edit-narrative').value) || '',
      position_lat: !isNaN(parsedLat) ? parsedLat : null,
      position_lng: !isNaN(parsedLng) ? parsedLng : null,
      brief_overview: briefVal,
      complete_overview: completeVal,
      start_date: startDateVal || null,
      end_date: endDateVal || null,
      timeline: timelineVal,
      details: detailsVal
    };

    var saveWarning = null;

    try {
      if (newGid !== oldGid) {
        var insRes = await supabaseClient.from('projects').insert(fullPayload);
        if (insRes.error) throw insRes.error;
        await supabaseClient.from('projects').delete().eq('id', oldGid);
      } else {
        var upRes = await supabaseClient.from('projects').upsert(fullPayload);
        if (upRes.error) throw upRes.error;
      }
    } catch (err) {
      var errMsg = String((err && (err.message || err.details || err.hint)) || '').toLowerCase();
      if (errMsg.includes('column') || errMsg.includes('schema cache') || errMsg.includes('does not exist')) {
        console.warn('Supabase projects table missing extended columns; retrying with core fields:', errMsg);
        saveWarning = 'Core project fields saved successfully.\n\nNote: Extended columns (brief_overview, complete_overview, timeline, details) could not be saved to Supabase because schema_migration.sql has not been run yet in the Supabase Cloud SQL Editor.';
        var corePayload = {
          id: fullPayload.id,
          title: fullPayload.title,
          project_type: fullPayload.project_type,
          status: fullPayload.status,
          category: fullPayload.category,
          budget: fullPayload.budget,
          start_year: fullPayload.start_year,
          shepherd: fullPayload.shepherd,
          partner: fullPayload.partner,
          narrative: fullPayload.narrative,
          position_lat: fullPayload.position_lat,
          position_lng: fullPayload.position_lng
        };
        try {
          if (newGid !== oldGid) {
            var retryIns = await supabaseClient.from('projects').insert(corePayload);
            if (retryIns.error) throw retryIns.error;
            await supabaseClient.from('projects').delete().eq('id', oldGid);
          } else {
            var retryUp = await supabaseClient.from('projects').upsert(corePayload);
            if (retryUp.error) throw retryUp.error;
          }
        } catch (retryErr) {
          console.error('Supabase retry save error:', retryErr);
          alert('Error saving project to Supabase: ' + (retryErr.message || JSON.stringify(retryErr)));
          if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
          return;
        }
      } else {
        console.error('Supabase save error:', err);
        alert('Error saving project to Supabase: ' + (err.message || JSON.stringify(err)));
        if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
        return;
      }
    }

    try {
      // Sync links
      await supabaseClient.from('project_links').delete().eq('project_id', newGid);
      if (links.length > 0) {
        var linksPayload = links.map(function (l, idx) {
          return {
            project_id: newGid,
            label: l.label,
            url: l.url,
            display_order: idx
          };
        });
        await supabaseClient.from('project_links').insert(linksPayload);
      }

      // Sync captions
      if (captionUpdates.length > 0) {
        await Promise.all(captionUpdates.map(function (cu) {
          return supabaseClient
            .from('project_assets')
            .update({ caption: cu.caption })
            .match({ project_id: newGid, filename: cu.filename });
        }));
      }

      cancelEditCleanup();
      var projects = await loadData();
      allProjects = projects;
      rebuildMarkers();
      var targetIdx = allProjects.findIndex(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === newGid.toLowerCase();
      });
      showDetail(targetIdx !== -1 ? targetIdx : (activeEditIdx >= 0 ? activeEditIdx : 0));

      if (saveWarning) {
        alert(saveWarning);
      }
    } catch (err) {
      console.error('Post-save sync error:', err);
    } finally {
      if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
    }
  } else {
    alert('Supabase client is not connected. Cannot save changes.');
    if (btn) { btn.textContent = 'Save Changes'; btn.disabled = false; }
  }
}

window.openCreateForm = function () {
  if (!isMaintenanceMode) {
    window.toggleMaintenanceMode(true);
  }
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
    + '    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
    + '      <label style="font-size:11px;font-weight:bold;">Project Title * <span style="font-weight:normal;color:#64748b;">(SPC prjTitle max 50 chars)</span></label>'
    + '      <span id="counter-title" class="char-counter counter-normal">0 / 50</span>'
    + '    </div>'
    + '    <input type="text" id="edit-title" maxlength="60" oninput="updateTitleCharCounter()" placeholder="Project Title" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '  </div>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project Start Date (YYYY-MM-DD or YYYY-MM)</label>'
    + '      <input type="text" id="edit-start-date" placeholder="YYYY-MM-DD" value="' + currentYear + '-01-01" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '    <div>'
    + '      <label style="font-size:11px;font-weight:bold;display:block;margin-bottom:2px;">Project End Date (YYYY-MM-DD or YYYY-MM)</label>'
    + '      <input type="text" id="edit-end-date" placeholder="YYYY-MM-DD" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;">'
    + '    </div>'
    + '  </div>'
    + '  <div style="margin-bottom:12px;">'
    + '    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
    + '      <label style="font-size:11px;font-weight:bold;">Brief Overview <span style="font-weight:normal;color:#64748b;">(Exported to SPC prjOverview — max 100 chars)</span></label>'
    + '      <span id="counter-brief" class="char-counter counter-normal">0 / 100</span>'
    + '    </div>'
    + '    <textarea id="edit-brief-overview" rows="2" maxlength="150" oninput="updateBriefCharCounter()" placeholder="Punchy 100-character overview for Service Project Center..." style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;box-sizing:border-box;"></textarea>'
    + '  </div>'
    + '  <div style="margin-bottom:12px;">'
    + '    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
    + '      <label style="font-size:11px;font-weight:bold;">Complete Overview <span style="font-weight:normal;color:#64748b;">(Exported to SPC prjDetailedDescription — max 1,000 chars)</span></label>'
    + '      <span id="counter-complete" class="char-counter counter-normal">0 / 1,000</span>'
    + '    </div>'
    + '    <textarea id="edit-complete-overview" rows="4" maxlength="1200" oninput="updateCompleteCharCounter()" placeholder="Comprehensive 1,000-character overview of the project, community served, and impact..." style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;box-sizing:border-box;"></textarea>'
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

window.saveNewProject = async function () {
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
  var pType = (document.getElementById('edit-type') && document.getElementById('edit-type').value) || 'Club Direct / Donation';

  var briefVal = (document.getElementById('edit-brief-overview') && document.getElementById('edit-brief-overview').value.trim()) || '';
  var completeVal = (document.getElementById('edit-complete-overview') && document.getElementById('edit-complete-overview').value.trim()) || '';
  var startDateVal = (document.getElementById('edit-start-date') && document.getElementById('edit-start-date').value.trim()) || (intYear ? intYear + '-01-01' : '');
  var endDateVal = (document.getElementById('edit-end-date') && document.getElementById('edit-end-date').value.trim()) || '';

  var initialMilestones = [];
  if (pType === 'Global Grant') {
    initialMilestones.push({ id: 'm_1', name: 'Submitted', date: startDateVal || '', notes: 'Submitted to Rotary International' });
    initialMilestones.push({ id: 'm_2', name: 'Approved', date: '', notes: 'Approved by The Rotary Foundation' });
  } else {
    initialMilestones.push({ id: 'm_1', name: 'Project Initiated', date: startDateVal || '', notes: '' });
  }

  var links = [];
  document.querySelectorAll('#modal-links-list .link-row').forEach(function (r) {
    var inputs = r.querySelectorAll('input');
    if (inputs[0].value.trim() && inputs[1].value.trim()) {
      links.push({ label: inputs[0].value.trim(), url: inputs[1].value.trim() });
    }
  });

  if (getDataSourceMode() !== 'csv' && supabaseClient) {
    var fullPayload = {
      id: gid,
      title: title,
      project_type: pType,
      status: (document.getElementById('edit-status') && document.getElementById('edit-status').value) || 'proposed',
      category: (document.getElementById('edit-category') && document.getElementById('edit-category').value) || 'Community Service',
      budget: numAmt,
      start_year: intYear || (startDateVal ? (parseInt(startDateVal.slice(0, 4), 10) || null) : null),
      shepherd: shepherdVal,
      partner: (document.getElementById('edit-partner') && document.getElementById('edit-partner').value) || '',
      narrative: (document.getElementById('edit-narrative') && document.getElementById('edit-narrative').value) || '',
      position_lat: !isNaN(parsedLat) ? parsedLat : null,
      position_lng: !isNaN(parsedLng) ? parsedLng : null,
      brief_overview: briefVal,
      complete_overview: completeVal,
      start_date: startDateVal || null,
      end_date: endDateVal || null,
      timeline: { backstory: '', milestones: initialMilestones },
      details: {}
    };

    var saveWarning = null;

    try {
      var insRes = await supabaseClient.from('projects').insert(fullPayload);
      if (insRes.error) throw insRes.error;
    } catch (err) {
      var errMsg = String((err && (err.message || err.details || err.hint)) || '').toLowerCase();
      if (errMsg.includes('column') || errMsg.includes('schema cache') || errMsg.includes('does not exist')) {
        console.warn('Supabase projects table missing extended columns; retrying with core fields:', errMsg);
        saveWarning = 'Project created successfully with core fields.\n\nNote: Extended columns (brief_overview, complete_overview, timeline, details) could not be saved to Supabase because schema_migration.sql has not been run yet in the Supabase Cloud SQL Editor.';
        var corePayload = {
          id: fullPayload.id,
          title: fullPayload.title,
          project_type: fullPayload.project_type,
          status: fullPayload.status,
          category: fullPayload.category,
          budget: fullPayload.budget,
          start_year: fullPayload.start_year,
          shepherd: fullPayload.shepherd,
          partner: fullPayload.partner,
          narrative: fullPayload.narrative,
          position_lat: fullPayload.position_lat,
          position_lng: fullPayload.position_lng
        };
        try {
          var retryIns = await supabaseClient.from('projects').insert(corePayload);
          if (retryIns.error) throw retryIns.error;
        } catch (retryErr) {
          console.error('Supabase retry create error:', retryErr);
          alert('Error creating project: ' + (retryErr.message || JSON.stringify(retryErr)));
          if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
          return;
        }
      } else {
        console.error('Supabase create error:', err);
        alert('Error creating project: ' + (err.message || JSON.stringify(err)));
        if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
        return;
      }
    }

    try {
      if (links.length > 0) {
        var linksPayload = links.map(function (l, idx) {
          return { project_id: gid, label: l.label, url: l.url, display_order: idx };
        });
        await supabaseClient.from('project_links').insert(linksPayload);
      }

      cancelEditCleanup();
      var projects = await loadData();
      allProjects = projects;
      rebuildMarkers();
      var targetIdx = allProjects.findIndex(function (item) {
        return String(item.id || item.grant_id || '').trim().toLowerCase() === gid.toLowerCase();
      });
      showDetail(targetIdx !== -1 ? targetIdx : 0);

      if (saveWarning) {
        alert(saveWarning);
      }
    } catch (err) {
      console.error('Post-create sync error:', err);
    } finally {
      if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
    }
  } else {
    alert('Supabase client is not connected. Cannot create project.');
    if (btn) { btn.textContent = 'Create Project'; btn.disabled = false; }
  }
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

function checkMaintenanceMode() {
  var urlParams = new URLSearchParams(window.location.search);
  var maintParam = urlParams.get('maint') || urlParams.get('admin');
  var editParam = urlParams.get('edit') || urlParams.get('mode');

  if (maintParam !== null) {
    var val = maintParam.toLowerCase();
    if (val === 'true' || val === '1' || val === 'yes' || val === 'on') {
      sessionStorage.setItem('rcla_maint_mode', 'true');
      return true;
    } else if (val === 'false' || val === '0' || val === 'no' || val === 'off') {
      sessionStorage.setItem('rcla_maint_mode', 'false');
      return false;
    }
  }

  if (editParam !== null) {
    var eVal = editParam.toLowerCase();
    if (eVal === 'true' || eVal === '1' || eVal === 'edit') {
      sessionStorage.setItem('rcla_maint_mode', 'true');
      return true;
    }
  }

  var stored = sessionStorage.getItem('rcla_maint_mode');
  if (stored === 'true') return true;
  if (stored === 'false') return false;

  // Local development defaults to true, production (github.io) defaults to false
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

function applyMaintenanceModeUI() {
  var panel = document.getElementById('maintainer-panel');
  var isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  if (panel) {
    panel.style.display = isMaintenanceMode ? 'flex' : 'none';
  }

  var localBtns = document.querySelectorAll('.local-only-btn');
  localBtns.forEach(function (el) {
    el.style.display = isLocal ? '' : 'none';
  });
}

window.toggleMaintenanceMode = function (forceState) {
  if (forceState !== undefined) {
    isMaintenanceMode = Boolean(forceState);
  } else {
    isMaintenanceMode = !isMaintenanceMode;
  }
  sessionStorage.setItem('rcla_maint_mode', isMaintenanceMode ? 'true' : 'false');
  applyMaintenanceModeUI();

  if (currentView === 'detail' && allProjects[currentIndex]) {
    showDetail(currentIndex);
  }
};

window.handleBackendIndicatorClick = function (event) {
  window.toggleMaintenanceMode();
};

// Keyboard shortcut: Ctrl+Shift+M or Cmd+Shift+M to toggle maintainer mode
window.addEventListener('keydown', function (e) {
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'M' || e.key === 'm')) {
    e.preventDefault();
    window.toggleMaintenanceMode();
  }
});

function initMaintainerClient() {
  isMaintenanceMode = checkMaintenanceMode();
  applyMaintenanceModeUI();

  var isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (!isLocal) {
    // On production/GitHub Pages, don't poll local backend URL
    return;
  }

  // Load existing log history immediately on load
  window.fetchLogHistory();

  try {
    var evtSource = new EventSource(BACKEND_URL + '/api/logs');
    evtSource.onmessage = function (event) {
      var logDiv = document.getElementById('log-output');
      var drawer = document.getElementById('log-drawer');
      if (logDiv) {
        var newLine = document.createElement('div');
        newLine.className = 'log-line';
        newLine.textContent = event.data;
        logDiv.appendChild(newLine);
        if (drawer) drawer.scrollTop = drawer.scrollHeight;
      }
      pollMaintStatus();
    };

    evtSource.onerror = function () {
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

window.fetchLogHistory = async function () {
  try {
    var res = await fetch(BACKEND_URL + '/api/logs/history');
    if (res.ok) {
      var data = await res.json();
      var logDiv = document.getElementById('log-output');
      var drawer = document.getElementById('log-drawer');
      if (logDiv && data.logs && data.logs.length > 0) {
        logDiv.innerHTML = '';
        var hasFinished = false;
        data.logs.forEach(function (line) {
          var div = document.createElement('div');
          div.className = 'log-line';
          div.textContent = line;
          logDiv.appendChild(div);
          if (line.indexOf('finished successfully') !== -1 || line.indexOf('Synced SPC export state') !== -1 || line.indexOf('Synced to Supabase') !== -1) {
            hasFinished = true;
          }
        });
        if (drawer) drawer.scrollTop = drawer.scrollHeight;
        if (hasFinished && window.currentActiveProjectId) {
          window.loadProjectSyncStatus(window.currentActiveProjectId);
        }
      }
    }
  } catch (e) {}
};

var logPollInterval = null;
window.startLogPolling = function (durationMs) {
  if (logPollInterval) clearInterval(logPollInterval);
  window.fetchLogHistory();
  var endTime = Date.now() + (durationMs || 15000);
  logPollInterval = setInterval(function () {
    window.fetchLogHistory();
    if (Date.now() > endTime) {
      clearInterval(logPollInterval);
      logPollInterval = null;
    }
  }, 1000);
};

function pollMaintStatus() {
  var isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (!isLocal) return;

  fetch(BACKEND_URL + '/api/status')
    .then(function (res) {
      if (!res.ok) throw new Error();
      return res.json();
    })
    .then(function (data) {
      var badge = document.getElementById('sync-status-badge');
      if (badge) {
        var label = data.status.toUpperCase();
        if (data.task) label += ' (' + (data.task === 'spc_export' ? 'SPC' : 'GrantCenter') + ')';
        badge.textContent = 'Status: ' + label;
        badge.style.background = data.status === 'running' ? '#d97706' : data.status === 'error' ? '#dc2626' : '#059669';
      }
    })
    .catch(function () {
      var badge = document.getElementById('sync-status-badge');
      if (badge) {
        badge.textContent = 'Orchestrator: Offline';
        badge.style.background = '#64748b';
      }
    });
}

window.triggerSync = function (dryRun) {
  if (dryRun === undefined) dryRun = true;
  window.toggleLogConsole(true);
  window.startLogPolling(20000);
  fetch(BACKEND_URL + '/api/grantcenter/sync?dry_run=' + dryRun, { method: 'POST' });
};

window.triggerSpcExport = function (dryRun) {
  if (dryRun === undefined) dryRun = true;
  window.toggleLogConsole(true);
  window.startLogPolling(20000);
  fetch(BACKEND_URL + '/api/spc/export?dry_run=' + dryRun, { method: 'POST' });
};

window.toggleLogConsole = function (forceOpen) {
  var drawer = document.getElementById('log-drawer');
  if (drawer) {
    var willOpen = forceOpen || drawer.style.display === 'none';
    drawer.style.display = willOpen ? 'block' : 'none';
    if (willOpen) {
      window.fetchLogHistory();
      drawer.scrollTop = drawer.scrollHeight;
    }
  }
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
