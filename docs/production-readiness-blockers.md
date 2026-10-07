# Production Readiness Blockers

## Decision

Do not enable Production release flags yet. Connector tests and the isolated
business fixture are necessary evidence, not proof that all production failure
and concurrency paths are correct. PR findings were checked against the current
definitions on 2026-10-02. Two failure-propagation findings were remediated and
their review threads resolved; three data-correctness findings remain open.

## Correctness Findings

The two failure-propagation definition findings now have fixes: eleven cleanup
branches end with an explicit Fail activity using a Completed dependency, which
also covers failure of logging itself. Isolated runtime tests passed for Bronze
and Silver patterns with successful and failed cleanup. Parent jobs
`e4ae631a-60a6-4198-893e-52579bdca1c8` and
`a41e895f-8dcd-47ea-9d9e-b671266181bb` failed as intended; their downstream
Gold sentinel never executed. Production still retains its existing definitions.
GitHub Dev/Test release `36959708090` passed at commit
`6066b04a67fc1e01c7f2f219b9e3d42bac3ac6d1`. It published the eleven Fail
activities and passed both fault scenarios under the Test CI identity, followed
by the twelve Silver checks and ten Gold SQL stages. These tests substitute
constant SQL for failure-path business work;
they do not prove real Copy/manifest or lease-cleanup behavior.

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

The remaining open review findings are independent S3 snapshot alignment,
changed DQ classifications, and overlapping-arrival checkpoint safety.
The current business fixture uses matching reference-arrival timestamps, tests
an unchanged reject classification, and executes transformations sequentially.
It therefore cannot close these findings. Do not resolve review threads merely
because that fixture or the deployment workflow passes. Expand acceptance tests
alongside the remediation and verify actual pipeline failure outcomes.

## Deployment and Governance

The legacy runtime is a template-app workspace excluded from native stage
assignment. On 2026-10-03 the user authorized replacement: Terraform created
normal workspace `300b8bbe-ee03-4a93-913f-16293c6117e4` and its Production
stage assignment succeeded. Four empty foundation containers exist there.
All 29 legacy items remain intact; data/state migration and retirement are not
complete. This removes the assignment blocker, not the correctness gates.
See [Production cutover](production-workspace-cutover.md). Keep legacy runtime
bindings gated until verified migration, rebinding, recovery and one-schedule
cutover. Never delete the data-bearing workspace merely to fix stage eligibility.

Physical manifest/recovery still requires acceptance. The separate isolated
semantic model passed delegated-operator measure/datasource checks; that does
not establish target-environment or service-principal SSO serving readiness.
The scoped AWS OIDC infrastructure role is not yet authorized/verified.
Production SQL adoption, release flags and temporary branch permission cleanup
remain approval/governance gates. A single-owner implementation and trial capacity
must not be described as independent enterprise approvals or paid-production SLA.

## Safe Implementation Order

1. Fix failure propagation and fault-inject the actual child/parent paths in Test.
2. Establish committed-input boundary semantics before changing checkpoints.
3. Fix classification transitions with recoverable idempotent target writes.
4. Fix reference enrichment history and test staggered S3 snapshots.
5. Run expanded business, manifest/replay and semantic acceptance under appropriate identities.
6. Resolve only verified review findings and merge through protected checks.
7. Complete the approved replacement cutover and reconciliation before legacy
   retirement, Production SQL adoption and code promotion.

Never reset Production checkpoints or replace its business data to make a test pass.
