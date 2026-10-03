# Learning and interview guide

The strongest portfolio evidence is code you can explain and operate. Work through these exercises before claiming independent proficiency.

1. **Follow one row.** Pick a quadkey in the UI. Find its source URL, normalized record, partition digest, SQL row and returned API object. Explain the difference between kbps and Mbps and why test weights matter.
2. **Explain a release.** Run ingestion twice. Show that unchanged records are not duplicated. Change a synthetic test fixture to a negative speed and demonstrate that the old release remains available.
3. **Understand cloud identity.** Explain Entra ID, the managed identity client ID and container-scoped RBAC. Explain why the API can read while the pipeline can publish. After deployment, verify an actual denied write.
4. **Read the infrastructure.** Locate each Bicep resource and draw its dependency. Explain why there is no Azure SQL server or AKS cluster in this version. Identify what would justify adding them.
5. **Trace a deployment.** Explain GitHub OIDC, the protected environment, the immutable image digest and the bootstrap/data/API sequence. Distinguish a compiled template from a deployed application.
6. **Recover a failure.** Explain the local file lock, renewable cloud lease and atomic pointer. Demonstrate rollback only within your dedicated project environment.
7. **Measure an operation.** Compare a local benchmark with cloud cold-start and warm-request timings. Explain what the local TestClient benchmark does not measure.
8. **Defend an analysis.** Why is a regional speed increase not proof of an infrastructure upgrade? Why is adding distinct devices across tiles invalid? Why do matched-tile comparisons still have sample bias?
9. **Control costs.** Explain how active replica time, logs and retention drive cost. Show actual usage after deployment. Explain why a budget is an alert, not a hard limit.

## Three-minute demo

- 0:00–0:30: state the connectivity question and show one region/quarter.
- 0:30–1:00: change the sample threshold and explain changed coverage.
- 1:00–1:30: show matched-tile comparison and a source partition.
- 1:30–2:15: show Bicep, identity separation and the data release workflow.
- 2:15–2:45: show a tested failure and recovery, with real evidence.
- 2:45–3:00: state verified scope and one justified next improvement.
