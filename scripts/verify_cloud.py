"""Exercise the public Azure demo using only its bundled synthetic samples."""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

base = sys.argv[1].rstrip("/")
root = Path(__file__).resolve().parents[1]


def get(path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.load(r)


def upload(sample):
    query = urllib.parse.urlencode(
        {"supplier": sample["supplier"], "warehouse": sample["warehouse"], "filename": sample["file"]}
    )
    req = urllib.request.Request(
        base + "/api/uploads?" + query,
        data=(root / "samples" / sample["file"]).read_bytes(),
        headers={"Content-Type": "text/csv"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def wait(ids):
    deadline = time.monotonic() + 720
    while time.monotonic() < deadline:
        rows = [get("/api/runs/" + i) for i in ids]
        counts = {
            s: sum(r["status"] == s for r in rows)
            for s in ("queued", "processing", "completed", "rejected", "failed")
        }
        print(counts, flush=True)
        if all(r["status"] in ("completed", "rejected", "failed") for r in rows):
            return rows
        time.sleep(15)
    raise TimeoutError("Cloud job did not complete within 12 minutes")


assert get("/health/ready") == {"status": "ready", "storage": "azure"}
assert get("/api/catalog")["runtime"] == "azure"
manifest = json.loads((root / "samples/manifest.json").read_text())
valid = [upload(s) for s in manifest if s["kind"] == "valid"]
rows = wait([r["id"] for r in valid])
assert all(r["status"] == "completed" for r in rows)
time.sleep(11)
before = get("/api/state")["inventory"]
assert len(before) == 48
bad = upload(next(s for s in manifest if s["kind"] == "invalid"))
bad = wait([bad["id"]])[0]
assert bad["status"] == "rejected" and len(bad["errors"]) == 2
time.sleep(11)
assert get("/api/state")["inventory"] == before
corrected = upload(next(s for s in manifest if s["kind"] == "correction"))
corrected = wait([corrected["id"]])[0]
assert corrected["status"] == "completed"
duplicate = upload(next(s for s in manifest if s["kind"] == "correction"))
assert duplicate["duplicate"] and duplicate["id"] == corrected["id"]
time.sleep(11)
state = get("/api/state")
assert (
    next(r for r in state["inventory"] if r["warehouse"] == "centro" and r["sku"] == "EL-101")["quantity"]
    == 18
)
assert len(state["runs"]) == 14 and len(state["inventory"]) == 48
assert all(r["runtime"] == "azure" for r in state["runs"])
evidence = {
    "app_url": base,
    "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "health": "ready",
    "runtime": "azure",
    "runs": len(state["runs"]),
    "completed": sum(r["status"] == "completed" for r in state["runs"]),
    "rejected": sum(r["status"] == "rejected" for r in state["runs"]),
    "inventory_rows": 48,
    "checks": [
        "twelve_supplier_warehouse_snapshots",
        "invalid_file_preserves_inventory",
        "correction_replaces_snapshot",
        "duplicate_returns_same_id",
    ],
    "correction_run": corrected["id"],
    "rejected_run": bad["id"],
}
(root / "evidence").mkdir(exist_ok=True)
(root / "evidence/cloud-public.json").write_text(json.dumps(evidence, indent=2) + "\n")
(root / "dist/assets/demo.json").write_text(
    json.dumps({"catalog": get("/api/catalog"), "state": state}, ensure_ascii=False)
)
(root / "dist/assets/mode.json").write_text(json.dumps({"mode": "snapshot", "cloud_url": base}))
print(json.dumps(evidence, indent=2), flush=True)
