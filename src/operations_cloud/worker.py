"""One bounded Azure Queue batch per Container Apps Job execution."""

import json
import logging
import re

from .service import get_run, now, process
from .store import Busy, configured_store, write_json


def consume(store, limit=20):
    handled = 0
    messages = store.queue.receive_messages(messages_per_page=1, max_messages=limit, visibility_timeout=300)
    for message in messages:
        run_id = message.content
        if not re.fullmatch(r"[a-f0-9]{64}", run_id):
            store.dead.send_message(json.dumps({"reason": "invalid_message"}))
            store.queue.delete_message(message)
            continue
        try:
            process(store, run_id)
        except Busy:
            continue
        except Exception:
            if message.dequeue_count < 5:
                raise
            try:
                with store.lock(run_id):
                    record = get_run(store, run_id)
                    # Another delivery could have completed while this one failed.
                    if record["status"] not in {"completed", "rejected"}:
                        record.update(
                            status="failed",
                            finished_at=now(),
                            errors=[
                                {
                                    "line": 0,
                                    "message": "Fallo técnico tras cinco entregas; revisa Azure Monitor y reintenta.",
                                }
                            ],
                        )
                        write_json(store, f"runs/{run_id}.json", record)
            except FileNotFoundError:
                pass
            store.dead.send_message(json.dumps({"run_id": run_id, "reason": "delivery_limit"}))
        store.queue.delete_message(message)
        handled += 1
    return handled


def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("azure").setLevel(logging.WARNING)
    store = configured_store()
    if store.mode != "azure":
        raise SystemExit("Cloud worker requires OPERATIONS_STORAGE_ACCOUNT.")
    consume(store)


if __name__ == "__main__":
    main()
