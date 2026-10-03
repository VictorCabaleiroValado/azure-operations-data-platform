/* The browser displays API results; processing and SQL run on the server. */
'use strict';
const $ = (selector) => document.querySelector(selector);
const money = (cents) => new Intl.NumberFormat('es-ES', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0}).format(cents / 100);
const number = (value) => new Intl.NumberFormat('es-ES').format(value);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const labels = {queued: 'En cola', processing: 'Procesando', completed: 'Completado', rejected: 'Rechazado', failed: 'Fallo técnico'};
const titles = {overview: 'Operaciones de almacén', inventory: 'Inventario', upload: 'Recepción de archivos', runs: 'Procesamientos', cloud: 'El sistema en Azure'};
let catalog, data, runtime, map, markers = [], selection = '', activeTab = 'overview', refreshBusy = false;

async function json(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Error ${response.status}. No se ha completado la operación.`);
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
function dateTime(value) { return value ? new Date(value).toLocaleString('es-ES', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'}) : '—'; }
function empty(message) { return `<div class="empty">${escapeHtml(message)}</div>`; }

function runTable(records) {
  if (!records.length) return empty('No hay archivos en esta selección.');
  return `<table><thead><tr><th>Archivo / proveedor</th><th>Almacén</th><th>Estado</th><th>Filas</th><th>Recibido</th></tr></thead><tbody>${records.map((r) => `<tr><td><button class="row-button" data-run="${r.id}">${escapeHtml(r.filename)}</button><small>${escapeHtml(supplierName(r.supplier))}</small></td><td>${escapeHtml(warehouseName(r.warehouse))}</td><td>${badge(r.status)}</td><td>${r.row_count || '—'}</td><td>${dateTime(r.received_at)}</td></tr>`).join('')}</tbody></table>`;
}

function visibleInventory() {
  const query = $('#search').value.trim().toLowerCase();
  return filteredState(data, selection).inventory.filter((r) => (!query || `${r.sku} ${r.product}`.toLowerCase().includes(query)) && (!$('#only-low').checked || r.quantity < 10));
}

function renderInventory() {
  const rows = visibleInventory();
  $('#inventory-count').textContent = `${rows.length} productos / almacén`;
  $('#inventory-table').innerHTML = rows.length ? `<table><thead><tr><th>Producto</th><th>Almacén</th><th>Categoría</th><th>Unidades</th><th>Valor a coste</th><th>Fecha de stock</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${escapeHtml(r.product)}<small>${escapeHtml(r.sku)}</small></td><td>${escapeHtml(warehouseName(r.warehouse))}</td><td>${escapeHtml(r.category)}</td><td class="${r.quantity < 10 ? 'low' : ''}">${number(r.quantity)}${r.quantity < 10 ? ' · revisar' : ''}</td><td>${money(r.value_cents)}</td><td>${escapeHtml(r.oldest_snapshot)}${r.oldest_snapshot !== r.newest_snapshot ? ' – ' + escapeHtml(r.newest_snapshot) : ''}</td></tr>`).join('')}</tbody></table>` : empty('No hay productos con estos filtros.');
}

function render() {
  const view = filteredState(data, selection);
  $('#units').textContent = number(view.units);
  $('#value').textContent = money(view.value);
  $('#references').textContent = view.references;
  $('#low-stock').textContent = view.low;
  $('#run-scope').textContent = selection ? warehouseName(selection) : 'Todos los almacenes';
  $('#run-summary').innerHTML = ['completed', 'rejected', 'queued', 'processing', 'failed'].map((status) => `<div class="status-line"><span><i class="status-dot ${status}"></i>${labels[status]}</span><strong>${view.runs.filter((r) => r.status === status).length}</strong></div>`).join('');
  $('#recent-runs').innerHTML = runTable(view.runs.slice(0, 5));
  $('#runs-table').innerHTML = runTable(view.runs.filter((r) => !$('#status-filter').value || r.status === $('#status-filter').value));
  const newest = view.runs.find((r) => r.status === 'completed');
  $('#freshness').textContent = newest ? `Última carga válida: ${dateTime(newest.finished_at)}` : 'Sin cargas válidas';
  document.querySelectorAll('[data-warehouse]').forEach((b) => b.classList.toggle('selected', b.dataset.warehouse === selection));
  markers.forEach(({marker, warehouse, index}) => marker.setIcon(markerIcon(warehouse.id, index)));
  renderInventory();
}

function chooseWarehouse(id) {
  selection = id;
  $('#warehouse').value = id;
  if (id) { $('#upload-warehouse').value = id; updateSamples(); }
  render();
}

function markerIcon(id, index) {
  return L.divIcon({className: '', html: `<span class="warehouse-marker ${selection === id ? 'selected' : ''}">${index + 1}</span>`, iconSize: [30, 30], iconAnchor: [15, 15]});
}

function initializeMap() {
  if (!window.L) { $('#map-fallback').hidden = false; return; }
  map = L.map('map', {scrollWheelZoom: false}).setView([40.423, -3.68], 10);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 17, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
  catalog.warehouses.forEach((warehouse, index) => {
    const marker = L.marker([warehouse.lat, warehouse.lon], {icon: markerIcon(warehouse.id, index), title: `Seleccionar ${warehouse.name}`, keyboard: true}).addTo(map);
    marker.getElement()?.setAttribute('aria-label', `Seleccionar ${warehouse.name}`);
    marker.bindTooltip(`${warehouse.code} · ${warehouse.name}`);
    marker.on('click', () => chooseWarehouse(selection === warehouse.id ? '' : warehouse.id));
    markers.push({marker, warehouse, index});
  });
  map.fitBounds(catalog.warehouses.map((w) => [w.lat, w.lon]), {padding: [30, 30], maxZoom: 10});
}

function showTab(id) {
  activeTab = id;
  document.querySelectorAll('.view').forEach((section) => { section.hidden = section.id !== id; });
  document.querySelectorAll('[data-tab]').forEach((button) => { button.classList.toggle('active', button.dataset.tab === id); button.setAttribute('aria-current', button.dataset.tab === id ? 'page' : 'false'); });
  $('#page-title').textContent = titles[id];
  if (id === 'overview' && map) requestAnimationFrame(() => map.invalidateSize());
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
  $('#upload-result').textContent = 'Enviando archivo…';
  try {
    if (file.size > 512 * 1024) throw new Error('El archivo supera 512 KiB.');
    const params = new URLSearchParams({supplier: $('#supplier').value, warehouse: $('#upload-warehouse').value, filename: file.name});
    const result = await json(`./api/uploads?${params}`, {method: 'POST', headers: {'Content-Type': 'text/csv'}, body: file});
    $('#upload-result').innerHTML = `<div class="success-message">${result.duplicate ? 'Archivo ya registrado: se conserva el procesamiento original.' : 'Archivo recibido. El procesador actualizará su estado.'}<br><button class="row-button" data-run="${result.id}">Consultar procesamiento →</button></div>`;
    await refresh();
  } catch (error) { $('#upload-result').textContent = error.message; }
  finally { $('#submit').disabled = false; }
}

async function detail(id) {
  try {
    const run = runtime === 'snapshot' ? data.runs.find((r) => r.id === id) : await json(`./api/runs/${id}`);
    if (!run) return;
    $('#detail-content').innerHTML = `<p class="eyebrow">DETALLE DE PROCESAMIENTO</p><h2>${escapeHtml(run.filename)}</h2>${badge(run.status)}<div class="detail-facts"><div><span>Almacén</span><strong>${escapeHtml(warehouseName(run.warehouse))}</strong></div><div><span>Proveedor</span><strong>${escapeHtml(supplierName(run.supplier))}</strong></div><div><span>Filas leídas</span><strong>${run.row_count}</strong></div><div><span>Intentos de proceso</span><strong>${run.attempts}</strong></div><div><span>Duración de proceso</span><strong>${run.duration_ms === null ? '—' : number(run.duration_ms) + ' ms'}</strong></div><div><span>Fecha del inventario</span><strong>${escapeHtml(run.snapshot_date || '—')}</strong></div><div><span>Entorno de ejecución registrado</span><strong>${escapeHtml(run.runtime)}</strong></div><div><span>Finalizado</span><strong>${dateTime(run.finished_at)}</strong></div></div><p class="muted">ID: ${escapeHtml(run.id)}</p>${run.errors.length ? `<ul class="error-list">${run.errors.slice(0, 100).map((e) => `<li><b>${e.line ? 'Línea ' + e.line : 'Archivo'}:</b> ${escapeHtml(e.message)}</li>`).join('')}</ul><p class="muted">${run.errors.length} errores. Corrige el archivo y vuelve a enviarlo.</p>` : `<p>${run.status === 'completed' ? 'Todas las filas son válidas. Esta fotografía participa en el inventario si es la versión más reciente del proveedor y almacén.' : 'El archivo todavía no ha publicado un resultado válido.'}</p>`}`;
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
  link.href = url; link.download = `inventario-${selection || 'madrid'}.csv`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function init() {
  try {
    const mode = await json('./assets/mode.json');
    if (mode.mode === 'snapshot') {
      const snapshot = await json('./assets/demo.json');
      catalog = snapshot.catalog; data = snapshot.state; runtime = 'snapshot';
    } else {
      [catalog, data] = await Promise.all([json('./api/catalog'), json('./api/state')]);
      runtime = catalog.runtime;
    }
    $('#runtime').textContent = {snapshot: 'Demo estática', local: 'Ejecución local', azure: 'Conectado a Azure'}[runtime];
    const note = {snapshot: 'Copia de consulta: los filtros y el mapa funcionan; la carga de archivos requiere la aplicación conectada a Azure o el modo local.', local: 'Procesamiento real en este equipo. Los datos de negocio son sintéticos.', azure: 'Almacenamiento y procesamiento en Azure. La demo pública acepta los ejemplos descargables; las ejecuciones pueden tardar un minuto en comenzar.'}[runtime];
    $('#runtime-note').textContent = note;
    if (mode.cloud_url) {
      const url = new URL(mode.cloud_url);
      if (url.protocol === 'https:' && url.hostname.endsWith('.azurecontainerapps.io')) {
        const link = document.createElement('a'); link.href = url.href; link.textContent = ' Abrir aplicación Azure ↗'; $('#runtime-note').append(link);
      }
    }
    $('#cloud-proof').textContent = runtime === 'azure' ? 'Esta web está conectada al almacenamiento de Azure. En cada procesamiento puedes comprobar el entorno y la duración registrados por el worker.' : 'Esta vista explica la arquitectura. El entorno actual es ' + (runtime === 'local' ? 'local' : 'una copia estática') + '; no representa una ejecución nueva en Azure.';
    const options = catalog.warehouses.map((w) => `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join('');
    $('#warehouse').insertAdjacentHTML('beforeend', options);
    $('#upload-warehouse').innerHTML = options;
    $('#supplier').innerHTML = catalog.suppliers.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
    $('#supplier-formats').innerHTML = catalog.suppliers.map((s) => `<div class="format"><h3>${escapeHtml(s.name)}</h3><code>${escapeHtml(s.fields.join(s.delimiter + ' '))}</code></div>`).join('');
    $('#warehouse-buttons').innerHTML = catalog.warehouses.map((w, i) => `<button data-warehouse="${w.id}">${i + 1} · ${escapeHtml(w.name.replace('Madrid ', ''))}</button>`).join('');
    $('#upload-policy').textContent = runtime === 'snapshot' ? 'La carga está desactivada en esta copia estática. Usa la aplicación Azure o ejecuta el proyecto localmente.' : runtime === 'azure' ? 'Demo pública: solo los ejemplos descargables del proveedor y almacén seleccionados. Para archivos propios, usa el modo local.' : 'Modo local: puedes editar los ejemplos y cargar tus propios CSV con el formato indicado.';
    $('#submit').disabled = runtime === 'snapshot';
    $('#file').disabled = runtime === 'snapshot';
    updateSamples();
    initializeMap();
    render();
    document.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
    document.querySelectorAll('[data-warehouse]').forEach((b) => b.addEventListener('click', () => chooseWarehouse(selection === b.dataset.warehouse ? '' : b.dataset.warehouse)));
    $('#warehouse').addEventListener('change', (e) => chooseWarehouse(e.target.value));
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
  } catch (error) { $('#error').textContent = 'No se han podido cargar los datos: ' + error.message; $('#error').hidden = false; $('#runtime').textContent = 'Sin conexión'; }
}
init();
