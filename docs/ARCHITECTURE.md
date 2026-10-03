# Architecture decisions

## Bounded, event-driven data integration

One Container App serves the portal and API; one event-driven Container Apps Job processes queued files. Azure Blob Storage holds immutable originals and normalized results plus mutable run records. Queue Storage provides at-least-once delivery. Each job processes at most twenty messages, one at a time, to amortize cold starts. Both compute components scale to zero. No calendar schedule is enabled.

Container Apps Jobs replace the initially discussed Functions option: the same Python image can run the web service and a short-lived job, reducing duplicated packaging. [Microsoft documents this queue-driven pattern](https://learn.microsoft.com/en-us/azure/container-apps/tutorial-event-driven-jobs).

## State and recovery

Upload original first, then create the run record atomically if absent, then enqueue its ID. A repeat upload repairs an interrupted enqueue for non-terminal work. A per-run renewable 60-second blob lease excludes concurrent processors; local mode uses `flock`. A worker writes the normalized result before marking the run complete. The query layer includes only complete runs. Validation failures are terminal rejections; transient failures remain retryable through message visibility. After five failed deliveries, the run is marked failed and its ID goes to `failed-jobs`. The operator can requeue it after fixing the cause.

No distributed transaction spans upload and queue submission. If a client disconnects before enqueue, repeat the upload or use the recovery command; this is an explicit limitation. A production system would use an outbox or a reconciliation process. Blob leases reduce concurrent publication risk but do not replace a transactional database for high-volume inventory mutations.

## Storage and SQL

This portfolio workload is bounded by fourteen approved fixture files and four warehouses. Blob listing and in-memory DuckDB SQL keep persistent infrastructure small. They are not an architecture for unbounded inventory traffic. For a larger service, introduce indexed run metadata and a relational store with transactional updates. Azure SQL/Data Factory are not deployed or claimed.

## Identity and public access

The API and job have separate user-assigned managed identities. Both receive Blob Data Contributor on the single project container because each writes run documents. The API can send messages only to the input queue. The worker can consume that queue and send failed IDs to the dead-letter queue. Both can pull the private project image. Shared storage account keys and anonymous blob access are disabled.

The public API exposes only synthetic fixtures. It rejects arbitrary uploads and manual retry requests. Local mode permits own files up to the size limit. This demo is not a multi-tenant supplier portal: production operation requires user authentication, authorization, malware policy, retention and load testing appropriate to its data.

## Map and presentation

Leaflet 1.9.4 is vendored with its licence. OpenStreetMap tiles are requested by the visitor's browser for its visible viewport, with attribution, normal caching and Referer headers. No bulk tile downloads. A button list provides equivalent warehouse selection if map tiles are unavailable. Hosting and tile providers can change independently.
