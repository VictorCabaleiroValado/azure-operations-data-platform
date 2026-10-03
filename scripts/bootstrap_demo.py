"""Recreate the local SQL store from the included, verified real-data snapshot."""
import json
from pathlib import Path

from telecom_cloud.model import digest_rows
from telecom_cloud.pipeline import run

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'dist/assets/demo.json').read_text())
release = data['metadata']['release']


def fetch(period, network, region):
    source = next(s for s in release['sources']
                  if (s['region'], s['network'], s['period']) == (region['id'], network, period))
    rows = [r for r in data['rows'] if
            (r['region'], r['network'], r['period']) == (region['id'], network, period)]
    if digest_rows(rows) != source['sha256']:
        raise ValueError('Bundled source partition checksum mismatch')
    return rows, source['url']


result = run(release['config'], root / 'data/processed', fetch)
print(f"Bootstrapped {result['rows']} verified observations from bundled release {release['run_id']}")
