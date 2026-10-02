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

## Native Deployment Pipeline and Runtime Gates

The native `fabric retail intelligence platform` pipeline has correctly assigned
Dev/Test workspaces. Existing retail Production is a template-app workspace;
assignment fails with `ALM_InvalidRequest_TemplateAppWorkspacesNotSupported`.
Do not deploy to its empty Production stage, substitute the unrelated workspace
named `Production`, or recreate the existing retail workspace. GitHub remains
the single release authority; native stage comparisons do not authorize UI
deployments. Direct Lake models need explicit target datasource rebinding.

Dev/Test have separate SQL workspace-identity and Lakehouse OAuth connectors.
Gateway-backed copies require `allowConnectionUsageInGateway=true` on the
Lakehouse sink. Bootstrap now preserves this setting without changing Production.
The Oct 2 Test probe initially failed with gateway error 2015, but run
`e24bd8ca-fdc4-47ef-9474-37ec16e708d6` passed after the source container and
Windows VM were started. All four S3 checks, SQL and one-row PostgreSQL copy
succeeded without ingestion checkpoint updates. Keep the gateway VM and source
online. Inspect DNS, TLS/outbound 443 and gateway diagnostics if this recurs;
never weaken TLS or firewall protections blindly. Workflow runners are pinned
to Ubuntu 24.04 to match the SQL-driver package source.

`test_control_contracts.py --environment test` passed nine metadata-only tests
for leases, failed-run checkpoint safety, count/manifest guards, replay and schema
drift. Its dedicated fixture is inactive after completion. These tests do not
copy business data or prove a physical manifest was written.
`test_connectivity.py --environment test` performs a separate bounded runtime
probe; it must pass before a release proceeds. Test additionally runs the isolated
Silver/Gold business fixture described in [business acceptance](business-acceptance-runbook.md).
This gate requires the notebook's twelve assertion results and Gold reconciliation,
not only a successful job status. Evidence is uploaded as a GitHub artifact.
Physical manifest recovery, complete orchestration and semantic serving remain
further Production gates. Production release flags stay false.
Open pipeline failure, snapshot alignment, DQ-transition and checkpoint findings
are documented in [Production blockers](production-readiness-blockers.md).
A passing fixture does not close those untested cases or authorize promotion.

On 2026-10-02, GitHub run
[36954704106](https://github.com/dimpupraharsh/fabric-data-platform/actions/runs/36954704106)
passed the hardened Dev -> Test release at commit
`b2b88d36f8b6eb8a94053c1e6a1dc3821320e01d`. Both CI identities completed
migrations, definition publication, binding/schema audits, all nine metadata
control-contract checks and the bounded connector probe. Dev probe job:
`83f29577-696f-4c8e-b0be-a9036382ba52`; Test probe job:
`69d5e005-3284-4a7d-b115-80afa80984a6`. Each probe expected one synthetic row,
checked four S3 files and performed zero ingestion checkpoint updates. The later
runner pin and metadata inventory update do not constitute a Production release.

Subsequent releases `36958405291` and `36959708090` passed under GitHub OIDC.
The latter published the eleven explicit failure-propagation activities at
`6066b04a67fc1e01c7f2f219b9e3d42bac3ac6d1`, tested successful/failed cleanup,
required failed child/parent outcomes with no downstream Gold execution, and
passed the twelve Silver fixture checks and ten Gold SQL stages. Evidence is
retained in its `business-acceptance-6066b04a67fc1e01c7f2f219b9e3d42bac3ac6d1`
artifact. An independent delegated-operator semantic check passed separately.
Three data-correctness review findings remain unresolved; Production is unchanged.

## Rollback Procedure

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
