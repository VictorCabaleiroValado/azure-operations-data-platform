# Verification — 3 October 2026 (America/Chicago)

## Code and local application

- 23 Python tests passed: three CSV formats; rejection preserving inventory; content-based duplicate handling; warehouse isolation; corrected snapshot replacement; out-of-order protection; removal of absent SKUs; quantities, dates, precision and encoding; writer exclusion; transient failure recovery; API limits; fixture-only Azure uploads; queue acknowledgement and failed delivery handling.
- JavaScript checks passed for all five warehouse selections (all + four), totals, scoped CSV rows and HTML escaping. Ruff passed.
- Local Edge walkthrough: map selection, CSV upload, duplicate, rejected-file error lines and correction all verified. At 390 px width there was no horizontal overflow. The downloaded Pedrezuela CSV, filtered to EL-101, contained exactly that one warehouse/product row.
- Synthetic data: four warehouses, three suppliers, twelve products, twelve valid source snapshots, one rejected example and one correction.

## Build and deployment

- GitHub Validate run [37163092434](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37163092434) succeeded for application commit `cc9ae4c`.
- Build Azure image run [37163092706](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37163092706) succeeded, including federated Azure login and registry push.
- Application image: `operations@sha256:38a4a994a8fc2e92118e53547edf14f90d1875abf292f900ca1ee708bc0a9db9`.
- An initial environment defaulted to Express and rejected Container Apps Jobs. The template now explicitly selects WorkloadProfiles with the 2026-07-01 API. Bicep 0.47.16 compiles it but emits BCP081 because its type catalog does not include that API. ARM acceptance is checked separately.

## Account and cost checks

Azure for Students is Enabled and its subscription spending limit was verified as `On` through ARM on 4 October UTC / 3 October Chicago. No pay-as-you-go conversion was performed. The dedicated resource group's $5 monthly budget is an alert, not a hard cap.

Cost Management's ActualCost query returned `NotFound` because this student subscription lacks a supported WebDirect/AIRS offer type. Therefore current accrued cost and remaining credit are **not verified** here. The initial $100 credit must not be presented as the current balance. Check the Education credit view for the current balance.

## Cloud acceptance

At `2026-10-04T00:02:04Z`, the live Azure API passed the complete acceptance sequence: twelve initial snapshots completed, one invalid file rejected with two row errors and unchanged inventory, one correction completed, and duplicate upload returned the original ID. Final state: **14 runs, 13 completed, 1 rejected, 48 inventory rows**. All records identify their runtime as Azure.

Three queue-triggered job executions succeeded without a manual job start: `operations-processor-wtmrn`, `operations-processor-psvh6`, `operations-processor-mb5rv`. Console logs showed `file_processed` events with run IDs, statuses and durations. The deployed portal was checked in Edge: Azure connection badge, four locations and Pedrezuela selection (549 units, 12 references, EUR 117,786 at supplier cost).

- [Acceptance evidence](../evidence/cloud-public.json)
- [Provider execution statuses](../evidence/azure-executions.json)
- Storage: shared keys and anonymous blobs disabled; TLS 1.2 minimum. An anonymous request for an existing original blob was blocked with HTTP 409. An unapproved public upload was rejected with HTTP 403.
- Role assignments were read back from Azure: per-container Blob Data Contributor, queue-specific sender/contributor roles, registry-only AcrPull and registry-only build AcrPush.
- The failed Express application and environment were removed; durable storage and the working Standard environment remain.
- Azure Monitor / Log Analytics ingestion was independently verified: a KQL query returned twelve `file_processed` events for the first batch. [Query result](../evidence/azure-monitor.json). Later events may appear after the normal ingestion delay.

The static demo now contains a snapshot exported from the Azure API and a link to the live portal. It remains explicitly read-only. Data represents a fictional inventory snapshot, not real business activity.

## English edition — 5 October 2026 (America/Chicago)

The local portal, product/supplier display labels, API and validation messages, sample descriptions, learning guide and professional drafts now use English. The read-only copies in `dist/` and the project's `MAIN/` folder, plus the existing inventory export's display values, were updated. Formatting uses `en-GB` and keeps EUR. Place names, supplier input headers and processing IDs remain compatible with the existing data contract.

Existing stored results are read using current catalog labels before SQL aggregation. Legacy error messages are translated for API presentation; the original stored evidence is not migrated or rewritten. The static snapshot keeps its original Azure run IDs, timestamps, quantities and runtime provenance. Historical provider evidence under `evidence/` remains verbatim.

Verification performed for this edition:

- 25 Python tests passed, including two new checks for legacy inventory labels and errors without rewriting stored evidence. Ruff and JavaScript syntax checks passed.
- JavaScript checks passed for all five warehouse filters, integer totals, CSV row scope and HTML escaping.
- A temporary headless Edge test checked both local static copies: all five tabs, English labels, Pedrezuela's 549 units, English laptop search, rejected-run error details and disabled static uploads. No JavaScript page errors or horizontal overflow at 390 px were observed. Desktop layout was also visually inspected. External basemap tiles and 3D readiness were not confirmed during this local check.
- `git fetch origin` succeeded. The local baseline and `origin/main` both point to `e15048c`; translation changes remain uncommitted local work.

These checks establish local readiness only. This English edition has not been pushed to GitHub, published to GitHub Pages or deployed to Azure. Next publication steps are to commit/push the reviewed changes, publish `dist/`, build an immutable Azure image, update the portal and worker to that image, and verify the live English interface and existing processing behavior. Victor authorized publication to GitHub Pages and Azure on 5 October 2026; deployment verification follows below once completed.

### Published English release

Victor authorized publication and explicitly authorized reading the synthetic live inventory for verification.

- Application commit: `da453abf04753afae6e268b8664afe8c83de864c`.
- [Validate](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37346677159), [Build Azure image](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37346746825) and [Publish free demo](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37346752251) all completed successfully for that commit.
- Portal and processing job both use `telecomvc53728.azurecr.io/operations@sha256:51b822dea5ddb0567e0f7b807e8f031333032180108cd9a24185d0bb2c99090f`.
- Azure revision `operations-web--0000005` is Healthy and Provisioned; it is the only active revision and receives 100% of traffic. The processing job update succeeded. `/health/ready` confirms Azure storage is ready.
- Published HTML and JavaScript bytes match the approved English sources in both Azure and Pages. The live Azure catalog, inventory labels and historical rejected-run details return English.
- Live numeric inventory and run-ID hashes match the preserved static cloud snapshot: 14 runs, 48 inventory rows, 2,417 units and EUR 358,052 at supplier cost. No complete live inventory payload was persisted during verification.
- A read-only headless Edge walkthrough of both published applications verified five tabs, English labels, Pedrezuela's 549 units, English product search, historical errors, appropriate upload availability and no horizontal overflow at 390 px. No JavaScript page errors were observed.

No new live uploads or worker executions were triggered for this language release. The duplicate/rejection/correction behavior passed local and GitHub CI tests; the earlier cloud execution evidence remains historical. External map tile rendering and 3D readiness were not reverified in this release. No personal payments or account-plan changes were made.
