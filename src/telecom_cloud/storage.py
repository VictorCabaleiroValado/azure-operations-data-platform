"""Azure Blob immutable releases with a single leased writer and atomic pointer publication."""
import hashlib
import json
import os
import threading
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


def container():
    url = os.environ['AZURE_STORAGE_ACCOUNT_URL']
    return BlobServiceClient(url, credential=DefaultAzureCredential()).get_container_client(
        os.getenv('TELECOM_CONTAINER', 'curated'))


def download_snapshot(output: Path, client=None):
    client = client or container()
    try:
        manifest = json.loads(client.download_blob('current.json').readall())
    except ResourceNotFoundError:
        return None
    name = manifest['database']
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Invalid snapshot path')
    output.mkdir(parents=True, exist_ok=True)
    target = output / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = client.download_blob(name).readall()
        if hashlib.sha256(payload).hexdigest() != manifest['database_sha256']:
            raise ValueError('Snapshot checksum mismatch')
        tmp = target.with_suffix('.download')
        tmp.write_bytes(payload)
        os.replace(tmp, target)
    pointer = output / '.download-current.json'
    pointer.write_text(json.dumps(manifest))
    os.replace(pointer, output / 'current.json')
    return manifest


def cloud_pipeline(config, output):
    from telecom_cloud.pipeline import run
    client = container()
    lock = client.get_blob_client('_writer.lock')
    try:
        lock.upload_blob(b'lock', overwrite=False)
    except ResourceExistsError:
        pass
    lease = lock.acquire_lease(lease_duration=60)
    stop = threading.Event()
    lease_errors = []

    def renew():
        while not stop.wait(20):
            try:
                lease.renew()
            except Exception as exc:
                lease_errors.append(exc)
                return

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        download_snapshot(output, client)
        manifest = run(config, output)
        if lease_errors:
            raise RuntimeError('Lost publication lease') from lease_errors[0]
        payload = (output / manifest['database']).read_bytes()
        manifest['database_sha256'] = hashlib.sha256(payload).hexdigest()
        client.upload_blob(manifest['database'], payload, overwrite=False)
        client.upload_blob(f"{manifest['run_id']}/manifest.json", json.dumps(manifest).encode(), overwrite=False)
        lease.renew()  # Must still own the writer lease before switching the remote pointer.
        client.upload_blob('current.json', json.dumps(manifest).encode(), overwrite=True)
        return manifest
    finally:
        stop.set()
        thread.join(timeout=25)
        lease.release()
