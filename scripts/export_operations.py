"""Publish a read-only static edition with the exact API dataset and synthetic fixtures."""

import json
import shutil
from pathlib import Path

from operations_cloud.api import create_app
from operations_cloud.service import state
from operations_cloud.store import configured_store

ROOT = Path(__file__).resolve().parents[1]
store = configured_store()
app = create_app(store, local_worker=False)
catalog = next(r for r in app.routes if r.path == "/api/catalog").endpoint()
output = ROOT / "dist"
output.mkdir(exist_ok=True)
shutil.copy(ROOT / "web/index.html", output / "index.html")
shutil.copytree(ROOT / "web", output / "assets", dirs_exist_ok=True, ignore=shutil.ignore_patterns('index.html'))
shutil.copytree(ROOT / "samples", output / "samples", dirs_exist_ok=True)
mode = {"mode": "snapshot"}
config_path = ROOT / "evidence/cloud-public.json"
if config_path.exists():
    mode["cloud_url"] = json.loads(config_path.read_text())["app_url"]
(output / "assets/mode.json").write_text(json.dumps(mode))
(output / "assets/demo.json").write_text(
    json.dumps({"catalog": catalog, "state": state(store)}, ensure_ascii=False)
)
(output / ".nojekyll").touch()
print("Exported operations snapshot; uploads are explicitly disabled on static hosting.")
