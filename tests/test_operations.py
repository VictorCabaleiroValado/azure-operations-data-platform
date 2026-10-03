import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operations_cloud.api import create_app
from operations_cloud.catalog import SUPPLIERS, WAREHOUSES
from operations_cloud.service import get_run, inventory, process, retry, state, submit
from operations_cloud.store import Busy, LocalStore
from operations_cloud.validation import validate

ROOT = Path(__file__).resolve().parents[1]
VALID = (ROOT / "samples/nexo-centro.csv").read_bytes()
BAD = (ROOT / "samples/nexo-centro-errors.csv").read_bytes()
FIXED = (ROOT / "samples/nexo-centro-corrected.csv").read_bytes()


@pytest.fixture
def store(tmp_path):
    return LocalStore(tmp_path)


def load(store, content=VALID, supplier="nexo", warehouse="centro"):
    r = submit(store, content, supplier, warehouse)
    return process(store, r["id"])


def test_three_supplier_formats():
    for supplier in SUPPLIERS:
        payload = (ROOT / "samples" / f"{supplier['id']}-centro.csv").read_bytes()
        result = validate(payload, supplier["id"])
        assert not result["errors"]
        assert len(result["rows"]) == 4
        assert all(type(r["unit_cost_cents"]) is int for r in result["rows"])


def test_rejected_file_preserves_inventory(store):
    load(store)
    before = inventory(store)
    rejected = load(store, BAD)
    assert rejected["status"] == "rejected"
    assert {e["line"] for e in rejected["errors"]} == {2, 3}
    assert inventory(store) == before


def test_duplicate_delivery_is_idempotent(store):
    first = load(store)
    before = inventory(store)
    second = submit(store, VALID, "nexo", "centro", "renamed.csv")
    assert second["duplicate"] and second["id"] == first["id"]
    assert process(store, second["id"])["attempts"] == 1
    assert inventory(store) == before


def test_same_bytes_different_warehouses_are_distinct(store):
    a = load(store)
    b = load(store, warehouse="leganes")
    assert a["id"] != b["id"]
    assert len(inventory(store)) == 8


def test_corrected_snapshot_replaces_not_adds(store):
    load(store)
    load(store, FIXED)
    stock = inventory(store)
    assert len(stock) == 4
    assert next(r for r in stock if r["sku"] == "EL-101")["quantity"] == 18


def test_older_snapshot_cannot_overwrite_newer(store):
    load(store, FIXED)
    load(store, VALID.replace(b"2026-10-03", b"2026-10-02"))
    assert next(r for r in inventory(store) if r["sku"] == "EL-101")["quantity"] == 18


def test_new_snapshot_removes_absent_products(store):
    load(store)
    shorter = b"\r\n".join(FIXED.splitlines()[:2]) + b"\r\n"
    load(store, shorter)
    assert len(inventory(store)) == 1


@pytest.mark.parametrize("replacement", [b"-1", b"NaN", b"1.5", b"100001", b"=cmd()"])
def test_invalid_quantities(replacement):
    assert validate(VALID.replace(b"EL-101,8,", b"EL-101," + replacement + b","), "nexo")["errors"]


def test_money_precision_and_invalid_dates():
    assert validate(VALID.replace(b"649.00", b"649.001"), "nexo")["errors"]
    assert validate(VALID.replace(b"2026-10-03", b"2028-01-01"), "nexo", today=date(2026, 10, 3))["errors"]
    assert validate(VALID.replace(b"2026-10-03", b"2026-02-30"), "nexo")["errors"]


def test_utf8_empty_and_duplicate_sku():
    assert validate(b"\xff", "nexo")["errors"]
    assert validate(b"", "nexo")["errors"]
    assert validate(VALID + VALID.splitlines()[1] + b"\n", "nexo")["errors"]


def test_exclusive_writer_lock(store):
    with store.lock("one"):
        with pytest.raises(Busy):
            with store.lock("one"):
                pass


def test_failure_before_commit_is_retryable(store, monkeypatch):
    load(store)
    baseline = inventory(store)
    queued = submit(store, FIXED, "nexo", "centro")
    original = store.put

    def broken(name, content, create=False):
        if name.startswith("results/"):
            raise RuntimeError("Temporary storage failure")
        return original(name, content, create=create)

    monkeypatch.setattr(store, "put", broken)
    with pytest.raises(RuntimeError):
        process(store, queued["id"])
    assert inventory(store) == baseline
    monkeypatch.setattr(store, "put", original)
    retry(store, queued["id"])
    completed = process(store, queued["id"])
    assert completed["attempts"] == 2 and completed["status"] == "completed"
    assert inventory(store) != baseline


def test_rejected_requires_correction(store):
    run = load(store, BAD)
    with pytest.raises(ValueError):
        retry(store, run["id"])


def test_query_filters_and_units(store):
    for w in WAREHOUSES:
        load(store, warehouse=w["id"])
    assert state(store, "centro")["totals"]["units"] == 199
    assert state(store)["totals"]["units"] == 796
    assert state(store)["totals"]["references"] == 4


def test_api_upload_validation_and_csv(store):
    with TestClient(create_app(store, local_worker=False)) as client:
        response = client.post(
            "/api/uploads?supplier=nexo&warehouse=centro&filename=sample.csv", content=VALID
        )
        assert response.status_code == 202
        process(store, response.json()["id"])
        stock = client.get("/api/state").json()
        assert stock["totals"]["units"] == 199
        assert client.get("/api/inventory.csv?warehouse=centro").text.count("EL-") == 4
        assert client.get("/api/inventory.csv?warehouse=bad").status_code == 422
        assert client.get("/api/runs/bad").status_code == 404
        assert client.post("/api/uploads?supplier=unknown&warehouse=centro", content=VALID).status_code == 422
        assert (
            client.post(
                "/api/uploads?supplier=nexo&warehouse=centro", content=b"x" * (512 * 1024 + 1)
            ).status_code
            == 413
        )
        assert client.get("/api/catalog").json()["runtime"] == "local"
        assert client.get("/assets/mode.json").json()["mode"] == "api"
        assert client.get("/").status_code == 200


def test_public_cloud_rejects_arbitrary_content_and_wrong_destination(store):
    store.mode = "azure"
    with TestClient(create_app(store, local_worker=False)) as client:
        assert client.post("/api/uploads?supplier=nexo&warehouse=centro", content=VALID).status_code == 202
        assert (
            client.post("/api/uploads?supplier=nexo&warehouse=centro", content=b"private data").status_code
            == 403
        )
        assert client.post("/api/uploads?supplier=nexo&warehouse=leganes", content=VALID).status_code == 403


def test_paths_and_integer_money(store):
    with pytest.raises(FileNotFoundError):
        get_run(store, "../../private")
    run = load(store)
    for r in inventory(store):
        assert type(r["value_cents"]) is int
    assert json.loads(store.get(f"results/{run['id']}.json"))["rows"]


def test_queue_batch_acknowledges_only_processed_messages(store, monkeypatch):
    from types import SimpleNamespace

    from operations_cloud.worker import consume

    record = submit(store, VALID, "nexo", "centro")
    acknowledged, dead = [], []
    message = SimpleNamespace(content=record["id"], dequeue_count=1)
    store.queue = SimpleNamespace(
        receive_messages=lambda **kwargs: iter([message]), delete_message=acknowledged.append
    )
    store.dead = SimpleNamespace(send_message=dead.append)
    assert consume(store) == 1
    assert acknowledged == [message] and not dead
    assert get_run(store, record["id"])["status"] == "completed"


def test_queue_transient_failure_is_not_acknowledged(store, monkeypatch):
    from types import SimpleNamespace

    from operations_cloud.worker import consume

    record = submit(store, VALID, "nexo", "centro")
    acknowledged, dead = [], []
    message = SimpleNamespace(content=record["id"], dequeue_count=1)
    store.queue = SimpleNamespace(
        receive_messages=lambda **kwargs: iter([message]), delete_message=acknowledged.append
    )
    store.dead = SimpleNamespace(send_message=dead.append)

    def fail(*args):
        raise RuntimeError("temporary network failure")

    monkeypatch.setattr("operations_cloud.worker.process", fail)
    with pytest.raises(RuntimeError):
        consume(store)
    assert not acknowledged and not dead
    message.dequeue_count = 5
    consume(store)
    assert acknowledged == [message] and len(dead) == 1
    assert get_run(store, record["id"])["status"] == "failed"
