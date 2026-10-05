"""Fixed, aggregate-only Azure Monitor query; no public query or raw-log interface."""

import json
import os
import threading
import urllib.request
from datetime import datetime, timezone
from time import monotonic
from uuid import UUID

from azure.identity import ManagedIdentityCredential

QUERY = r'''ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(7d)
| where ContainerAppName_s == "operations-processor"
    or tostring(column_ifexists("ContainerJobName_s", "")) == "operations-processor"
    or tostring(column_ifexists("ContainerGroupName_s", "")) startswith "operations-processor-"
| extend event = parse_json(extract(@"(\{.*\})", 1, Log_s))
| extend processed = tostring(event.event) == "file_processed",
    failure = Log_s contains "Processing failed for run"
| where processed or failure
| extend run_id = iff(processed, tostring(event.run_id), extract(@"run ([a-f0-9]{64})", 1, Log_s))
| where isnotempty(run_id)
| summarize failure_attempts=countif(failure), arg_max(TimeGenerated, *) by run_id, processed
| summarize completed=countif(processed and tostring(event.status) == "completed"),
    rejected=countif(processed and tostring(event.status) == "rejected"),
    technical_failure_attempts=sum(failure_attempts),
    average_duration_ms=avgif(todouble(event.duration_ms), processed),
    last_event_at=max(TimeGenerated)'''


def parse_metrics(payload):
    if payload.get("error"):
        raise ValueError("Incomplete monitor response")
    table = next(t for t in payload["tables"] if t["name"] == "PrimaryResult")
    row = dict(zip((c["name"] for c in table["columns"]), table["rows"][0], strict=True))
    # Only expose known aggregate fields, never arbitrary provider columns.
    return {key: row[key] for key in (
        "completed", "rejected", "technical_failure_attempts", "average_duration_ms", "last_event_at"
    )}


class Monitor:
    def __init__(self, enabled=True):
        self.workspace = os.getenv("OPERATIONS_LOG_WORKSPACE_ID") if enabled else None
        self.cached = None
        self.at = 0.0
        self.lock = threading.Lock()

    def read(self):
        if not self.workspace:
            return {"status": "not_configured", "source": "Azure Monitor", "window_days": 7,
                    "message": "Azure Monitor is not connected in this runtime."}
        with self.lock:
            if self.cached is not None and monotonic() - self.at < 300:
                return self.cached
            result = {"source": "Azure Monitor", "window_days": 7,
                      "checked_at": datetime.now(timezone.utc).isoformat(), "scope": "All warehouses"}
            try:
                workspace = str(UUID(self.workspace))
                with ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID")) as credential:
                    token = credential.get_token("https://api.loganalytics.io/.default").token
                request = urllib.request.Request(
                    f"https://api.loganalytics.azure.com/v1/workspaces/{workspace}/query",
                    data=json.dumps({"query": QUERY, "timespan": "P7D"}).encode(),
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    metrics = parse_metrics(json.load(response))
                result.update(status="ok", metrics=metrics)
            except Exception:
                # Permission, network and partial-result failures must never look like zero activity.
                result.update(status="unavailable", message="Azure Monitor is unavailable. Check workspace access and connectivity.")
            self.cached, self.at = result, monotonic()
            return result
