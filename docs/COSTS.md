# Student deployment and cost control

Selected plan: Azure for Students, with its credit spending limit kept on. No conversion to pay-as-you-go and no personal charges are authorized. A $5/month budget alert exists in the dedicated project resource group; it is an alert, not an enforced cap.

Container Apps and the processing job use Consumption, 0.25 vCPU / 0.5 GiB, minimum zero and maximum one replica/execution. Queue polling is every 60 seconds. Logs retain 30 days with a 0.1 GB/day workspace cap. Blob versioning and seven-day soft delete aid recovery but consume storage.

Potential charges include compute execution, ACR, storage capacity and operations, logs and network egress. Scale-to-zero does not make the registry or storage free. Actual eligibility for free amounts is account-specific; consult the billing view. The current registry is reused so no second registry is needed.

The public cloud demo accepts only fourteen known small fixture files. Identical terminal uploads do not enqueue again. This bounds demonstration data growth but is not a general enterprise rate limiter. The free static copy does not run Azure jobs.

Record observed costs and dates in VERIFICATION.md only after reading the provider. Never present the initial $100 credit as a guaranteed current balance after deployment.

Sources: https://azure.microsoft.com/en-us/free/students/ and the Azure portal's Cost Management / Education credit views.
