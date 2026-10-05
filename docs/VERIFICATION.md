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
- `git fetch origin` succeeded. The local baseline and `origin/main` both point to `e15048c`; translation changes were still uncommitted at that local checkpoint.

Those initial checks established local readiness only. Victor then authorized publication to GitHub Pages and Azure on 5 October 2026; the completed deployment is recorded below.

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

### Follow-up functional audit — 5 October 2026

A full follow-up audit found and fixed one presentation defect: the upload form's intrinsic grid sizing caused horizontal overflow at 320 px. Form and label grids now use a zero minimum column width, preserving usable controls within the available width. The stylesheet cache version and both local static copies were updated. Earlier local-only publication wording above was clarified as historical.

Checks completed:

- 25 Python tests, Ruff, JavaScript filter/CSV checks and dependency compatibility (`pip check`) passed. GitHub Validate for `8c23644` also succeeded, including the Docker build and container health check.
- A fresh local application with isolated temporary storage processed all three supplier formats across four warehouses through the browser. Accepted upload, identical duplicate, invalid-file rejection with unchanged stock, and corrected snapshot replacement all passed. Final local state matched the expected 14 runs, 48 inventory rows, 2,417 units and EUR 358,052 at cost.
- 40 combinations of warehouse, text query and low-stock filtering matched the underlying records. The downloaded English CSV contained exactly the selected Pedrezuela/EL-101 row.
- All five tabs passed layout checks at 320, 390, 768 and 1,440 px after the fix, with no JavaScript page errors. The corrected narrow-screen upload form was visually inspected.
- Live OpenFreeMap vector loading, the 3D camera, warehouse selection and return to the full network passed on both Azure and Pages. Simulating an unavailable vector provider locally activated the raster fallback, disabled 3D and retained warehouse filters.
- All 30 files in `dist/` and `MAIN/` matched before the audit; updated HTML/CSS were synchronized again after the fix. All 14 input fixture files retain their original bytes. The live synthetic inventory and run-ID hashes still matched the approved snapshot.

Scope: live Azure verification is read-only. No new cloud upload or queue-triggered processing execution was performed. Local browser tests exercised real local processing, while cloud worker configuration and existing records were checked separately. A separate local wheel build could not run because the local environment lacks `setuptools`; the successful GitHub Docker build provides packaging verification. The test runner emits a non-failing upstream Starlette/httpx deprecation warning. These bounded functional checks do not establish production-scale load or availability guarantees.

The mobile fix is published from application commit `283d145247e58c27943f1069075a38f79a66b80d`. [Validate](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37349621519), [image build](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37349657045) and [Pages publication](https://github.com/VictorCabaleiroValado/azure-operations-data-platform/actions/runs/37349661769) succeeded. Portal and worker use digest `sha256:13823393fc95282458ce40ed093ea4a95100012d3c426376fa5b76d8e78275d3`; Azure revision `operations-web--0000006` is ready with 100% of traffic. Published HTML/CSS exactly match the local sources. The final read-only browser check passed all five tabs and widths 320/390/768/1440 on both public URLs, including English search, historical error details and correct upload availability, with no JavaScript page errors.

## Functional improvements — 2026-10-05

Implemented snapshot comparisons, historical incident summaries, warehouse/category charts and a fixed aggregate Azure Monitor endpoint. Local validation: 32 Python tests, Ruff, JavaScript syntax and five-scope chart/CSV reconciliation. Browser checks cover a real local correction (+10 units / EUR 6,490 at cost), incident row details, disconnected monitoring, five warehouse scopes and all five views at 320/390/768/1440 px. Comparison details fetch their current baseline with the run, avoiding stale state immediately after processing.

Bicep compilation succeeds with the pre-existing BCP081 warning for the managed environment API. Actual Monitor permissions, query compatibility and the new Azure revision require authenticated deployment and live verification; they are not established by unit tests. The temporary Azure session from the earlier release was no longer present. A new owner sign-in was blocked by organizational Conditional Access (53003); no policy changes or alternate credentials were used. The static dataset preserves its previous cloud inventory and run records, with comparisons derived only from bundled fixtures whose content hashes match those recorded run IDs. No cloud inventory has been uploaded or changed for this release.

The owner-provided Azure portal session subsequently allowed an ephemeral Cloud Shell in Azure for Students. The exact committed Monitor query was run through the official Logs API on 2026-10-05 at approximately 20:33 UTC: 13 completed, 1 rejected, 0 technical failure attempts, average worker duration 146.41 ms, latest matching event 2026-10-04T00:01:40.7858658Z. This aggregate observation is included in the static demo with its timestamp. Managed-identity access and the new container revision still require separate verification.
