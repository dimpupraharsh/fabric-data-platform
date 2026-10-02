# Production Readiness Blockers

## Decision

Do not enable Production release flags yet. Connector tests and the isolated
business fixture are necessary evidence, not proof that all production failure
and concurrency paths are correct. The following open PR findings were checked
against the current definitions on 2026-10-02. They remain unresolved.

## Correctness Findings

| Finding | Current risk | Required remediation and test |
| --- | --- | --- |
| Bronze failure propagation | Successful cleanup Scripts can handle an upstream failed activity, leaving a successful child outcome | Add explicit failure propagation after failure logging; fault-inject counting, Copy, manifest and commit branches and require parent failure |
| Silver failure propagation | Successful failure logging can allow the daily parent's Gold success dependency | Re-raise each failed notebook/reconciliation path after releasing leases; require no Gold invocation and unchanged transform checkpoint |
| Independent S3 snapshots | `nb_silver_dimensions` requires exact equality of independently generated ingestion timestamps | Define coherent reference-version/as-of semantics, including reference-only changes and initial history assumptions; test staggered file arrivals and non-null zone/geography enrichment |
| Changed DQ classification | `nb_silver_sales` independently merges accepted facts and rejects without removing a superseded classification | Reconcile both targets for every processed key, retaining appropriate audit history; test reject-to-accept, accept-to-reject, replay and interrupted recovery |
| Silver arrival boundary | The lower bound uses last completion time; rows arriving during notebook execution can fall behind the next checkpoint | Freeze a committed input set/upper boundary at start and advance only that boundary after success; test overlapping Bronze commits, including batches whose ingest timestamp predates their actual commit |

Relevant definitions:

- `workspace/pl_bronze_pg_watermark.DataPipeline/pipeline-content.json`
- `workspace/pl_silver_orchestrator.DataPipeline/pipeline-content.json`
- `workspace/nb_silver_dimensions.Notebook/notebook-content.py`
- `workspace/nb_silver_sales.Notebook/notebook-content.py`
- `control.sp_start_silver_run` and `control.sp_finish_silver_run`

The current business fixture uses matching reference-arrival timestamps, tests
an unchanged reject classification, and executes transformations sequentially.
It therefore cannot close these findings. Do not resolve review threads merely
because that fixture or the deployment workflow passes. Expand acceptance tests
alongside the remediation and verify actual pipeline failure outcomes.

## Deployment and Governance

Existing Production is a template-app workspace. Native deployment-pipeline
assignment returns `ALM_InvalidRequest_TemplateAppWorkspacesNotSupported`.
Preserve it while using the gated GitHub release design, or approve a separately
planned migration to a normal workspace. No migration/deletion is authorized by
this status document. Dev and Test remain assigned to the native pipeline.

Physical manifest/recovery and semantic serving still require acceptance.
The scoped AWS OIDC infrastructure role is not yet authorized/verified.
Production SQL adoption, release flags and temporary branch permission cleanup
remain approval/governance gates. A single-owner portfolio and trial capacity
must not be described as independent enterprise approvals or paid-production SLA.

## Safe Implementation Order

1. Fix failure propagation and fault-inject the actual child/parent paths in Test.
2. Establish committed-input boundary semantics before changing checkpoints.
3. Fix classification transitions with recoverable idempotent target writes.
4. Fix reference enrichment history and test staggered S3 snapshots.
5. Run expanded business, manifest/replay and semantic acceptance under appropriate identities.
6. Resolve only verified review findings and merge through protected checks.
7. Decide Production workspace strategy; then approve SQL adoption/promotion.

Never reset Production checkpoints or replace its business data to make a test pass.
