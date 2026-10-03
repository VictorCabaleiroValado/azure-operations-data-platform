"""Durable run documents: atomic local files or private Azure blobs, plus a cloud queue."""

import fcntl
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


class Busy(Exception):
    pass


class LocalStore:
    mode = "local"

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, name, content, create=False):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if create:
            # Protect create-if-absent and expose only complete bytes.
            with self.lock("create"):
                if target.exists():
                    return False
                self.put(name, content)
                return True
        fd, temporary = tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True

    def get(self, name):
        return (self.root / name).read_bytes()

    def names(self, prefix):
        directory = self.root / prefix
        return [str(p.relative_to(self.root)) for p in directory.glob("*.json")]

    @contextmanager
    def lock(self, key):
        with (self.root / f"{key}.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Busy() from exc
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def enqueue(self, run_id):
        # The local worker recovers queued/processing documents after a restart.
        pass


class AzureStore:
    mode = "azure"

    def __init__(self, account):
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
        from azure.storage.queue import QueueClient

        credential = DefaultAzureCredential()
        self.container = BlobServiceClient(
            f"https://{account}.blob.core.windows.net", credential=credential, retry_total=2
        ).get_container_client("operations")
        self.queue = QueueClient(
            f"https://{account}.queue.core.windows.net", "file-jobs", credential=credential, retry_total=2
        )
        self.dead = QueueClient(
            f"https://{account}.queue.core.windows.net", "failed-jobs", credential=credential, retry_total=2
        )

    def put(self, name, content, create=False):
        try:
            self.container.upload_blob(name, content, overwrite=not create)
            return True
        except ResourceExistsError:
            return False

    def get(self, name):
        try:
            return self.container.download_blob(name).readall()
        except ResourceNotFoundError as exc:
            raise FileNotFoundError(name) from exc

    def names(self, prefix):
        return [
            b.name
            for b in self.container.list_blobs(name_starts_with=prefix + "/")
            if b.name.endswith(".json")
        ]

    @contextmanager
    def lock(self, key):
        from azure.core.exceptions import HttpResponseError

        blob = self.container.get_blob_client(f"locks/{key}")
        self.put(f"locks/{key}", b"", create=True)
        try:
            lease = blob.acquire_lease(lease_duration=60)
        except HttpResponseError as exc:
            if exc.status_code == 409:
                raise Busy() from exc
            raise
        stop, lost = threading.Event(), []

        def renew():
            while not stop.wait(20):
                try:
                    lease.renew()
                except Exception as exc:
                    lost.append(exc)
                    return

        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
        try:
            yield lambda: self._check_lease(lost, lease)
        finally:
            stop.set()
            thread.join(timeout=30)
            try:
                lease.release()
            except HttpResponseError:
                pass

    @staticmethod
    def _check_lease(lost, lease):
        if lost:
            raise RuntimeError("Processing lease was lost") from lost[0]
        lease.renew()

    def enqueue(self, run_id):
        self.queue.send_message(run_id, time_to_live=604800)


def configured_store():
    account = os.getenv("OPERATIONS_STORAGE_ACCOUNT")
    return AzureStore(account) if account else LocalStore(os.getenv("OPERATIONS_DATA_DIR", "data/operations"))


def read_json(store, name):
    return json.loads(store.get(name))


def write_json(store, name, value, create=False):
    return store.put(name, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), create=create)
