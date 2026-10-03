"""Contracts, quality validation and SQL storage. Raw speeds are kbps, UI speeds Mbps."""
import hashlib
import json
import math
import re
import sqlite3
from pathlib import Path

PERIOD = re.compile(r"^20\d{2}-Q[1-4]$")
COLUMNS = ("region", "period", "network", "quadkey", "longitude", "latitude",
           "download_kbps", "upload_kbps", "latency_ms", "tests", "devices")
SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
 region TEXT NOT NULL, period TEXT NOT NULL, network TEXT NOT NULL,
 quadkey TEXT NOT NULL, longitude REAL NOT NULL, latitude REAL NOT NULL,
 download_kbps REAL NOT NULL, upload_kbps REAL NOT NULL, latency_ms REAL NOT NULL,
 tests INTEGER NOT NULL, devices INTEGER NOT NULL,
 PRIMARY KEY(region,period,network,quadkey),
 CHECK(network IN ('fixed','mobile')),
 CHECK(tests > 0 AND devices > 0 AND devices <= tests),
 CHECK(download_kbps >= 0 AND upload_kbps >= 0 AND latency_ms >= 0)
);
CREATE INDEX IF NOT EXISTS selection ON measurements(region,network,period);
CREATE TABLE IF NOT EXISTS partitions (
 region TEXT, period TEXT, network TEXT, sha256 TEXT NOT NULL, rows INTEGER NOT NULL,
 source_url TEXT NOT NULL, PRIMARY KEY(region,period,network)
);
"""


def source_url(period, network):
    if not PERIOD.fullmatch(period) or network not in ("fixed", "mobile"):
        raise ValueError("Invalid source partition")
    year, quarter = int(period[:4]), int(period[-1])
    month = (quarter - 1) * 3 + 1
    return ("https://ookla-open-data.s3.amazonaws.com/parquet/performance/"
            f"type={network}/year={year}/quarter={quarter}/"
            f"{year}-{month:02d}-01_performance_{network}_tiles.parquet")


def validate(rows, bbox):
    if not rows:
        raise ValueError("Empty source partition: refusing to publish")
    seen = set()
    for row in rows:
        if set(row) != set(COLUMNS):
            raise ValueError("Unexpected source schema")
        key = tuple(row[k] for k in COLUMNS[:4])
        if key in seen:
            raise ValueError("Duplicate tile in source partition")
        seen.add(key)
        if not PERIOD.fullmatch(row['period']) or row['network'] not in ('fixed', 'mobile'):
            raise ValueError("Invalid period/network")
        if not isinstance(row['quadkey'], str) or not re.fullmatch(r'[0-3]{16}', row['quadkey']):
            raise ValueError("Invalid zoom-16 quadkey")
        for field in COLUMNS[4:]:
            if not isinstance(row[field], (int, float)) or not math.isfinite(row[field]):
                raise ValueError(f"Non-finite numeric value: {field}")
        if not (bbox[0] <= row['longitude'] <= bbox[2] and bbox[1] <= row['latitude'] <= bbox[3]):
            raise ValueError("Coordinate outside requested study area")
        if any(row[k] < 0 for k in ('download_kbps', 'upload_kbps', 'latency_ms')):
            raise ValueError("Negative performance metric")
        if any(type(row[k]) is not int or row[k] <= 0 for k in ('tests', 'devices')):
            raise ValueError("Invalid test/device count")
        if row['devices'] > row['tests']:
            raise ValueError("Devices exceed tests")


def connect(path: Path, readonly=False):
    if readonly:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def replace_partition(conn, rows, checksum, url):
    region, period, network = (rows[0][k] for k in COLUMNS[:3])
    if any(tuple(r[k] for k in COLUMNS[:3]) != (region, period, network) for r in rows):
        raise ValueError("Mixed partitions")
    prior = conn.execute('SELECT sha256 FROM partitions WHERE region=? AND period=? AND network=?',
                         (region, period, network)).fetchone()
    if prior and prior['sha256'] == checksum:
        return False
    # Caller controls the transaction: deleting and inserting must commit together.
    conn.execute('DELETE FROM measurements WHERE region=? AND period=? AND network=?',
                 (region, period, network))
    conn.executemany(f"INSERT INTO measurements VALUES ({','.join('?' for _ in COLUMNS)})",
                     [tuple(r[k] for k in COLUMNS) for r in rows])
    conn.execute('INSERT OR REPLACE INTO partitions VALUES (?,?,?,?,?,?)',
                 (region, period, network, checksum, len(rows), url))
    return True


def query(conn, region, network, period=None, minimum_tests=10):
    params = [region, network, minimum_tests]
    where = 'region=? AND network=? AND tests>=?'
    if period:
        where += ' AND period=?'
        params.append(period)
    return [dict(r) for r in conn.execute(
        f'SELECT * FROM measurements WHERE {where} ORDER BY period,quadkey', params)]


def summary(rows):
    tests = sum(r['tests'] for r in rows)
    if not tests:
        return {'tiles': 0, 'tests': 0, 'download_mbps': None, 'upload_mbps': None, 'latency_ms': None}
    return {'tiles': len(rows), 'tests': tests,
            'download_mbps': sum(r['download_kbps'] * r['tests'] for r in rows) / tests / 1000,
            'upload_mbps': sum(r['upload_kbps'] * r['tests'] for r in rows) / tests / 1000,
            'latency_ms': sum(r['latency_ms'] * r['tests'] for r in rows) / tests}


def digest_rows(rows):
    """Stable logical digest across Parquet integers and SQLite REAL roundtrips."""
    canonical = []
    for row in sorted(rows, key=lambda r: tuple(r[k] for k in COLUMNS[:4])):
        record = dict(row)
        for key in COLUMNS[4:9]:
            record[key] = float(record[key])
        canonical.append(record)
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
