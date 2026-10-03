import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from telecom_cloud import api
from telecom_cloud.model import connect, digest_rows, query, source_url, summary, validate
from telecom_cloud.pipeline import run

CONFIG = {'periods': ['2024-Q3', '2024-Q4'], 'networks': ['fixed'],
          'regions': [{'id': 'test', 'name': 'Test area', 'bbox': [-4, 40, -3, 41]}],
          'review_download_mbps': 100, 'review_latency_ms': 40, 'minimum_tests': 10}


def fixture_fetch(period, network, region):
    # Explicit synthetic test fixtures, never used by the shipped demo.
    return [dict(region=region['id'], period=period, network=network, quadkey='0'*15+str(i),
                 longitude=-3.8+i*.1, latitude=40.4, download_kbps=(i+1)*10000,
                 upload_kbps=5000, latency_ms=20, tests=10 if i == 0 else 30, devices=5)
            for i in range(2)], source_url(period, network)


@pytest.fixture
def built(tmp_path):
    manifest = run(CONFIG, tmp_path, fixture_fetch)
    return tmp_path, manifest


def test_idempotent_rerun(built):
    path, first = built
    second = run(CONFIG, path, fixture_fetch)
    assert second['changed_partitions'] == 0
    assert first['rows'] == second['rows'] == 4
    with connect(path / second['database'], readonly=True) as db:
        assert db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0] == 4


def test_failed_partition_keeps_last_good_snapshot(built):
    path, first = built
    before = (path / 'current.json').read_bytes()

    def broken(period, network, region):
        rows, url = fixture_fetch(period, network, region)
        if period == '2024-Q4':
            rows[0]['download_kbps'] = -1
        return rows, url

    with pytest.raises(ValueError, match='Negative'):
        run(CONFIG, path, broken)
    assert (path / 'current.json').read_bytes() == before
    assert (path / first['database']).exists()
    assert not list(path.glob('.build-*'))


def test_corrected_partition_replaces_not_appends(built):
    path, _ = built

    def corrected(period, network, region):
        rows, url = fixture_fetch(period, network, region)
        if period == '2024-Q4':
            rows = rows[:1]
            rows[0]['download_kbps'] = 40000
        return rows, url

    new = run(CONFIG, path, corrected)
    assert new['rows'] == 3
    assert new['changed_partitions'] == 1
    with connect(path / new['database'], readonly=True) as db:
        rows = query(db, 'test', 'fixed', '2024-Q4')
        assert len(rows) == 1
        assert rows[0]['download_kbps'] == 40000


def test_removed_scope_is_pruned(built):
    path, _ = built
    config = copy.deepcopy(CONFIG)
    config['periods'] = ['2024-Q4']
    new = run(config, path, fixture_fetch)
    assert new['rows'] == 2
    with connect(path / new['database'], readonly=True) as db:
        assert query(db, 'test', 'fixed', '2024-Q3') == []


@pytest.mark.parametrize('field,value', [('tests', 0), ('devices', 11), ('latitude', 90),
                                       ('download_kbps', float('nan')), ('latency_ms', -1),
                                       ('quadkey', 'bad'), ('tests', 1.5)])
def test_reject_invalid_source(field, value):
    rows, _ = fixture_fetch('2024-Q3', 'fixed', CONFIG['regions'][0])
    rows[0][field] = value
    with pytest.raises(ValueError):
        validate(rows, CONFIG['regions'][0]['bbox'])


def test_reject_duplicate_and_empty():
    rows, _ = fixture_fetch('2024-Q3', 'fixed', CONFIG['regions'][0])
    with pytest.raises(ValueError, match='Duplicate'):
        validate([rows[0], rows[0]], CONFIG['regions'][0]['bbox'])
    with pytest.raises(ValueError, match='Empty'):
        validate([], CONFIG['regions'][0]['bbox'])


def test_weighted_means_and_units():
    rows, _ = fixture_fetch('2024-Q3', 'fixed', CONFIG['regions'][0])
    result = summary(rows)
    assert result['download_mbps'] == 17.5  # (10 Mbps * 10 + 20 Mbps * 30) / 40
    assert result['tests'] == 40
    assert summary([])['download_mbps'] is None


def test_source_allowlist():
    with pytest.raises(ValueError):
        source_url('2024-Q5', 'fixed')
    with pytest.raises(ValueError):
        source_url('2024-Q4', '../../other')


@pytest.fixture
def client(built, monkeypatch):
    path, _ = built
    monkeypatch.setattr(api, 'DATA', path)
    monkeypatch.delenv('AZURE_STORAGE_ACCOUNT_URL', raising=False)
    with TestClient(api.app) as c:
        yield c


def test_api_filter_comparison_export_contract(client):
    r = client.get('/api/explore', params={'region': 'test', 'period': '2024-Q4', 'minimum_tests': 20})
    assert r.status_code == 200
    body = r.json()
    assert body['summary']['tiles'] == 1
    assert body['summary']['tests'] == 30
    assert body['summary']['download_mbps'] == 20
    assert body['excluded_tiles'] == 1
    assert body['comparison']['matched_tiles'] == 1
    assert body['comparison']['download_change_mbps'] == 0


def test_api_rejects_injection_and_invalid_threshold(client):
    assert client.get('/api/explore', params={'region': "test' OR 1=1--"}).status_code == 400
    assert client.get('/api/explore', params={'region': 'test', 'minimum_tests': 0}).status_code == 422
    assert client.get('/api/explore', params={'region': 'test', 'network': 'invalid'}).status_code == 400


def test_api_assets_health_security(client):
    for url in ['/', '/assets/app.js', '/assets/styles.css', '/health/ready', '/health/live']:
        response = client.get(url)
        assert response.status_code == 200, url
        assert response.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/api/metadata').json()['runtime']['mode'] == 'local'


def test_missing_dataset_not_fabricated(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'DATA', tmp_path)
    monkeypatch.delenv('AZURE_STORAGE_ACCOUNT_URL', raising=False)
    with TestClient(api.app) as c:
        assert c.get('/health/live').status_code == 200
        assert c.get('/health/ready').status_code == 503
        assert c.get('/api/metadata').status_code == 503


def test_cloud_download_verifies_hash(tmp_path):
    from telecom_cloud.storage import download_snapshot
    payload = b'not-a-real-db'
    manifest = {'database': 'release/analytics.db', 'database_sha256': '0'*64}

    class Download:
        def __init__(self, value):
            self.value = value
        def readall(self):
            return self.value

    class Client:
        def download_blob(self, name):
            return Download(json.dumps(manifest).encode() if name == 'current.json' else payload)

    with pytest.raises(ValueError, match='checksum'):
        download_snapshot(tmp_path, Client())
    assert not (tmp_path / 'current.json').exists()
    manifest['database_sha256'] = hashlib.sha256(payload).hexdigest()
    download_snapshot(tmp_path, Client())
    assert (tmp_path / 'release/analytics.db').read_bytes() == payload


def test_real_demo_reconciles():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / 'dist/assets/demo.json').read_text())
    rows = data['rows']
    manifest = data['metadata']['release']
    assert len(rows) == manifest['rows']
    assert manifest['data_kind'] == 'observed_public_measurements'
    for source in manifest['sources']:
        partition = [r for r in rows if all(r[k] == source[k] for k in ('region', 'period', 'network'))]
        assert len(partition) == source['rows']
        assert digest_rows(partition) == source['sha256']
        region = next(r for r in manifest['config']['regions'] if r['id'] == source['region'])
        validate(partition, region['bbox'])


def test_local_writer_lock(built):
    import fcntl
    path, _ = built
    with (path / '.pipeline.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            run(CONFIG, path, fixture_fetch)


def test_source_scope_mismatch_keeps_previous(built):
    path, _ = built
    before = (path / 'current.json').read_bytes()

    def wrong(period, network, region):
        rows, url = fixture_fetch(period, network, region)
        rows[0]['region'] = 'wrong-region'
        return rows, url

    with pytest.raises(ValueError, match='scope'):
        run(CONFIG, path, wrong)
    assert (path / 'current.json').read_bytes() == before


@pytest.mark.parametrize('fail_pointer', [False, True])
def test_cloud_publication_order_and_failed_pointer(built, monkeypatch, fail_pointer):
    from azure.core.exceptions import ResourceNotFoundError

    from telecom_cloud import pipeline, storage
    path, manifest = built
    objects = {}
    calls = []

    class Lease:
        released = False
        def renew(self):
            calls.append('renew')
        def release(self):
            self.released = True

    lease = Lease()

    class Lock:
        def upload_blob(self, *args, **kwargs):
            pass
        def acquire_lease(self, **kwargs):
            return lease

    class Client:
        def get_blob_client(self, name):
            return Lock()
        def download_blob(self, name):
            raise ResourceNotFoundError('No release yet')
        def upload_blob(self, name, payload, **kwargs):
            calls.append(name)
            if name == 'current.json' and fail_pointer:
                raise RuntimeError('Injected pointer upload failure')
            objects[name] = payload

    monkeypatch.setattr(storage, 'container', Client)
    monkeypatch.setattr(pipeline, 'run', lambda *_: copy.deepcopy(manifest))
    if fail_pointer:
        with pytest.raises(RuntimeError, match='Injected'):
            storage.cloud_pipeline(CONFIG, path)
        assert 'current.json' not in objects
    else:
        result = storage.cloud_pipeline(CONFIG, path)
        pointer = json.loads(objects['current.json'])
        assert pointer['database'] in objects
        assert hashlib.sha256(objects[pointer['database']]).hexdigest() == result['database_sha256']
        assert calls.index(pointer['database']) < calls.index('current.json')
        assert calls[calls.index('current.json')-1] == 'renew'
    assert lease.released
