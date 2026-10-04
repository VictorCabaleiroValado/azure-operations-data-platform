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
