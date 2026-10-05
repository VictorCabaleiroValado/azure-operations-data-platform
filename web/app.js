/* The browser displays API results; processing and SQL run on the server. */
'use strict';
const $ = (selector) => document.querySelector(selector);
const money = (cents) => new Intl.NumberFormat('en-GB', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0}).format(cents / 100);
const number = (value) => new Intl.NumberFormat('en-GB').format(value);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const labels = {queued: 'Queued', processing: 'Processing', completed: 'Completed', rejected: 'Rejected', failed: 'Technical failure'};
const titles = {overview: 'Warehouse operations', inventory: 'Inventory', upload: 'File intake', runs: 'Processing runs', cloud: 'The system in Azure'};
let observation, observationBusy = false;
let catalog, data, runtime, map, markers = [], selection = '', activeTab = 'overview', refreshBusy = false, map3D = false, mapVectorReady = false;

async function json(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Error ${response.status}. The operation could not be completed.`);
  }
  return response.json();
}

function filteredState(source, warehouse) {
  const inventory = source.inventory.filter((row) => !warehouse || row.warehouse === warehouse);
  const runs = source.runs.filter((row) => !warehouse || row.warehouse === warehouse);
  return {inventory, runs, units: inventory.reduce((sum, row) => sum + row.quantity, 0), value: inventory.reduce((sum, row) => sum + row.value_cents, 0), references: new Set(inventory.map((row) => row.sku)).size, low: inventory.filter((row) => row.quantity < 10).length};
}

function warehouseName(id) { return catalog.warehouses.find((w) => w.id === id)?.name || id; }
function supplierName(id) { return catalog.suppliers.find((s) => s.id === id)?.name || id; }
function badge(status) { return `<span class="status ${escapeHtml(status)}">${escapeHtml(labels[status] || status)}</span>`; }
function dateTime(value) { return value ? new Date(value).toLocaleString('en-GB', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'}) : '—'; }
function empty(message) { return `<div class="empty">${escapeHtml(message)}</div>`; }

function runTable(records) {
  if (!records.length) return empty('No files in this selection.');
  return `<table><thead><tr><th>File / supplier</th><th>Warehouse</th><th>Status</th><th>Rows</th><th>Received</th></tr></thead><tbody>${records.map((r) => `<tr><td><button class="row-button" data-run="${r.id}">${escapeHtml(r.filename)}</button><small>${escapeHtml(supplierName(r.supplier))}</small></td><td>${escapeHtml(warehouseName(r.warehouse))}</td><td>${badge(r.status)}</td><td>${r.row_count || '—'}</td><td>${dateTime(r.received_at)}</td></tr>`).join('')}</tbody></table>`;
}

function visibleInventory() {
  const query = $('#search').value.trim().toLowerCase();
  return filteredState(data, selection).inventory.filter((r) => (!query || `${r.sku} ${r.product}`.toLowerCase().includes(query)) && (!$('#only-low').checked || r.quantity < 10));
}

function renderInventory() {
  const rows = visibleInventory();
  $('#inventory-count').textContent = `${rows.length} products / warehouse`;
  $('#inventory-table').innerHTML = rows.length ? `<table><thead><tr><th>Product</th><th>Warehouse</th><th>Category</th><th>Units</th><th>Value at cost</th><th>Stock date</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${escapeHtml(r.product)}<small>${escapeHtml(r.sku)}</small></td><td>${escapeHtml(warehouseName(r.warehouse))}</td><td>${escapeHtml(r.category)}</td><td class="${r.quantity < 10 ? 'low' : ''}">${number(r.quantity)}${r.quantity < 10 ? ' · review' : ''}</td><td>${money(r.value_cents)}</td><td>${escapeHtml(r.oldest_snapshot)}${r.oldest_snapshot !== r.newest_snapshot ? ' – ' + escapeHtml(r.newest_snapshot) : ''}</td></tr>`).join('')}</tbody></table>` : empty('No products match these filters.');
}

function chartGroups(rows, field, metric) {
  const groups = new Map();
  rows.forEach((row) => groups.set(row[field], (groups.get(row[field]) || 0) + row[metric]));
  return [...groups].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
function bars(groups, format, name = (value) => value) {
  if (!groups.length) return empty('No inventory in this selection.');
  const max = Math.max(1, ...groups.map(([, value]) => value));
  return `<ul class="bar-chart">${groups.map(([key, value]) => `<li><div><span>${escapeHtml(name(key))}</span><strong>${escapeHtml(format(value))}</strong></div><div class="bar-track" aria-hidden="true"><span style="width:${value / max * 100}%"></span></div></li>`).join('')}</ul>`;
}
function repairTip(message) {
  if (/quantity|units/i.test(message)) return 'Use a whole number from 0 to 100,000.';
  if (/reference|sku/i.test(message)) return 'Use a product reference from the sample catalog; remove duplicate references.';
  if (/cost|price/i.test(message)) return 'Use a positive cost with at most two decimal places.';
  if (/date|day|month/i.test(message)) return 'Use one valid YYYY-MM-DD stock date for all rows, between 2020 and today.';
  if (/technical|attempt|storage/i.test(message)) return 'Ask the operator to inspect the worker logs before retrying.';
  return 'Check the supplier sample format, encoding, headers and delimiters; correct and upload the file again.';
}
function renderIncidents(records) {
  const issues = records.filter((r) => ['rejected', 'failed'].includes(r.status));
  const errors = issues.reduce((n, r) => n + r.errors.length, 0);
  $('#incident-summary').textContent = `${issues.length} affected files · ${errors} reported errors`;
  $('#incidents').innerHTML = issues.length ? issues.map((r) => `<details class="incident"><summary>${escapeHtml(r.filename)} · ${escapeHtml(warehouseName(r.warehouse))} · ${escapeHtml(labels[r.status])} · ${r.errors.length} errors</summary><p>${escapeHtml(supplierName(r.supplier))} · ${dateTime(r.received_at)}</p><ul>${[...new Set(r.errors.map((e) => e.message))].map((message) => `<li><strong>${escapeHtml(message)}</strong><p>${escapeHtml(repairTip(message))}</p></li>`).join('')}</ul><button class="row-button" data-run="${r.id}">View affected rows →</button></details>`).join('') : empty('No rejected files or technical failures in this selection.');
}
function comparisonHtml(id, comparison = data.comparisons?.[id]) {
  if (!comparison) return '';
  const explanation = `<h3>Snapshot comparison</h3><p>${comparison.active ? 'Current valid snapshot' : 'Superseded snapshot'} for this supplier and warehouse.</p>`;
  if (!comparison.baseline_id) return explanation + '<p>First valid business version: no earlier snapshot to compare.</p>';
  const exactMoney = (value) => new Intl.NumberFormat('en-GB', {style:'currency', currency:'EUR'}).format(value / 100);
  const signed = (value, format) => (value > 0 ? '+' : '') + format(value);
  return explanation + `<p>Compared with <button class="row-button" data-run="${comparison.baseline_id}">previous valid snapshot (${escapeHtml(comparison.baseline_date)})</button>, ordered by stock date, then receipt time. This is a stock difference, not a shipment or sale.</p><p><strong>${signed(comparison.units_delta, number)} units · ${signed(comparison.value_delta_cents, exactMoney)} at cost</strong></p>` + (comparison.changes.length ? `<div class="table-wrap"><table><thead><tr><th>Product</th><th>Change</th><th>Units before → after</th><th>Unit cost before → after</th></tr></thead><tbody>${comparison.changes.map((c) => `<tr><td>${escapeHtml(c.product)}<small>${escapeHtml(c.sku)}</small></td><td>${escapeHtml(c.change)}</td><td>${number(c.before_quantity)} → ${number(c.after_quantity)}</td><td>${c.before_cost_cents === null ? '—' : exactMoney(c.before_cost_cents)} → ${c.after_cost_cents === null ? '—' : exactMoney(c.after_cost_cents)}</td></tr>`).join('')}</tbody></table></div>` : '<p>No quantity or unit-cost changes.</p>');
}
function renderObservability() {
  const target = $('#observability');
  if (!observation || observation.status !== 'ok') {
    target.textContent = observation?.message || 'Azure Monitor is not connected in this runtime. Monitoring values are unavailable.';
    return;
  }
  const m = observation.metrics;
  target.innerHTML = `<p>${runtime === 'snapshot' ? 'Saved observation' : 'Last successful query'}: ${dateTime(observation.checked_at)} · refreshed at most every 5 minutes in Azure. Logs may arrive with a delay.</p><div class="monitor-grid">${[['Completed files', m.completed], ['Rejected files', m.rejected], ['Technical failure attempts', m.technical_failure_attempts], ['Mean processing duration', m.average_duration_ms === null ? '—' : number(Math.round(m.average_duration_ms * 100) / 100) + ' ms']].map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div><p class="muted">${m.last_event_at ? 'Last matching log: ' + dateTime(m.last_event_at) : 'No matching processor events in this 7-day window.'} · Counts come from Azure Monitor logs; retries and retention can differ from processing history. Duration measures worker processing, not queue wait.</p>`;
}
async function refreshObservability() {
  if (runtime === 'snapshot' || observationBusy) return;
  observationBusy = true;
  try { observation = await json('./api/observability'); }
  catch (_) { observation = {status:'unavailable', message:'Azure Monitor could not be reached. Monitoring values are unavailable.'}; }
  finally { observationBusy = false; renderObservability(); }
}

function render() {
  const view = filteredState(data, selection);
  $('#units').textContent = number(view.units);
  $('#value').textContent = money(view.value);
  $('#references').textContent = view.references;
  $('#low-stock').textContent = view.low;
  $('#run-scope').textContent = selection ? warehouseName(selection) : 'All warehouses';
  $('#run-summary').innerHTML = ['completed', 'rejected', 'queued', 'processing', 'failed'].map((status) => `<div class="status-line"><span><i class="status-dot ${status}"></i>${labels[status]}</span><strong>${view.runs.filter((r) => r.status === status).length}</strong></div>`).join('');
  $('#recent-runs').innerHTML = runTable(view.runs.slice(0, 5));
  $('#runs-table').innerHTML = runTable(view.runs.filter((r) => !$('#status-filter').value || r.status === $('#status-filter').value));
  const newest = view.runs.find((r) => r.status === 'completed');
  $('#freshness').textContent = newest ? `Latest valid upload: ${dateTime(newest.finished_at)}` : 'No valid uploads';
  document.querySelectorAll('[data-warehouse]').forEach((b) => {
    const selected = b.dataset.warehouse === selection;
    b.classList.toggle('selected', selected);
    b.setAttribute('aria-pressed', String(selected));
    const stock = filteredState(data, b.dataset.warehouse);
    b.querySelector('.warehouse-stock').textContent = `${number(stock.units)} units · ${stock.references} references`;
  });
  markers.forEach(({element, warehouse}) => {
    element.classList.toggle('selected', selection === warehouse.id);
    element.setAttribute('aria-pressed', String(selection === warehouse.id));
  });
  renderInventory();
  $('#units-chart').innerHTML = bars(chartGroups(view.inventory, 'warehouse', 'quantity'), number, warehouseName);
  $('#value-chart').innerHTML = bars(chartGroups(view.inventory, 'category', 'value_cents'), money);
  renderIncidents(view.runs);
}

function chooseWarehouse(id) {
  selection = id;
  $('#warehouse').value = id;
  if (id) { $('#upload-warehouse').value = id; updateSamples(); }
  render();
  if (map3D && id) focusWarehouse(id);
}

function focusWarehouse(id) {
  const warehouse = catalog.warehouses.find((w) => w.id === id) || catalog.warehouses[0];
  map.easeTo({center: [warehouse.lon, warehouse.lat], zoom: 16, pitch: 55, bearing: -20, duration: 650});
}

function fitWarehouseMap() {
  if (!map) return;
  const locations = catalog.warehouses;
  map.fitBounds([[Math.min(...locations.map(w => w.lon)), Math.min(...locations.map(w => w.lat))], [Math.max(...locations.map(w => w.lon)), Math.max(...locations.map(w => w.lat))]], {padding: {top: 55, bottom: 50, left: 70, right: 70}, maxZoom: 10, pitch: 0, bearing: 0, duration: 0});
}

function setMap3D(enabled) {
  map3D = enabled && mapVectorReady;
  $('#map-3d').setAttribute('aria-pressed', String(map3D));
  $('#map-3d').textContent = map3D ? 'Back to 2D' : '3D view';
  $('#basemap-status').textContent = mapVectorReady ? `Bright / OpenFreeMap · ${map3D ? '3D: drag to explore' : '2D overview'}` : 'Fallback basemap · OpenStreetMap';
  if (map3D) {
    if (!selection) chooseWarehouse(catalog.warehouses[0].id);
    else focusWarehouse(selection);
  } else fitWarehouseMap();
}

function initializeMap() {
  if (!window.maplibregl) { $('#map-fallback').hidden = false; $('#map-3d').disabled = true; return; }
  maplibregl.setWorkerUrl(new URL('assets/vendor/maplibre-gl-csp-worker.js', window.location.href).href);
  map = new maplibregl.Map({container: 'map', style: 'https://tiles.openfreemap.org/styles/bright', center: [-3.68, 40.423], zoom: 10, attributionControl: false});
  map.scrollZoom.disable();
  map.addControl(new maplibregl.NavigationControl({visualizePitch: true}), 'bottom-right');
  map.addControl(new maplibregl.AttributionControl({compact: true}), 'bottom-right');
  let fallbackUsed = false;
  const fallback = () => {
    if (mapVectorReady || fallbackUsed) return;
    fallbackUsed = true;
    map.setStyle({version: 8, sources: {osm: {type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 17, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}}, layers: [{id: 'osm', type: 'raster', source: 'osm'}]});
    $('#map-3d').disabled = true;
    $('#basemap-status').textContent = 'Fallback basemap · OpenStreetMap';
  };
  map.once('style.load', () => {
    if (fallbackUsed) return;
    const label = map.getStyle().layers.find(layer => layer.type === 'symbol' && layer.layout?.['text-field']);
    map.addLayer({id: 'warehouse-buildings-3d', source: 'openmaptiles', 'source-layer': 'building', type: 'fill-extrusion', minzoom: 14, filter: ['!=', ['get', 'hide_3d'], true], paint: {'fill-extrusion-color': '#d3c6b4', 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 5], 'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0], 'fill-extrusion-opacity': 0.88}}, label?.id);
  });
  map.once('idle', () => {
    if (fallbackUsed) return;
    mapVectorReady = true;
    $('#map-3d').disabled = false;
    setMap3D(false);
  });
  setTimeout(fallback, 20000);
  catalog.warehouses.forEach((warehouse, index) => {
    const element = document.createElement('button');
    element.type = 'button'; element.className = 'warehouse-map-marker';
    element.setAttribute('aria-label', `Select ${warehouse.name}`);
    element.setAttribute('aria-pressed', 'false');
    element.innerHTML = `<span class="warehouse-marker"><svg viewBox="0 0 24 24" width="21" height="21" aria-hidden="true"><path d="M3 10 12 4l9 6v10H3Z M8 20v-7h8v7 M8 16h8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg><i>${index + 1}</i></span><span class="warehouse-map-label"><strong>${escapeHtml(warehouse.name.replace('Madrid ', ''))}</strong><small>${escapeHtml(warehouse.code)}</small></span>`;
    element.addEventListener('click', () => chooseWarehouse(selection === warehouse.id ? '' : warehouse.id));
    new maplibregl.Marker({element, anchor: 'center'}).setLngLat([warehouse.lon, warehouse.lat]).addTo(map);
    markers.push({element, warehouse});
  });
  fitWarehouseMap();
}

function showTab(id) {
  activeTab = id;
  document.querySelectorAll('.view').forEach((section) => { section.hidden = section.id !== id; });
  document.querySelectorAll('[data-tab]').forEach((button) => { button.classList.toggle('active', button.dataset.tab === id); button.setAttribute('aria-current', button.dataset.tab === id ? 'page' : 'false'); });
  $('#page-title').textContent = titles[id];
  if (id === 'cloud') refreshObservability();
  if (id === 'overview' && map) requestAnimationFrame(() => map.resize());
}

function updateSamples() {
  const matches = catalog.samples.filter((s) => s.supplier === $('#supplier').value && s.warehouse === $('#upload-warehouse').value);
  $('#sample').innerHTML = matches.map((s) => `<option value="${escapeHtml(s.file)}">${escapeHtml(s.label)}</option>`).join('');
  updateDownload();
}
function updateDownload() {
  const file = $('#sample').value;
  $('#download-sample').href = runtime === 'snapshot' ? `./samples/${encodeURIComponent(file)}` : `./api/samples/${encodeURIComponent(file)}`;
  $('#download-sample').download = file;
}

async function refresh(silent = false) {
  if (refreshBusy) return;
  refreshBusy = true;
  try {
    if (runtime !== 'snapshot') data = await json('./api/state');
    render();
    if (activeTab === 'cloud') refreshObservability();
    $('#error').hidden = true;
  } catch (error) {
    if (!silent) { $('#error').textContent = error.message; $('#error').hidden = false; }
  } finally { refreshBusy = false; }
}

async function upload(event) {
  event.preventDefault();
  if (runtime === 'snapshot') return;
  const file = $('#file').files[0];
  if (!file) return;
  $('#submit').disabled = true;
  $('#upload-result').textContent = 'Uploading file…';
  try {
    if (file.size > 512 * 1024) throw new Error('The file exceeds 512 KiB.');
    const params = new URLSearchParams({supplier: $('#supplier').value, warehouse: $('#upload-warehouse').value, filename: file.name});
    const result = await json(`./api/uploads?${params}`, {method: 'POST', headers: {'Content-Type': 'text/csv'}, body: file});
    $('#upload-result').innerHTML = `<div class="success-message">${result.duplicate ? 'File already recorded: the original processing run is preserved.' : 'File received. The processor will update its status.'}<br><button class="row-button" data-run="${result.id}">View processing run →</button></div>`;
    await refresh();
  } catch (error) { $('#upload-result').textContent = error.message; }
  finally { $('#submit').disabled = false; }
}

async function detail(id) {
  try {
    const run = runtime === 'snapshot' ? data.runs.find((r) => r.id === id) : await json(`./api/runs/${id}`);
    if (!run) return;
    $('#detail-content').innerHTML = `<p class="eyebrow">PROCESSING DETAILS</p><h2>${escapeHtml(run.filename)}</h2>${badge(run.status)}<div class="detail-facts"><div><span>Warehouse</span><strong>${escapeHtml(warehouseName(run.warehouse))}</strong></div><div><span>Supplier</span><strong>${escapeHtml(supplierName(run.supplier))}</strong></div><div><span>Rows read</span><strong>${run.row_count}</strong></div><div><span>Processing attempts</span><strong>${run.attempts}</strong></div><div><span>Processing duration</span><strong>${run.duration_ms === null ? '—' : number(run.duration_ms) + ' ms'}</strong></div><div><span>Inventory date</span><strong>${escapeHtml(run.snapshot_date || '—')}</strong></div><div><span>Recorded runtime</span><strong>${escapeHtml(run.runtime)}</strong></div><div><span>Finished</span><strong>${dateTime(run.finished_at)}</strong></div></div><p class="muted">ID: ${escapeHtml(run.id)}</p>${run.errors.length ? `<ul class="error-list">${run.errors.slice(0, 100).map((e) => `<li><b>${e.line ? 'Line ' + e.line : 'File'}:</b> ${escapeHtml(e.message)}</li>`).join('')}</ul><p class="muted">${run.errors.length} errors. Correct the file and submit it again.</p>` : `<p>${run.status === 'completed' ? 'All rows are valid. This snapshot contributes to inventory if it is the latest version for the supplier and warehouse.' : 'The file has not yet published a valid result.'}</p>`}`;
    $('#detail-content').insertAdjacentHTML('beforeend', comparisonHtml(id, run.comparison));
    if (!$('#detail').open) $('#detail').showModal();
  } catch (error) { $('#error').textContent = error.message; $('#error').hidden = false; }
}

function csvText(rows) {
  const fields = ['warehouse','sku','product','category','quantity','value_cents','suppliers','oldest_snapshot','newest_snapshot'];
  const quote = (v) => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  return '\uFEFF' + [fields, ...rows.map((r) => fields.map((f) => r[f]))].map((row) => row.map(quote).join(',')).join('\r\n') + '\r\n';
}
function downloadInventory() {
  const url = URL.createObjectURL(new Blob([csvText(visibleInventory())], {type: 'text/csv;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url; link.download = `inventory-${selection || 'madrid'}.csv`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function init() {
  try {
    const mode = await json('./assets/mode.json');
    if (mode.mode === 'snapshot') {
      const snapshot = await json('./assets/demo.json');
      catalog = snapshot.catalog; data = snapshot.state; observation = snapshot.observability; runtime = 'snapshot';
    } else {
      [catalog, data] = await Promise.all([json('./api/catalog'), json('./api/state')]);
      runtime = catalog.runtime;
    }
    $('#runtime').textContent = {snapshot: 'Static demo', local: 'Local runtime', azure: 'Connected to Azure'}[runtime];
    const note = {snapshot: 'Read-only copy: filters and the map work; file uploads require the Azure-connected application or local mode.', local: 'Actual processing on this computer. Business data is synthetic.', azure: 'Storage and processing in Azure. The public demo accepts the downloadable samples; executions may take a minute to start.'}[runtime];
    $('#runtime-note').textContent = note;
    if (mode.cloud_url) {
      const url = new URL(mode.cloud_url);
      if (url.protocol === 'https:' && url.hostname.endsWith('.azurecontainerapps.io')) {
        const link = document.createElement('a'); link.href = url.href; link.textContent = ' Open Azure application ↗'; $('#runtime-note').append(link);
      }
    }
    $('#cloud-proof').textContent = runtime === 'azure' ? 'This application is connected to Azure storage. Each processing run shows the runtime and duration recorded by the worker.' : 'This view explains the architecture. The current runtime is ' + (runtime === 'local' ? 'local' : 'a static copy') + '; it does not represent a new Azure execution.';
    const options = catalog.warehouses.map((w) => `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join('');
    $('#warehouse').insertAdjacentHTML('beforeend', options);
    $('#upload-warehouse').innerHTML = options;
    $('#supplier').innerHTML = catalog.suppliers.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
    $('#supplier-formats').innerHTML = catalog.suppliers.map((s) => `<div class="format"><h3>${escapeHtml(s.name)}</h3><code>${escapeHtml(s.fields.join(s.delimiter + ' '))}</code></div>`).join('');
    $('#warehouse-buttons').innerHTML = catalog.warehouses.map((w, i) => `<button data-warehouse="${w.id}" aria-pressed="false"><span class="warehouse-number">0${i + 1}</span><span><strong>${escapeHtml(w.name.replace('Madrid ', ''))}</strong><small class="warehouse-stock"></small></span><span class="warehouse-arrow" aria-hidden="true">↗</span></button>`).join('');
    $('#upload-policy').textContent = runtime === 'snapshot' ? 'Uploads are disabled in this static copy. Use the Azure application or run the project locally.' : runtime === 'azure' ? 'Public demo: only downloadable samples for the selected supplier and warehouse. Use local mode for custom files.' : 'Local mode: edit the samples and upload your own CSV files using the specified format.';
    $('#submit').disabled = runtime === 'snapshot';
    $('#file').disabled = runtime === 'snapshot';
    updateSamples();
    try { initializeMap(); } catch (error) { $('#map-fallback').hidden = false; $('#map-3d').disabled = true; $('#basemap-status').textContent = 'Basemap unavailable'; }
    render();
    renderObservability();
    document.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
    document.querySelectorAll('[data-warehouse]').forEach((b) => b.addEventListener('click', () => chooseWarehouse(selection === b.dataset.warehouse ? '' : b.dataset.warehouse)));
    $('#warehouse').addEventListener('change', (e) => chooseWarehouse(e.target.value));
    $('#map-3d').addEventListener('click', () => setMap3D(!map3D));
    $('#map-reset').addEventListener('click', () => { chooseWarehouse(''); setMap3D(false); });
    $('#go-upload').addEventListener('click', () => showTab('upload'));
    $('#all-runs').addEventListener('click', () => showTab('runs'));
    $('#refresh').addEventListener('click', () => refresh());
    $('#search').addEventListener('input', renderInventory);
    $('#only-low').addEventListener('change', renderInventory);
    $('#status-filter').addEventListener('change', render);
    $('#supplier').addEventListener('change', updateSamples);
    $('#upload-warehouse').addEventListener('change', updateSamples);
    $('#sample').addEventListener('change', updateDownload);
    $('#upload-form').addEventListener('submit', upload);
    $('#export').addEventListener('click', downloadInventory);
    document.addEventListener('click', (event) => { const button = event.target.closest('[data-run]'); if (button) detail(button.dataset.run); });
    $('.dialog-close').addEventListener('click', () => $('#detail').close());
    if (runtime !== 'snapshot') setInterval(() => { if (!document.hidden) refresh(true); }, 12000);
  } catch (error) { $('#error').textContent = 'Could not load data: ' + error.message; $('#error').hidden = false; $('#runtime').textContent = 'Disconnected'; }
}
init();
