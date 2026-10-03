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
  const csv = vm.runInContext('csvText(rows)', context);
  assert.equal(csv.trim().split('\r\n').length, rows.length + 1);
}
assert.equal(vm.runInContext('escapeHtml("<script>")', context), '&lt;script&gt;');
console.log('Verified all five warehouse filters, integer totals, CSV row scope and HTML escaping.');
