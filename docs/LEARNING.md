# Understanding Azure Operations Data Platform

## The story

Imagine an electronics distributor with four warehouses: Centro, Leganés, Sanchinarro and Pedrezuela. Three suppliers send stock files, each with different column names. Your system receives those files, checks them and prepares a common inventory view.

The company and data are fictional. The code, checks and deployed services must still be verified with real evidence.

## The five components

1. **Portal / API:** the web application where you select a warehouse and upload a file. An API receives the request and returns results.
2. **Blob Storage:** Azure storage for originals, statuses and results. Think of private files organized by identifier.
3. **Queue Storage:** the list of pending jobs. A message carries the file identifier, not its entire contents.
4. **Container Apps Job:** the Python program that starts to check a file and exits when it finishes.
5. **Azure Monitor:** logs that show what the program executed and why it failed.

A container packages the program and its dependencies. The same package serves the web application and processor with different startup commands, simplifying maintenance.

## What each status means

| Status | Meaning |
|---|---|
| Queued | The file is stored and awaiting processing |
| Processing | The worker has picked up the file |
| Completed | All rows are valid and the result is stored |
| Rejected | Data errors were found; previous inventory is preserved |
| Technical failure | Delivery attempts were exhausted; an operator investigates and retries |

A rejected file needs a correction. A technical failure may be resolved without changing the data, for example by restoring storage access.

## An example you can explain

Nexo reports eight laptops in the Centro warehouse inventory. The file declares eight available units; it is not a delivery to add every time it arrives. Uploading the same file twice still produces eight units. A corrected snapshot of eighteen units replaces the previous snapshot for the same supplier, warehouse and date. An older snapshot never supersedes a newer one.

Stock from different suppliers is assumed to represent independent lots. Sales, reservations and transfers are not implemented. Totals use each supplier's latest valid snapshot; dates may differ, and the application displays those dates.

## How to learn the workflow

1. Select each warehouse on the map and compare the filters with the selector at the top.
2. Download a sample, inspect its four columns and connect one row to a product.
3. Follow the file through `api.py`, `service.py` and `validation.py`.
4. Test a duplicate, an error and a correction; explain why the total should change or stay the same.
5. In Azure, identify storage, queue, portal and job. Check a real execution and its logs.
6. Read `infra/main.bicep` and connect each resource to a component you have used.
7. Review actual spending. An alert notifies you but does not stop consumption.

## Professional concepts, with examples

- **Idempotency:** repeating the same file does not duplicate stock.
- **Event-driven processing:** work starts when a message arrives in the queue.
- **Managed identity:** Azure recognizes the program and grants permissions without storing a password in the code.
- **Infrastructure as code:** Bicep describes resources so they can be recreated.
- **Observability:** logs explain what happened to a file.
- **CI:** GitHub runs tests before a version is considered valid.

## A three-minute demonstration

Select Pedrezuela and show its inventory. Switch to Centro, download the error sample, upload it and open the result. Show the correction, then upload it again to demonstrate that stock is not duplicated. Finish with an Azure job execution and a decision you can justify, such as separating the web application from processing.

The static copy supports navigation but not uploads. In Azure, samples pass through actual storage and a queue. Local mode supports custom files. Consult VERIFICATION.md before stating which components have been verified in Azure.

## Language and supplier contracts

The interface, product labels, messages and documentation use English. Warehouse place names retain their original spelling. Supplier CSV headers retain their source contracts, including Spanish columns, because those names are input data rather than interface labels. Preserving them keeps existing fixtures and content-based processing IDs compatible.
