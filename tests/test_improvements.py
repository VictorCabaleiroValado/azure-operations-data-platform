import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operations_cloud.api import create_app
from operations_cloud.monitor import Monitor, parse_metrics
from operations_cloud.service import process, state, submit
from operations_cloud.store import LocalStore, write_json

SAMPLES = Path(__file__).resolve().parents[1] / 'samples'


def load(store, filename, content=None, warehouse='centro', received=None):
    record = submit(store, content or (SAMPLES / filename).read_bytes(), 'nexo', warehouse, filename)
    if received:
        record['received_at'] = received
        write_json(store, f"runs/{record['id']}.json", record)
    return process(store, record['id'])['id']


def test_comparison_correction_rejection_and_scope(tmp_path):
    store = LocalStore(tmp_path)
    first = load(store, 'nexo-centro.csv', received='2026-10-03T01:00:00Z')
    other = load(store, 'nexo-centro.csv', warehouse='leganes')
    bad = load(store, 'nexo-centro-errors.csv')
    corrected = load(store, 'nexo-centro-corrected.csv', received='2026-10-03T02:00:00Z')
    result = state(store)['comparisons']
    assert result[first]['baseline_id'] is None and not result[first]['active']
    assert result[other]['baseline_id'] is None and result[other]['active']
    assert bad not in result
    assert result[corrected]['baseline_id'] == first
    assert result[corrected]['units_delta'] == 10
    assert result[corrected]['value_delta_cents'] == 649000
    assert result[corrected]['changes'][0]['before_quantity'] == 8
    assert result[corrected]['changes'][0]['after_quantity'] == 18
    assert other not in state(store, 'centro')['comparisons']


def test_comparison_business_order_and_removed_products(tmp_path):
    store = LocalStore(tmp_path)
    newer = load(store, 'nexo-centro-corrected.csv', received='2026-10-03T02:00:00Z')
    older_bytes = (SAMPLES / 'nexo-centro.csv').read_bytes().replace(b'2026-10-03', b'2026-10-02')
    older = load(store, 'older.csv', older_bytes)
    assert state(store)['comparisons'][newer]['baseline_id'] == older
    lines = (SAMPLES / 'nexo-centro-corrected.csv').read_bytes().splitlines()
    short = load(store, 'short.csv', b'\n'.join(lines[:2]) + b'\n', received='2026-10-04T01:00:00Z')
    result = state(store)['comparisons'][short]
    assert len(result['changes']) == 3
    assert all(c['change'] == 'removed' and c['after_cost_cents'] is None for c in result['changes'])
    assert result['units_delta'] == -191


def test_comparison_cost_only_added_and_unchanged(tmp_path):
    store = LocalStore(tmp_path)
    original = (SAMPLES / 'nexo-centro.csv').read_bytes()
    short = b'\n'.join(original.splitlines()[:2]) + b'\n'
    load(store, 'short.csv', short, received='2026-10-03T01:00:00Z')
    full = load(store, 'full.csv', original, received='2026-10-03T02:00:00Z')
    assert len(state(store)['comparisons'][full]['changes']) == 3
    cost = load(store, 'cost.csv', original.replace(b'649.00', b'650.00'), received='2026-10-03T03:00:00Z')
    comparison = state(store)['comparisons'][cost]
    assert comparison['units_delta'] == 0 and comparison['value_delta_cents'] == 800
    assert len(comparison['changes']) == 1
    assert comparison['changes'][0]['before_cost_cents'] == 64900
    unchanged = load(store, 'later.csv', original.replace(b'649.00', b'650.00').replace(b'2026-10-03', b'2026-10-04'))
    assert state(store)['comparisons'][unchanged]['changes'] == []


def test_monitor_missing_and_unavailable_are_not_zero(monkeypatch):
    monkeypatch.delenv('OPERATIONS_LOG_WORKSPACE_ID', raising=False)
    assert Monitor().read()['status'] == 'not_configured'
    monkeypatch.setenv('OPERATIONS_LOG_WORKSPACE_ID', 'invalid')
    monitor = Monitor()
    result = monitor.read()
    assert result['status'] == 'unavailable' and 'metrics' not in result
    assert monitor.read() is result
    assert Monitor(enabled=False).read()['status'] == 'not_configured'


def test_monitor_aggregates_only_and_rejects_partial():
    fields = ['completed', 'rejected', 'technical_failure_attempts', 'average_duration_ms', 'last_event_at', 'secret']
    payload = {'tables': [{'name': 'PrimaryResult', 'columns': [{'name': k} for k in fields], 'rows': [[13, 1, 0, 42.5, '2026-10-05T12:00:00Z', 'hidden']]}]}
    result = parse_metrics(payload)
    assert result['completed'] == 13 and 'secret' not in result
    payload['error'] = {'code': 'PartialError'}
    with pytest.raises(ValueError):
        parse_metrics(payload)


def test_observability_endpoint_and_comparison_api(tmp_path):
    store = LocalStore(tmp_path)
    run = load(store, 'nexo-centro.csv')
    with TestClient(create_app(store, local_worker=False)) as client:
        assert client.get('/api/observability').json()['status'] == 'not_configured'
        assert client.get('/api/state').json()['comparisons'][run]['active']
        corrected = load(store, 'nexo-centro-corrected.csv')
        assert client.get('/api/runs/' + corrected).json()['comparison']['units_delta'] == 10
        assert client.get('/api/observability').headers['Cache-Control'] == 'no-store'
    # Comparing never rewrites source snapshots.
    original = json.loads(store.get(f'results/{run}.json'))
    state(store)
    assert json.loads(store.get(f'results/{run}.json')) == original


def test_monitor_success_is_cached_and_uses_fixed_query(monkeypatch):
    import io
    from types import SimpleNamespace

    from operations_cloud import monitor as module

    monkeypatch.setenv('OPERATIONS_LOG_WORKSPACE_ID', '00000000-0000-0000-0000-000000000001')
    calls = []
    fields = ['completed', 'rejected', 'technical_failure_attempts', 'average_duration_ms', 'last_event_at']
    response = {'tables': [{'name': 'PrimaryResult', 'columns': [{'name': k} for k in fields], 'rows': [[0, 0, 0, None, None]]}]}

    class Credential:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_token(self, scope):
            assert scope == 'https://api.loganalytics.io/.default'
            return SimpleNamespace(token='test-only')

    def query(request, timeout):
        calls.append(request)
        assert json.loads(request.data)['query'] == module.QUERY
        assert timeout == 15
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(module, 'ManagedIdentityCredential', Credential)
    monkeypatch.setattr(module.urllib.request, 'urlopen', query)
    monitor = Monitor()
    result = monitor.read()
    assert result['status'] == 'ok' and result['metrics']['completed'] == 0
    assert result['metrics']['average_duration_ms'] is None
    assert result['checked_at'] and result['scope'] == 'All warehouses'
    assert monitor.read() == result and len(calls) == 1
