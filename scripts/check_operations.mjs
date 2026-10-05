import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const snapshot = JSON.parse(fs.readFileSync('dist/assets/demo.json', 'utf8'));
const source = fs.readFileSync('web/app.js', 'utf8').replace(/init\(\);\s*$/, '');
const context = vm.createContext({Intl, console, Set, document: {querySelector: () => null}});
vm.runInContext(source, context);
context.state = snapshot.state;
for (const warehouse of ['', ...snapshot.catalog.warehouses.map(w => w.id)]) {
  context.warehouse = warehouse;
  const actual = vm.runInContext('filteredState(state, warehouse)', context);
  const rows = snapshot.state.inventory.filter(r => !warehouse || r.warehouse === warehouse);
  assert.equal(actual.units, rows.reduce((sum, r) => sum + r.quantity, 0));
  assert.equal(actual.value, rows.reduce((sum, r) => sum + r.value_cents, 0));
  assert.equal(actual.inventory.length, rows.length);
  context.rows = rows;
  assert.equal(vm.runInContext("chartGroups(rows, 'warehouse', 'quantity').reduce((sum, r) => sum + r[1], 0)", context), actual.units);
  assert.equal(vm.runInContext("chartGroups(rows, 'category', 'value_cents').reduce((sum, r) => sum + r[1], 0)", context), actual.value);
  const csv = vm.runInContext('csvText(rows)', context);
  assert.equal(csv.trim().split('\r\n').length, rows.length + 1);
}
assert.equal(vm.runInContext('escapeHtml("<script>")', context), '&lt;script&gt;');
console.log('Verified all five warehouse filters, integer totals, CSV row scope and HTML escaping.');

assert.equal(vm.runInContext("bars([], number).includes('No inventory')", context), true);
assert.equal(vm.runInContext("bars([['<script>', 0]], number).includes('&lt;script&gt;')", context), true);
console.log('Verified both chart totals under all warehouse filters, empty states and chart escaping.');
