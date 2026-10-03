# Verification — 3 October 2026

## Operations implementation

- 21 Python tests passed: three CSV formats, file rejection preserving inventory, content-based duplicate handling, warehouse isolation, corrected snapshot replacement, out-of-order protection, removal of absent SKUs, invalid quantities/dates/precision/encoding, writer exclusion, transient failure recovery, API limits and fixture-only Azure upload policy.
- JavaScript checks passed for all five warehouse selections (all + four individual), totals, scoped CSV rows and HTML escaping.
- Ruff passed. Main Bicep compiled with v0.47.16 without diagnostics.
- Synthetic data: four warehouses, three suppliers, twelve products, twelve valid source snapshots and one rejected example. Fourteen downloadable fixtures include a correction.

## Pending live acceptance

Current operations Docker build, cloud deployment, event-triggered execution, provider IAM/logs and browser walkthrough are in progress. Successful checks from the previous telecom edition are not counted as operations checks.

Students subscription is Enabled. The previous GitHub login failure was traced to a mismatched OIDC subject and the existing scoped credential was updated to the exact subject presented by GitHub. A subsequent successful login is still required before claiming the fix verified.
