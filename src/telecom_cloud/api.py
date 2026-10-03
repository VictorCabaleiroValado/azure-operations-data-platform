"""Read-only analytics API. SQL parameters are bound; no public ingestion endpoint."""
import json
import logging
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from telecom_cloud.model import connect, query, summary

ROOT = Path(os.getenv('TELECOM_ROOT', Path.cwd())).resolve()
DATA = Path(os.getenv('TELECOM_DATA_DIR', ROOT / 'data/processed'))
WEB = ROOT / 'web'
refresh_lock = threading.Lock()
last_refresh = 0.0


def snapshot():
    global last_refresh
    if os.getenv('AZURE_STORAGE_ACCOUNT_URL') and time.monotonic() - last_refresh > 60:
        with refresh_lock:
            if time.monotonic() - last_refresh > 60:
                try:
                    from telecom_cloud.storage import download_snapshot
                    download_snapshot(DATA)
                    last_refresh = time.monotonic()
                except Exception:
                    logging.exception('snapshot_refresh_failed')
                    # Fail closed rather than silently presenting an unlabelled stale cloud snapshot.
                    raise HTTPException(503, 'Cloud snapshot unavailable') from None
    pointer = DATA / 'current.json'
    if not pointer.exists():
        raise HTTPException(503, 'No data release. Run the ingestion pipeline first.')
    result = json.loads(pointer.read_text())
    if not (DATA / result['database']).is_file():
        raise HTTPException(503, 'Data release is incomplete')
    return result


app = FastAPI(title='Azure Telecom Cloud', version='0.1.0')
if os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING'):
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    configure_azure_monitor(instrumentation_options={'fastapi': {'enabled': False}})
    FastAPIInstrumentor.instrument_app(app)


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return response


@app.get('/health/live')
def live():
    return {'status': 'alive'}


@app.get('/health/ready')
def ready():
    manifest = snapshot()
    return {'status': 'ready', 'release': manifest['run_id']}


@app.get('/api/metadata')
def metadata():
    manifest = snapshot()
    return {'release': manifest, 'runtime': {'mode': 'azure' if os.getenv('AZURE_STORAGE_ACCOUNT_URL') else 'local',
                                           'azure_deployment_verified': False}}


@app.get('/api/explore')
def explore(region: str, network: str = 'fixed', period: str = '2024-Q4',
            minimum_tests: int = Query(10, ge=1, le=100000)):
    manifest = snapshot()
    config = manifest['config']
    if region not in [r['id'] for r in config['regions']] or network not in config['networks'] or period not in config['periods']:
        raise HTTPException(400, 'Selection is outside the published data scope')
    conn = connect(DATA / manifest['database'], readonly=True)
    try:
        rows = query(conn, region, network, period, minimum_tests)
        trend = [{'period': p, **summary(query(conn, region, network, p, minimum_tests))}
                 for p in config['periods']]
        selected_index = config['periods'].index(period)
        comparison = None
        if selected_index > 0:
            previous = config['periods'][selected_index - 1]
            old = {r['quadkey']: r for r in query(conn, region, network, previous, minimum_tests)}
            common = [r for r in rows if r['quadkey'] in old]
            # Paired tile mean gives every common tile equal weight in both periods.
            comparison = {'previous_period': previous, 'matched_tiles': len(common),
                          'download_change_mbps': (sum((r['download_kbps'] - old[r['quadkey']]['download_kbps'])
                                                      / 1000 for r in common) / len(common)) if common else None,
                          'method': 'Unweighted mean change across matched tiles; not a causal estimate.'}
        all_count = conn.execute('SELECT count(*) FROM measurements WHERE region=? AND network=? AND period=?',
                                 (region, network, period)).fetchone()[0]
        return {'selection': {'region': region, 'network': network, 'period': period,
                              'minimum_tests': minimum_tests}, 'summary': summary(rows), 'trend': trend,
                'comparison': comparison, 'excluded_tiles': all_count - len(rows), 'tiles': rows,
                'review_thresholds': {'download_mbps': config['review_download_mbps'],
                                      'latency_ms': config['review_latency_ms']}}
    finally:
        conn.close()


@app.get('/')
def index():
    return FileResponse(WEB / 'index.html')


app.mount('/assets', StaticFiles(directory=WEB), name='assets')
