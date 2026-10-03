"""Fetch public Parquet partitions, validate, and publish an atomic analytical snapshot."""

import argparse
import fcntl
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telecom_cloud.model import connect, digest_rows, replace_partition, source_url, validate

LOG = logging.getLogger("telecom.pipeline")


def fetch_partition(period, network, region):
    import duckdb

    url = source_url(period, network)
    with duckdb.connect() as db:
        db.execute("SET extension_directory='/tmp/telecom-duckdb-extensions'")
        db.execute("INSTALL httpfs; LOAD httpfs;")
        db.execute("SET http_timeout=120")
        db.execute("SET threads=2")
        bbox = region["bbox"]
        records = db.execute(
            """
          SELECT quadkey::VARCHAR, tile_x, tile_y, avg_d_kbps, avg_u_kbps,
                 avg_lat_ms, tests::BIGINT, devices::BIGINT
          FROM read_parquet(?, hive_partitioning=false)
          WHERE tile_x BETWEEN ? AND ? AND tile_y BETWEEN ? AND ? ORDER BY quadkey
        """,
            [url, bbox[0], bbox[2], bbox[1], bbox[3]],
        ).fetchall()
    fields = (
        "quadkey",
        "longitude",
        "latitude",
        "download_kbps",
        "upload_kbps",
        "latency_ms",
        "tests",
        "devices",
    )
    rows = [
        dict(region=region["id"], period=period, network=network, **dict(zip(fields, r))) for r in records
    ]
    return rows, url


def _run(config, output: Path, fetcher=fetch_partition):
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    output.mkdir(parents=True, exist_ok=True)
    # A complete database and manifest live in one immutable version directory.
    # The current.json pointer is replaced only after every partition passes.
    stage = Path(tempfile.mkdtemp(prefix=".build-", dir=output))
    current = output / "current.json"
    try:
        if current.exists():
            prior = json.loads(current.read_text())
            shutil.copyfile(output / prior["database"], stage / "analytics.db")
        conn = connect(stage / "analytics.db")
        sources, changed, total = [], 0, 0
        try:
            with conn:
                expected = []
                for period in config["periods"]:
                    for network in config["networks"]:
                        for region in config["regions"]:
                            rows, url = fetcher(period, network, region)
                            if any(
                                (r["region"], r["period"], r["network"]) != (region["id"], period, network)
                                for r in rows
                            ):
                                raise ValueError("Source partition does not match requested scope")
                            validate(rows, region["bbox"])
                            digest = digest_rows(rows)
                            changed += int(replace_partition(conn, rows, digest, url))
                            total += len(rows)
                            expected.append((region["id"], period, network))
                            sources.append(
                                {
                                    "region": region["id"],
                                    "period": period,
                                    "network": network,
                                    "url": url,
                                    "rows": len(rows),
                                    "sha256": digest,
                                }
                            )
                # Configuration defines the published scope, including removal of old regions/periods.
                for row in conn.execute("SELECT region,period,network FROM partitions").fetchall():
                    key = tuple(row)
                    if key not in expected:
                        conn.execute(
                            "DELETE FROM measurements WHERE region=? AND period=? AND network=?", key
                        )
                        conn.execute("DELETE FROM partitions WHERE region=? AND period=? AND network=?", key)
                actual = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
                if actual != total:
                    raise ValueError(f"Reconciliation mismatch: {actual} != {total}")
        finally:
            conn.close()
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "succeeded",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "rows": total,
            "partitions": len(sources),
            "changed_partitions": changed,
            "database": f"{run_id}/analytics.db",
            "config": config,
            "sources": sources,
            "data_kind": "observed_public_measurements",
            "license": "CC BY-NC-SA 4.0",
            "attribution": "Source: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps.",
            "limitations": [
                "Volunteer tests are not a representative census of households.",
                "Bounding boxes are study areas, not administrative boundaries.",
                "Changes in tested tiles/devices can change aggregate averages.",
                "Counts of devices are not additive across tiles or periods.",
            ],
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(output / run_id)
        pointer = output / f".current-{run_id}.json"
        pointer.write_text(json.dumps(manifest, indent=2) + "\n")
        os.replace(pointer, current)
        LOG.info(
            json.dumps(
                {
                    "event": "pipeline_completed",
                    "run_id": run_id,
                    "rows": total,
                    "changed_partitions": changed,
                }
            )
        )
        return manifest
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        LOG.exception(json.dumps({"event": "pipeline_failed", "run_id": run_id}))
        raise


def run(config, output: Path, fetcher=fetch_partition):
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".pipeline.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(config, output, fetcher)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default=os.getenv("TELECOM_DATA_DIR", "data/processed"))
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = json.loads(Path(args.config).read_text())
    if args.publish:
        from telecom_cloud.storage import cloud_pipeline

        result = cloud_pipeline(config, Path(args.output))
    else:
        result = run(config, Path(args.output))
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("run_id", "rows", "partitions", "changed_partitions", "duration_seconds")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
