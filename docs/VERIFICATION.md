# Verification record — 3 October 2026

## Verified locally

- Public-source ingestion completed: 7,403 real observations, eight partitions, two study areas, two connection types, Q3–Q4 2024. Initial network ingestion elapsed 78.216 seconds on the author's Mac; this is not a cloud benchmark.
- 24 Python tests pass: idempotency, corrected-partition replacement, atomic failure recovery, removed-scope pruning, invalid values, duplicate/empty partitions, source scope validation, local writer lock, weighted units, API filters/injection rejection, real-source digest reconciliation and mocked cloud publication/checksum behavior.
- JavaScript static calculations agree with the SQL API across all 32 region/network/period/test-threshold combinations.
- Ruff passes for source, tests and scripts.
- Bicep v0.47.16 compiles both main infrastructure and budget templates without diagnostics. The main template also supports an optional private Azure Container Registry with identity-based image pulls. Compilation does not validate runtime permissions.
- All four GitHub workflow YAML files parse locally. Hosted workflow execution has not occurred.
- Browser review: local UI loads real metrics; connection and minimum-test filters update the view; a no-data selection displays missing values and zero evidence. At 390px viewport, document/body widths were both 390px (no page-level horizontal overflow). Desktop and mobile layouts were visually inspected.
- Local API benchmark: see `evidence/local-api-benchmark.json`. It is an in-process TestClient measurement, not a load test or network latency measurement.
- Static snapshot is generated from the same SQL records, with visible snapshot identification and source attribution.

## Remaining checks

- Docker build and container runtime: Docker is unavailable on the authoring machine. CI includes the build and liveness test, but it has not run remotely.
- Azure deployment, OIDC, actual RBAC denial, cloud lease concurrency, application telemetry and cost measurement require an approved subscription and spending decision.
- Browser CSV download completion could not be captured by the in-app browser's download event. CSV generation/filter scope has source-level coverage; recheck an actual downloaded file in Edge before publication.
- Public GitHub repository, image package, portfolio URL and LinkedIn publication have not been created or changed.

## Account check

Azure for Students was activated and verified in Edge on 3 October 2026: Active/Enabled, Owner role, $100 of $100 credit remaining, expiry 3 October 2027, spendingLimit On. West US 2 is an allowed deployment region. A dedicated project resource group and $5/month cost alert were provisioned successfully. Application deployment is still in progress. The two departmental subscriptions are outside this project's deployment scope.

## Known limits

Initial sources are historical. Geographic visuals are a coordinate-based tile-centroid plot, not a street map. SQLite is the implemented query engine; Azure SQL/private networking/event-driven queues are not implemented. Cloud-specific tests using fakes verify client logic, not provider behavior. The test stack emits an upstream httpx deprecation warning; tests pass.
