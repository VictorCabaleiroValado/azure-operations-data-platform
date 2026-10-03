"""Create disclosed synthetic fixtures and optionally process them locally."""

import csv
import io
import json
from pathlib import Path

from operations_cloud.catalog import PRODUCTS, SUPPLIERS, WAREHOUSES
from operations_cloud.service import process, submit
from operations_cloud.store import LocalStore

ROOT = Path(__file__).resolve().parents[1]


def build_samples():
    manifest = []
    for wi, warehouse in enumerate(WAREHOUSES):
        for si, supplier in enumerate(SUPPLIERS):
            output = io.StringIO(newline="")
            writer = csv.writer(output, delimiter=supplier["delimiter"])
            writer.writerow(supplier["fields"])
            for pi, product in enumerate(PRODUCTS[si * 4 : si * 4 + 4]):
                quantity = [8, 45, 120, 26, 60, 3, 90][(wi * 3 + si + pi) % 7]
                writer.writerow(
                    [product["sku"], quantity, f"{product['cost_cents'] / 100:.2f}", "2026-10-03"]
                )
            name = f"{supplier['id']}-{warehouse['id']}.csv"
            (ROOT / "samples" / name).write_bytes(output.getvalue().encode())
            manifest.append(
                {
                    "file": name,
                    "supplier": supplier["id"],
                    "warehouse": warehouse["id"],
                    "kind": "valid",
                    "label": f"{supplier['name']} · {warehouse['name']}",
                }
            )
    base = (ROOT / "samples/nexo-centro.csv").read_text()
    (ROOT / "samples/nexo-centro-errors.csv").write_text(
        base.replace("EL-101,8,", "EL-101,-8,").replace("EL-102,45,", "UNKNOWN,45,")
    )
    (ROOT / "samples/nexo-centro-corrected.csv").write_text(base.replace("EL-101,8,", "EL-101,18,"))
    manifest += [
        {
            "file": "nexo-centro-errors.csv",
            "supplier": "nexo",
            "warehouse": "centro",
            "kind": "invalid",
            "label": "Ejemplo con errores · Centro",
        },
        {
            "file": "nexo-centro-corrected.csv",
            "supplier": "nexo",
            "warehouse": "centro",
            "kind": "correction",
            "label": "Corrección de existencias · Centro",
        },
    ]
    (ROOT / "samples/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def seed(store):
    for item in json.loads((ROOT / "samples/manifest.json").read_text()):
        if item["kind"] == "correction":
            continue
        run = submit(
            store,
            (ROOT / "samples" / item["file"]).read_bytes(),
            item["supplier"],
            item["warehouse"],
            item["file"],
        )
        process(store, run["id"])


if __name__ == "__main__":
    build_samples()
    seed(LocalStore(ROOT / "data/operations"))
    print("Created 14 synthetic fixtures; seeded 12 valid snapshots and one rejected file.")
