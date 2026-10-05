"""Publish a read-only static edition with the exact API dataset and synthetic fixtures."""

import argparse
import json
import shutil
import urllib.request
from pathlib import Path

from operations_cloud.api import create_app
from operations_cloud.service import state
from operations_cloud.store import configured_store

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--cloud-url", help="Verified public Azure app URL; export its actual API data.")
args = parser.parse_args()
if args.cloud_url:
    if not args.cloud_url.startswith("https://"):
        parser.error("The cloud URL must use HTTPS")

    def fetch(path):
        with urllib.request.urlopen(args.cloud_url.rstrip("/") + path, timeout=60) as response:
            return json.load(response)

    catalog = fetch("/api/catalog")
    snapshot = fetch("/api/state")
    observability = fetch("/api/observability")
    if catalog["runtime"] != "azure" or any(r["runtime"] != "azure" for r in snapshot["runs"]):
        raise ValueError("Cloud export requires records actually processed in Azure")
else:
    store = configured_store()
    app = create_app(store, local_worker=False)
    catalog = next(r for r in app.routes if r.path == "/api/catalog").endpoint()
    snapshot = state(store)
    observability = {"status": "not_configured", "source": "Azure Monitor", "window_days": 7}
output = ROOT / "dist"
output.mkdir(exist_ok=True)
shutil.copy(ROOT / "web/index.html", output / "index.html")
shutil.copytree(
    ROOT / "web", output / "assets", dirs_exist_ok=True, ignore=shutil.ignore_patterns("index.html")
)
shutil.copytree(ROOT / "samples", output / "samples", dirs_exist_ok=True)
mode = {"mode": "snapshot"}
if args.cloud_url:
    mode["cloud_url"] = args.cloud_url.rstrip("/")
config_path = ROOT / "evidence/cloud-public.json"
if config_path.exists() and not args.cloud_url:
    mode["cloud_url"] = json.loads(config_path.read_text())["app_url"]
(output / "assets/mode.json").write_text(json.dumps(mode))
(output / "assets/demo.json").write_text(
    json.dumps({"catalog": catalog, "state": snapshot, "observability": observability}, ensure_ascii=False)
)
(output / ".nojekyll").touch()
print("Exported operations snapshot; uploads are explicitly disabled on static hosting.")
