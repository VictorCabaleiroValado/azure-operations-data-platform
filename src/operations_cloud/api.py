"""Portal API. Public Azure demo accepts only bundled synthetic sample files."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .catalog import PRODUCTS, SUPPLIERS, WAREHOUSE_IDS, WAREHOUSES
from .service import csv_bytes, get_run, process, retry, runs, state, submit
from .store import Busy, configured_store
from .validation import MAX_BYTES

ROOT = Path(os.getenv("OPERATIONS_ROOT", Path.cwd()))


def create_app(store=None, local_worker=True):
    store = store or configured_store()
    cache = {"at": 0.0, "data": None}
    samples = json.loads((ROOT / "samples/manifest.json").read_text())

    def refresh():
        if cache["data"] is None or monotonic() - cache["at"] > (10 if store.mode == "azure" else 1):
            cache["data"] = state(store)
            cache["at"] = monotonic()
        return cache["data"]

    async def work():
        while True:
            try:
                for record in await asyncio.to_thread(runs, store):
                    if record["status"] in {"queued", "processing"}:
                        try:
                            await asyncio.to_thread(process, store, record["id"])
                            cache["at"] = 0
                        except Busy:
                            pass
            except Exception:
                logging.exception("Local worker will retry")
            await asyncio.sleep(1)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(work()) if local_worker and store.mode == "local" else None
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="Azure Operations Data Platform", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tile.openstreetmap.org https://tiles.openfreemap.org; connect-src 'self' https://tiles.openfreemap.org; worker-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health/live")
    def live():
        return {"status": "ok", "application": "azure-operations-data-platform"}

    @app.get("/health/ready")
    def ready():
        try:
            store.names("runs")
            return {"status": "ready", "storage": store.mode}
        except Exception as exc:
            raise HTTPException(503, "Storage unavailable") from exc

    @app.get("/api/catalog")
    def catalog():
        return {
            "warehouses": WAREHOUSES,
            "suppliers": SUPPLIERS,
            "products": PRODUCTS,
            "samples": samples,
            "runtime": store.mode,
            "upload_policy": "bundled_samples_only" if store.mode == "azure" else "local_csv",
            "data_note": "Fictional demo company, suppliers, inventory and locations.",
        }

    @app.get("/api/state")
    def current_state():
        return refresh()

    @app.get("/api/runs/{run_id}")
    def detail(run_id: str):
        try:
            return get_run(store, run_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Processing run not found.") from exc

    @app.post("/api/uploads", status_code=202)
    async def upload(
        request: Request,
        supplier: str,
        warehouse: str,
        filename: str = Query("inventory.csv", max_length=100),
    ):
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                raise HTTPException(413, "Maximum 512 KiB.")
        raw = bytes(content)
        if store.mode == "azure":
            allowed = any(
                s["supplier"] == supplier
                and s["warehouse"] == warehouse
                and (ROOT / "samples" / s["file"]).read_bytes() == raw
                for s in samples
            )
            if not allowed:
                raise HTTPException(
                    403,
                    "The public Azure demo accepts only sample files for the selected warehouse. Use local mode for custom files.",
                )
        try:
            result = await asyncio.to_thread(submit, store, raw, supplier, warehouse, filename)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        cache["at"] = 0
        return result

    @app.post("/api/runs/{run_id}/retry")
    def retry_run(run_id: str):
        if store.mode == "azure":
            raise HTTPException(
                403, "Manual Azure retries are restricted to the operator through the CLI."
            )
        try:
            record = retry(store, run_id)
            cache["at"] = 0
            return record
        except FileNotFoundError as exc:
            raise HTTPException(404, "Processing run not found.") from exc
        except (ValueError, Busy) as exc:
            raise HTTPException(409, str(exc) or "Processing run is busy.") from exc

    @app.get("/api/inventory.csv")
    def export(warehouse: str = ""):
        if warehouse and warehouse not in WAREHOUSE_IDS:
            raise HTTPException(422, "Unknown warehouse.")
        stock = refresh()["inventory"]
        if warehouse:
            stock = [r for r in stock if r["warehouse"] == warehouse]
        return Response(
            csv_bytes(stock),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="inventory.csv"'},
        )

    @app.get("/api/samples/{filename}")
    def sample(filename: str):
        if filename not in {s["file"] for s in samples}:
            raise HTTPException(404, "Sample not found.")
        return FileResponse(ROOT / "samples" / filename, media_type="text/csv", filename=filename)

    @app.get("/assets/mode.json")
    def mode():
        return {"mode": "api"}

    app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")

    @app.get("/")
    def homepage():
        return FileResponse(ROOT / "web/index.html")

    return app


app = create_app()
