"""Export an explicit static snapshot for GitHub Pages with the same reviewed source rows."""

import json
import shutil
from pathlib import Path

from telecom_cloud.model import connect

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "data/processed/current.json").read_text())
with connect(root / "data/processed" / manifest["database"], readonly=True) as db:
    rows = [
        dict(row) for row in db.execute("SELECT * FROM measurements ORDER BY region,network,period,quadkey")
    ]
out = root / "dist"
(out / "assets").mkdir(parents=True, exist_ok=True)
shutil.copy(root / "web/index.html", out / "index.html")
for name in ["app.js", "styles.css"]:
    shutil.copy(root / "web" / name, out / "assets" / name)
(out / "assets/mode.json").write_text('{"mode":"snapshot"}\n')
(out / "assets/demo.json").write_text(
    json.dumps(
        {"metadata": {"release": manifest, "runtime": {"mode": "snapshot"}}, "rows": rows},
        separators=(",", ":"),
    )
)
(out / ".nojekyll").touch()
print(f"Exported {len(rows)} real observations to {out}")
