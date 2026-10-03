# Deployment and operations runbook

## Before deployment

Use a personally authorized subscription or an explicitly approved institutional sandbox. Being able to sign in to a university tenant is not sufficient authorization to use departmental resources. Confirm subscription, region availability, spending protection and a monthly consumption budget before provisioning. Keep identifiers and credentials out of public evidence.

The deployment identity needs resource deployment permissions in a dedicated resource group and permission to assign the two scoped data roles. Runtime identities have only container-scoped reader/writer permissions. Configure GitHub's `azure-portfolio` environment with required reviewers and federated OIDC trust restricted to that environment/repository. Put client, tenant, subscription and resource-group identifiers in environment variables; no client secret is needed.

## Build and bootstrap

An alternative to a public GHCR image is an Azure Container Registry in the dedicated project resource group. Build there with `az acr build`, keep admin credentials disabled, pin the resulting image digest and pass `registryName` to `infra/main.bicep`. The template grants each runtime identity AcrPull only on that registry. Registry/task usage must be included in cost checks. The registry is an external prerequisite, not created by the main template.

1. Run local tests and compile both Bicep files.
2. Run the `Build image` workflow after repository publication. Make that one image package public for credential-free pulls; scan it and use the returned immutable digest. Do not publish unrelated images or credentials.
3. Create a dedicated project resource group in the approved subscription. Check resource-provider registration and regional quotas.
4. Deploy `infra/budget.bicep` using the approved amount and notification email. A budget alert is not a hard spending cap; it may lag consumption.
5. Run the manual `Deploy Azure` workflow. It first deploys storage, identities and the job with `deployApi=false`, starts and waits for ingestion, then deploys the API with `deployApi=true`. This avoids a readiness deadlock before the first snapshot exists.
6. Verify `/health/ready`, metadata and a filtered query against the cloud endpoint. Inspect the actual revision image digest, runtime identity and Blob role assignments. Confirm that the API identity cannot upload or delete blobs.
7. Record cloud evidence separately from local results. A successful Bicep compile or ARM provisioning does not prove successful ingestion or identity enforcement.

The initial workflow expects the default `telecom` prefix. When using another prefix, update the job name consistently. Scheduled execution is disabled. Enabling a schedule does not discover new quarters: update the explicit configuration after checking source availability.

## Required live acceptance checks

- Container image builds for linux/amd64 and runs as UID 10001.
- First cloud job succeeds with real sources; remote pointer and database checksum agree.
- Second run produces no extra records; concurrent job writers cannot publish simultaneously.
- Deliberately invalid input leaves the last valid remote pointer intact.
- API read identity can retrieve snapshots but is denied write/delete operations.
- Application Insights receives a real request trace; Log Analytics receives job completion/failure records.
- Cloud readiness and selected metrics agree with local source expectations.
- Cold/warm latency, one job's duration and actual Cost Management usage are recorded.

## Refresh and recovery

For a normal refresh, run the job manually and inspect its execution status. Local mode: `python -m telecom_cloud.pipeline`. Existing unchanged partitions skip SQL rewrites, but source Parquet is still re-read to detect revisions.

If validation fails, inspect the structured `pipeline_failed` log and the exception. Fix the source/configuration issue, then retry. Never suppress the validation to force publication.

For cloud rollback, stop new job starts, acquire the writer lease, select a previously successful immutable release and verify its database SHA-256. Replace `current.json` with that release's manifest, then release the lease. The API refreshes within its 60-second cache window. Verify metrics after rollback. Do not delete the last good release.

If a writer is interrupted, its renewable 60-second lease expires. A second run can then acquire it. If the app cannot download a release, it returns a 503 rather than inventing values or silently serving a different dataset.

## Cost controls and teardown

Keep minReplicas=0, maxReplicas=2, manual job triggers and bounded source selections. Log ingestion has a configured daily cap; caps and budget notifications can have latency and are not a complete spending guarantee. Keep 30-day log retention. Avoid paid private networking or additional databases until justified.

After an authorized demo period, retain code, the static snapshot and verification records. Preview the exact resource group contents before deleting the dedicated project group. Group deletion is destructive and must be a deliberate user action; this repository does not run it automatically.

## Troubleshooting

- **No data / 503:** check job execution, remote `current.json`, identity role propagation and storage access.
- **Image pull failure:** verify the image package is public and the digest exists for linux/amd64.
- **403 on storage:** inspect the correct user-assigned identity's client ID and container-scoped role. Do not enable account keys as a workaround.
- **Source/extension access failure:** verify public HTTPS access to Ookla and DuckDB extension hosting. Download failure must not publish partial data.
- **Azure Policy/region rejection:** select an allowed region or request an authorized sandbox; do not weaken institutional policy.
