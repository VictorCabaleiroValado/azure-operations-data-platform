"""Receive, validate and publish supplier inventory snapshots. No fabricated cloud status."""

import csv
import hashlib
import io
import json
import logging
import re
from datetime import datetime, timezone
from time import perf_counter

import duckdb

from .catalog import PRODUCT_BY_SKU, SUPPLIER_BY_ID, WAREHOUSE_IDS
from .presentation import present_run
from .store import read_json, write_json
from .validation import MAX_BYTES, validate

log = logging.getLogger("operations")
TERMINAL = {"completed", "rejected", "failed"}


def now():
    return datetime.now(timezone.utc).isoformat()


def get_run(store, run_id):
    if not re.fullmatch(r"[a-f0-9]{64}", run_id):
        raise FileNotFoundError(run_id)
    return present_run(read_json(store, f"runs/{run_id}.json"))


def runs(store):
    return sorted(
        [present_run(read_json(store, p)) for p in store.names("runs")],
        key=lambda r: (r["received_at"], r["id"]),
        reverse=True,
    )


def submit(store, content, supplier, warehouse, filename="inventory.csv"):
    if supplier not in SUPPLIER_BY_ID or warehouse not in WAREHOUSE_IDS:
        raise ValueError("Unknown supplier or warehouse.")
    if not content or len(content) > MAX_BYTES:
        raise ValueError("The file must contain between 1 byte and 512 KiB.")
    identity = b"v1\0" + supplier.encode() + b"\0" + warehouse.encode() + b"\0" + content
    run_id = hashlib.sha256(identity).hexdigest()
    record = {
        "id": run_id,
        "supplier": supplier,
        "warehouse": warehouse,
        "filename": filename[:100],
        "received_at": now(),
        "finished_at": None,
        "status": "queued",
        "row_count": 0,
        "errors": [],
        "duration_ms": None,
        "attempts": 0,
        "snapshot_date": None,
        "runtime": store.mode,
    }
    store.put(f"raw/{run_id}.csv", content, create=True)
    created = write_json(store, f"runs/{run_id}.json", record, create=True)
    record = get_run(store, run_id)
    if record["status"] not in TERMINAL:
        # Duplicate delivery is safe; this also repairs an upload/enqueue interruption.
        store.enqueue(run_id)
    return {**record, "duplicate": not created}


def process(store, run_id):
    start = perf_counter()
    with store.lock(run_id) as check_lease:
        record = get_run(store, run_id)
        if record["status"] in TERMINAL:
            return record
        record.update(status="processing", attempts=record["attempts"] + 1)
        write_json(store, f"runs/{run_id}.json", record)
        try:
            result = validate(store.get(f"raw/{run_id}.csv"), record["supplier"])
            write_json(store, f"results/{run_id}.json", result)
            if check_lease:
                check_lease()
            record.update(
                status="rejected" if result["errors"] else "completed",
                errors=result["errors"],
                row_count=result["row_count"],
                snapshot_date=result["rows"][0]["snapshot_date"] if result["rows"] else None,
                finished_at=now(),
                duration_ms=round((perf_counter() - start) * 1000, 2),
            )
            write_json(store, f"runs/{run_id}.json", record)
            log.info(
                json.dumps(
                    {
                        "event": "file_processed",
                        "run_id": run_id,
                        "status": record["status"],
                        "rows": record["row_count"],
                        "duration_ms": record["duration_ms"],
                    }
                )
            )
            return record
        except Exception:
            log.exception("Processing failed for run %s; message remains retryable", run_id)
            raise


def retry(store, run_id):
    with store.lock(run_id):
        record = get_run(store, run_id)
        if record["status"] == "rejected":
            raise ValueError("Correct the file and upload it again; the original is preserved.")
        if record["status"] == "completed":
            return record
        record.update(status="queued", errors=[])
        write_json(store, f"runs/{run_id}.json", record)
        store.enqueue(run_id)
        return record


def inventory(store, all_runs=None):
    latest = {}
    for record in all_runs if all_runs is not None else runs(store):
        if record["status"] != "completed":
            continue
        key = record["warehouse"], record["supplier"]
        previous = latest.get(key)
        version = (record["snapshot_date"], record["received_at"], record["id"])
        if previous is None or version > (previous["snapshot_date"], previous["received_at"], previous["id"]):
            latest[key] = record
    data = []
    for record in latest.values():
        for row in read_json(store, f"results/{record['id']}.json")["rows"]:
            data.append(
                {
                    **row,
                    "product": PRODUCT_BY_SKU[row["sku"]]["name"],
                    "category": PRODUCT_BY_SKU[row["sku"]]["category"],
                    "warehouse": record["warehouse"],
                    "supplier": record["supplier"],
                    "run_id": record["id"],
                }
            )
    # SQL aggregates supplier-owned lots into one product per warehouse. Money is integer cents.
    with duckdb.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE stock (warehouse VARCHAR, supplier VARCHAR, sku VARCHAR, product VARCHAR, category VARCHAR, quantity BIGINT, unit_cost_cents BIGINT, snapshot_date VARCHAR, run_id VARCHAR)"
        )
        if data:
            db.executemany(
                "INSERT INTO stock VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        r["warehouse"],
                        r["supplier"],
                        r["sku"],
                        r["product"],
                        r["category"],
                        r["quantity"],
                        r["unit_cost_cents"],
                        r["snapshot_date"],
                        r["run_id"],
                    )
                    for r in data
                ],
            )
        cursor = db.execute("""SELECT warehouse, sku, product, category, SUM(quantity)::BIGINT quantity,
            SUM(quantity * unit_cost_cents)::BIGINT value_cents, COUNT(DISTINCT supplier) suppliers,
            MIN(snapshot_date) oldest_snapshot, MAX(snapshot_date) newest_snapshot
            FROM stock GROUP BY warehouse, sku, product, category ORDER BY warehouse, sku""")
        columns = [c[0] for c in cursor.description]
        aggregated = [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]
    return aggregated


def state(store, warehouse=None):
    records = runs(store)
    stock = inventory(store, records)
    if warehouse:
        stock = [r for r in stock if r["warehouse"] == warehouse]
        records = [r for r in records if r["warehouse"] == warehouse]
    return {
        "runs": records,
        "inventory": stock,
        "totals": {
            "units": sum(r["quantity"] for r in stock),
            "value_cents": sum(r["value_cents"] for r in stock),
            "references": len({r["sku"] for r in stock}),
            "low_stock": sum(r["quantity"] < 10 for r in stock),
        },
    }


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "warehouse",
            "sku",
            "product",
            "category",
            "quantity",
            "value_cents",
            "suppliers",
            "oldest_snapshot",
            "newest_snapshot",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
