# Cost planning — checked 3 October 2026

These are planning ranges, not observed invoices or a formal Azure quote. Region, offer eligibility, shared free quotas, data transfer and logging affect actual cost. No Azure resources were provisioned during local development.

| Scenario | Planning range, USD/month | Assumptions |
|---|---:|---|
| Static portfolio + occasional cloud demos | 0–5 | Small snapshots, manual jobs, cloud removed/idle between demos |
| Low-traffic public API | 1–10 | Scale-to-zero, few visits, modest logs, shared free quota available |
| Frequent development/testing | 5–20 | More refreshes, active replicas and diagnostics |

Victor selected Azure for Students plus a free public demo on 3 October 2026. Consumption covered by the student credit is authorized for this project; personal payments and a pay-as-you-go upgrade are not authorized. The initial planning target remains $5/month of credit consumption, pending confirmation of the activated offer and its spending protection. Budget notifications at 50%, 80% and a 100% forecast are defined in `infra/budget.bicep`; they do not stop charges automatically.

The free demo can be published from `dist` using the manual `Publish free demo` GitHub Actions workflow after repository publication and GitHub Pages configuration. It serves a dated data snapshot, independently of the live Azure API. Workflow preparation is not evidence of publication.

Azure Container Apps' published monthly free allowance is 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests per subscription. For illustration, a single 0.5 vCPU / 1 GiB replica active for 20 hours uses 36,000 vCPU-seconds and 72,000 GiB-seconds before jobs and other apps. Source downloading, startup, monitoring and storage also matter. Continuous load can exceed the allowance; minReplicas=0 does not guarantee zero cost.

Azure for Students advertises $100 credit usable within 12 months, with no credit card, subject to student eligibility. It is distinct from existing university departmental subscriptions even when the same email verifies student status. Confirm available products, quotas, expiry and spending-limit behavior during enrollment. Do not upgrade to pay-as-you-go implicitly.

Official sources:
- https://azure.microsoft.com/en-us/free/students/
- https://azure.microsoft.com/en-us/pricing/details/container-apps/
- https://azure.microsoft.com/en-us/pricing/details/monitor/
- https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets

Do not claim an actual cost-per-run until a cloud execution and delayed billing data have been reconciled.
