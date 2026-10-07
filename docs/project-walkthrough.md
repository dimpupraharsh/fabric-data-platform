# Source to Reporting: A Simple Walkthrough

## 1. Two Different Sources

PostgreSQL contains customers, products, sales lines, order headers and status
events. AWS S3 contains geography, delivery zones and warehouse coverage.
PostgreSQL says what happened; S3 supplies geography and fulfilment context.
Private CRM/ERP CSVs seed staging before operational tables. Source simulation
is an owned-project tool, not a claim that analytics engineers normally write
to application production databases.

## 2. Raw Ingestion Into Bronze

Metadata tells the parent which connection, object, destination and loading
strategy to use. PostgreSQL facts/events use `dwh_load_ts` incremental boundaries;
customer/product snapshots and S3 files follow configured snapshot paths.
The gateway lets Fabric reach private PostgreSQL; it does not execute PySpark.
Bronze preserves raw attributes and lineage rather than silently fixing defects.

## 3. Historical, Validated Data in Silver

Fabric notebooks standardize attributes, detect defects, deduplicate source
keys and conform dimensions/facts. SCD Type 2 preserves dimension versions.
Facts use business dates to find the appropriate historical version.

Example: a customer changes region in March. A January order arriving in April
belongs to the January customer version, not today's version. Stable entity
keys prevent those historical versions being counted as different customers.
Current open arrival/reference findings still limit universal safety claims.

## 4. Audited Gold Publication

Sales retain line-item grain. Orders have a separate one-row-per-order fact,
so a three-line order is counted once. SQL builds candidates and validates key
uniqueness, grain, eligibility and reconciliation before transactional publication.
Marts support sales, customer, product, geography, lifecycle, delivery and payment
status analysis. Booked sales is not net revenue or profit.

## 5. Semantic Serving

The Direct Lake model exposes Gold facts/dimensions with 18 DAX measures.
A health check compares publication audit and model sales, line, order and SLA
counts. Reports can consume this model; no deployed report or adoption is claimed.

## 6. Code Delivery Is Not Data Processing

To change a rule: edit its definition on a branch, add tests, review the PR,
validate in Dev/Test and promote an approved artifact. Fabric then runs the
released code on authorized processing runs. Terraform provisions infrastructure;
GitHub stores/releases definitions; Fabric processes data. None alone moves
existing business data into the replacement Production workspace.
