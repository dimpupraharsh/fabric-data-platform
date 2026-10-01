# Fabric Release Runbook

## Contract

PostgreSQL is transactional; S3 contains geography/fulfillment references. These
sources are not Terraform state storage. Workspaces, connector targets, SQL
schemas and checkpoints are separate per environment. Production is adopted in
place; publishing definitions never copies or replaces business data.

## Pull Requests

Use a feature branch and a pull request. The required `Validate Definitions`
check parses native Fabric metadata, pipeline JSON, Python notebooks and release
configuration; scans for credentials; runs unit tests; validates pinned Terraform
providers without accessing the backend. Fork PRs receive no cloud credentials.
Do not use `pull_request_target` to execute submitted code with deployment access.

## Bootstrap

1. Terraform creates/adopts workspaces and per-environment Entra OIDC identities.
2. Publish the two Lakehouse and two Warehouse shells per environment.
3. Apply catalog-derived additive migrations to Dev/Test only.
4. Rebind cloud/gateway connections. Do not reuse Production write destinations.
5. Bootstrap configuration only, with source/transform objects disabled and
   baseline checkpoints. Production bootstrap is prohibited.
6. Deploy semantic and application definitions; inspect the resolved bindings.
7. Run bounded integration, retry/replay, schema-drift and failure tests in Test.
8. Enable approved release flags through a reviewed PR, not a UI bypass.

## Promotion

Dispatch `Promote Fabric Release` from main. A single tested commit is archived,
hashed and uploaded. Dev and Test must pass before Production approval is offered.
The same artifact is verified before each stage. Deployment concurrency is
serialized and an in-flight release is not cancelled by another release.

Only additive reviewed migrations and definition publication are permitted.
SQL migrations have version/checksum ledger records and commit with their version
entry. Never edit an applied migration; add the next version instead. Production
schema adoption must be approved separately before enabling migrations there.

Deployment smoke checks prove item/schema accessibility, not business correctness.
Do not approve a production release based solely on item counts. Check connector
rebinding, fixture reconciliation, rerun idempotency, SCD2 history, late arrivals,
drift rejection, failure recovery, KPI audit and the semantic model connection.

## Rollback

Re-promote the previous known-good commit/artifact through the same gates.
Do not delete/recreate Warehouses or Lakehouses, reset checkpoints, or automatically
reverse schema changes. Schema rollback is a forward corrective migration. Keep
the existing Production schedule; Dev/Test schedule files are never published.

## Governance Limits

This is a single-owner portfolio repository. Production environment approval is
configured, but independent separation of duties requires another trusted reviewer.
Trial capacity does not provide paid-production capacity guarantees. Gateway
testing requires the Mac PostgreSQL container and Windows gateway VM online.
Long-lived source access keys previously shared in chat should be rotated before
real production use. They are not stored in this repository or GitHub secrets.
