# Data contract and calculations

All business data is synthetic. Four approximate warehouse coordinates are used only for demonstration: Madrid Centro (40.4169,-3.7038), Leganés (40.3270,-3.7653), Sanchinarro (40.4943,-3.6598), Pedrezuela (40.7424,-3.6001). Map tiles are OpenStreetMap cartography, not evidence of actual premises.

## Input grain

A CSV is a complete inventory snapshot for one supplier, one warehouse and one date. One row is one canonical product SKU. Three explicit formats are defined in `catalog.py`; header order and delimiters must match the downloaded example. Encoding: UTF-8, optional BOM. Maximum 512 KiB / 5,000 rows. The demo catalogue contains twelve SKUs.

Checks: known SKU, no duplicate SKU within a file, integer quantity 0–100,000, positive cost with at most two decimals, valid ISO date from 2020 through today, a common date across all rows, non-empty input, exact column count. Any row error rejects the entire snapshot. Empty snapshots are rejected to avoid accidental inventory erasure; supply a zero-quantity row for explicit zero stock.

## Versions and identity

The run ID hashes contract version, supplier, warehouse and original bytes. Identical content for the same context returns the original ID, even if renamed. Formatting changes create another run, but publication replaces the supplier snapshot rather than adding stock. The latest valid snapshot is selected by `(snapshot_date, received_at, run_id)`. This makes out-of-order arrivals safe; later corrected uploads win same-date ties. Re-uploading an already processed file preserves its original receipt time.

A newer complete snapshot removes products absent from the previous snapshot for that supplier/warehouse. Supplier holdings are assumed to be disjoint physical lots. This assumption must be verified before using the model with a real business.

## SQL and metrics

DuckDB SQL groups normalized records by warehouse, SKU, product and category. Quantity is summed over independent suppliers. Value at cost is `SUM(quantity * unit_cost_cents)` in integer cents, not revenue or retail valuation. Distinct references counts distinct SKUs within the selected warehouses. Low stock counts product/warehouse combinations with quantity < 10; it is a fixed demo threshold, not a forecast or purchasing recommendation.

The UI displays source dates and oldest/newest dates when records are combined. It does not invent a common observation time. Process duration excludes time waiting in the queue and container startup. No savings, SLA or production-scale performance claims are made.
