# Runbook

## Local

Use the README commands. `seed_operations.py` creates disclosed synthetic examples and processes twelve valid snapshots plus one rejected file. Restarting the local API recovers queued/processing runs through its local loop. Data lives under ignored `data/operations/`.

## Azure deployment

Use Azure for Students in the dedicated project resource group. Keep its spending limit enabled. Resource names may retain `telecom` where an existing registry/group is reused; those are historical names, not a second running application.

1. Run local tests and compile Bicep.
2. Run **Build Azure image** on main. Its federated identity has AcrPush only on the project ACR. Read the immutable digest from its `azure-image` artifact or ACR.
3. Deploy `infra/main.bicep` using the owner's authenticated Azure CLI:

```bash
az deployment group what-if --resource-group rg-azure-telecom-portfolio \
  --template-file infra/main.bicep --parameters image=REGISTRY.azurecr.io/operations@sha256:DIGEST
az deployment group create --resource-group rg-azure-telecom-portfolio \
  --template-file infra/main.bicep --parameters image=REGISTRY.azurecr.io/operations@sha256:DIGEST
```

CLI commands shown assume `az` is installed and logged into the correct student subscription. Do not place tokens or connection strings in the repository.

4. Verify `/health/ready` and `/api/catalog` (`runtime=azure`). Submit the bundled samples through the API. The queue starts a processing job; query its execution status and `/api/runs/ID` until terminal.
5. Test an invalid CSV and a duplicate. Check that invalid input leaves inventory unchanged and duplicate upload returns the same ID. Confirm logs and scoped access in Azure.

## Failed processing

Inspect Container Apps Job executions and Log Analytics. Do not blindly resubmit a rejected CSV: correct it first. After fixing a technical error, run `retry(store, run_id)` using an authorized operator identity, or resubmit a still-pending file. Public manual retry is disabled. The worker moves persistent technical failures to the dedicated failed queue after five deliveries.

## Rollback

Redeploy the previous verified image digest using the same Bicep. Input files and results remain in Blob Storage. Do not delete the storage account during application rollback. An older stock date cannot supersede a newer date; publish a corrected same-date snapshot to correct business data.

## Static copy

`python scripts/export_operations.py` exports the current local data by default. The snapshot mode visibly disables uploads. To publish cloud evidence, export the verified API state with the catalog and the real app URL; never relabel local runs as Azure. Run **Publish free demo** after committing `dist/`.

## Shutdown

Review actual resource costs in the portal. To stop processing, remove the event trigger or stop/delete the project job after confirming pending messages. Delete the dedicated portfolio resource group only when the owner wants to retire the deployment and after exporting evidence; this deletes storage, logs and the registry. GitHub Pages remains independent. Nothing here enables an unattended cleanup schedule.
