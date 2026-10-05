# Runbook

## Local

Use the README commands. `seed_operations.py` creates disclosed synthetic examples and processes twelve valid snapshots plus one rejected file. Restarting the local API recovers queued/processing runs through its local loop. Data lives under ignored `data/operations/`.

## Azure deployment

Use Azure for Students in the dedicated project resource group. Keep its spending limit enabled. Resource names may retain `telecom` where an existing registry/group is reused; those are historical names, not a second running application.

1. Run local tests and compile Bicep.
2. Run **Build Azure image** on main. Its federated identity has AcrPush only on the project ACR. Read the immutable digest from its `azure-image` artifact or ACR.
3. The environment explicitly uses `environmentMode: WorkloadProfiles`. Express environments cannot run Container Apps Jobs. The 2026-07-01 resource API exposes this setting; older Bicep type catalogs can emit BCP081, so ARM deployment validation is also required. Deploy `infra/main.bicep` using the owner's authenticated Azure CLI:

```bash
az deployment group what-if --resource-group rg-azure-telecom-portfolio \
  --template-file infra/main.bicep --parameters image=REGISTRY.azurecr.io/operations@sha256:DIGEST
az deployment group create --resource-group rg-azure-telecom-portfolio \
  --template-file infra/main.bicep --parameters image=REGISTRY.azurecr.io/operations@sha256:DIGEST
```

CLI commands shown assume `az` is installed and logged into the correct student subscription. Do not place tokens or connection strings in the repository.

4. Verify `/health/ready` and `/api/catalog` (`runtime=azure`). Submit the bundled samples through the API. The queue starts a processing job; query its execution status and `/api/runs/ID` until terminal.
5. Run `python scripts/verify_cloud.py https://YOUR-APP.azurecontainerapps.io` to perform the bounded acceptance sequence and export its evidence. It uploads the bundled fictional fixtures, waits for automatic jobs and verifies rejection, correction and duplicate behavior. Test an invalid CSV and a duplicate. Check that invalid input leaves inventory unchanged and duplicate upload returns the same ID. Confirm logs and scoped access in Azure.

## Failed processing

Inspect Container Apps Job executions and Log Analytics. Do not blindly resubmit a rejected CSV: correct it first. After fixing a technical error, run `retry(store, run_id)` using an authorized operator identity, or resubmit a still-pending file. Public manual retry is disabled. The worker moves persistent technical failures to the dedicated failed queue after five deliveries.

## Rollback

Redeploy the previous verified image digest using the same Bicep. Input files and results remain in Blob Storage. Do not delete the storage account during application rollback. An older stock date cannot supersede a newer date; publish a corrected same-date snapshot to correct business data.

## Static copy

`python scripts/export_operations.py` exports the current local data by default. The snapshot mode visibly disables uploads. To publish cloud evidence, run `python scripts/export_operations.py --cloud-url https://YOUR-APP.azurecontainerapps.io`; never relabel local runs as Azure. Run **Publish free demo** after committing `dist/`.

## Shutdown

Review actual resource costs in the portal. To stop processing, remove the event trigger or stop/delete the project job after confirming pending messages. Delete the dedicated portfolio resource group only when the owner wants to retire the deployment and after exporting evidence; this deletes storage, logs and the registry. GitHub Pages remains independent. Nothing here enables an unattended cleanup schedule.

## Azure Monitor summary

The portal's `/api/observability` endpoint runs one fixed query over the existing `ContainerAppConsoleLogs_CL` table. It returns only aggregate completed/rejected file counts, technical failure attempts, mean worker duration and the latest matching timestamp over seven days. The query is defined in `src/operations_cloud/monitor.py`. It includes existing `file_processed` log events and the worker's existing technical-failure message; no historical log migration is required. Completed events are deduplicated by run ID. Technical failures count attempts and may include files that later succeeded. Queue waiting time is not measured.

Set `OPERATIONS_LOG_WORKSPACE_ID` to the existing workspace customer ID. The portal's managed identity needs **Log Analytics Reader** scoped only to `operations-logs`; this assignment is included in Bicep. Authentication uses managed identity, with no storage keys or workspace tokens exposed in the browser. The public endpoint accepts no custom queries and exposes no raw logs. Results, including temporary failures, are cached for five minutes to bound requests. Logs may arrive late; absent access or partial responses show unavailable, never false zero metrics.

Monitoring is global across warehouses because historical worker events lack warehouse fields. New events also include warehouse and supplier for operator investigation. The static export preserves the last successful observation and its query timestamp; it never claims live monitoring. Local mode leaves Azure Monitor disconnected. No additional Azure service is provisioned, although log querying remains subject to the existing workspace's pricing and limits. See Microsoft's [Logs API authentication documentation](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/api/access-api).
