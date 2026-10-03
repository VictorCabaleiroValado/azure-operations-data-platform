# Architecture decisions

## Scope and acceptance

Deliver a complete local data product, a reproducible cloud deployment definition and inspectable verification evidence. Azure deployment is a distinct acceptance gate requiring an authorized subscription and budget. Initial geography consists of explicitly labelled study rectangles around Madrid and Fayetteville. Initial historical coverage is fixed/mobile Q3–Q4 2024.

## ADR-001: Blob-backed immutable SQL snapshots

The API serves small, read-heavy analytical datasets. The job writes a new SQLite database locally, validates it, uploads it under a unique run ID, then publishes `current.json`. The API downloads a release once per instance, verifies its SHA-256 and opens read-only SQL connections. SQL queries use bound parameters. Each replica has an independent, disposable cache.

Benefits: simple rollback, no shared writable database files, low resource footprint, offline reproduction and clear data lineage. Limits: full snapshot downloads, bounded dataset size and up to 60 seconds of per-instance refresh delay. This is not suitable for high-write workloads or unbounded data. Azure SQL becomes justified if transactional multi-writer access or larger concurrent query workloads are required.

## ADR-002: Separate runtime identities

The job receives Storage Blob Data Contributor on the **curated container**, not the subscription. The API receives Storage Blob Data Reader on that same container. Shared storage keys and anonymous blob access are disabled. GitHub authenticates deployments through OIDC, avoiding a stored client secret.

The initial storage endpoint is internet-routable but requires Entra authorization. Private endpoints/VNet integration are not implemented. The API is public and serves only licensed public measurements; it has no public ingestion or mutation route. Cost exposure from public requests remains possible even with replica caps.

## ADR-003: Container Apps consumption

The application can scale from zero to two replicas; the processing job runs manually by default. No AKS cluster is needed for this bounded workload. A public GHCR image, preferably pinned by digest, avoids an always-on private registry. Image publication is a separate explicit workflow. Cold starts and extension installation affect initial latency and require cloud measurement.

## ADR-004: Atomic publication and failure recovery

A failed quality check never replaces the local release pointer. Cloud writers use a renewable Blob lease. They upload immutable database and manifest objects before changing the remote pointer. A checksum detects a corrupted download. Old releases support rollback.

A cloud publication failure may leave an unreferenced immutable object; it does not make that object the active release. Retention cleanup is intentionally manual until a recovery window and retention budget are agreed. Local concurrent writers are serialized using a filesystem lock. Cloud lease behavior has unit-test coverage with fakes and requires a live concurrency exercise before a production claim.

## ADR-005: Honest data interpretation

Weighted regional speeds describe tests. Matched-tile changes control for changing tile coverage but cannot control for changing test participants or devices. No confidence interval is fabricated from aggregated source means. Absolute review thresholds are an exploratory user-facing rule and are not a service-level agreement.

## Roadmap beyond initial scope

- Azure SQL backend with measured justification and query benchmarks.
- VNet/private endpoints when network isolation is required.
- Queue-based arrivals, dead-letter processing and event deduplication when source arrival becomes event-driven.
- Load testing, cost-per-refresh and recovery-time evidence after deployment.
- Additional periods selected and validated explicitly; no automatic inference of latest availability.
