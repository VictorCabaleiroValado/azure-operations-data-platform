# Data methodology

Source: Ookla Open Data, https://github.com/teamookla/ookla-open-data. Source metadata and URL patterns were checked against that repository. Initial data was read from the public S3 HTTPS Parquet objects on 3 October 2026. The source manifest records URLs, source periods, row counts and normalized logical SHA-256 digests. Digests identify selected records, not the full remote object bytes.

## Population and grain

One record = region + quarter + connection type + zoom-16 quadkey. Selection includes a tile if its centroid lies within an inclusive bounding rectangle. Regions are study areas, not administrative boundaries. Each tile can occur in multiple quarters and connection types: 7,403 observations do not mean 7,403 unique geographic tiles.

Fields: longitude, latitude, average download/upload in kbps, average latency in ms, tests and distinct devices within that source tile-period. The base source records with valid positive counts are retained. A minimum-test UI filter changes the eligible population consistently in the map, metrics, trend, review list and CSV export.

## Aggregation

Download Mbps = sum(tile mean download kbps × tile tests) / sum(tile tests) / 1,000.
Upload is analogous. Latency = sum(tile mean latency ms × tile tests) / sum(tile tests).
Source means are rounded, so reconstructed aggregates are approximate. Devices are never summed across tiles or periods. Tests are summed only within the explicitly selected population.

The trend independently applies the same threshold to each quarter. The matched-tile measure intersects eligible quadkeys for the selected and prior configured quarter, then averages each tile's speed difference with equal weights. It is distinct from a difference in test-weighted regional means. Neither establishes causation.

## Quality contract

Reject empty partitions, duplicate keys, invalid quadkeys, unexpected columns, non-finite or negative performance values, out-of-region centroids, non-positive or fractional counts, and devices exceeding tests. Publish only if the stored row count reconciles with all configured partitions. Missing data is displayed as missing, never zero speed.

## Limitations

Participants self-select tests. Repeated tests are not independent random samples. Device, access technology, provider, time of day and test conditions may change. Small test counts offer limited evidence; filtering them also changes coverage. No inference about all households, coverage, outage incidence, provider performance or causes of change is warranted. Historical data is not a live assessment of current connectivity.

## Licensing

Ookla data and redistributed derived datasets retain CC BY-NC-SA 4.0. The repository carries separate code and data licenses. Source attribution and transformation descriptions are visible in the application. No trademark permission, endorsement or affiliation is claimed.
