# Isolated Test Business Acceptance

## Purpose and Safety

Connector success does not establish analytical correctness. This harness tests
the published Silver transformations and Gold publication SQL against a tiny,
deterministic fixture. It does not copy Production data, write PostgreSQL or S3,
advance ingestion checkpoints, enable schedules, or deploy to Production.

Only the unscheduled Test workspace is permitted. Five separately owned assets
are reused there: `lh_cicd_acceptance_bronze`, `lh_cicd_acceptance_silver`,
`wh_cicd_acceptance_gold`, `nb_cicd_business_acceptance`, and
`pl_cicd_business_acceptance`. Their description starts with
`retail_ci_business_fixture_v1`. An existing item with the same name but a
different ownership description causes failure rather than replacement.
Fixture data is retained for inspection; nothing is automatically deleted.

## Execution

Use an authenticated Azure CLI session and the repository Python dependencies.
The SQL portion also requires ODBC Driver 18 for SQL Server.

```bash
python deploy/test_business_acceptance.py --environment test
python deploy/test_business_acceptance.py --environment test --execute
```

The first command is a local, nonmutating plan. The second creates or reuses the
isolated assets, downloads the four published Silver notebooks, imports a
fixture notebook, verifies its code by definition read-back, and submits one
Fabric pipeline job. It requires a successful notebook exit payload containing
all twelve checks; a green pipeline with an empty notebook is not accepted.

The notebook executes the deployed business code in Fabric Spark. It supplies
fixture parameters and removes only the terminal notebook exit so the four
transformations can execute sequentially in one session. Business expressions
for joins, SCD2, DQ and Delta merges are not replaced with test implementations.

After Spark succeeds, the authenticated runner applies the reviewed Gold baseline
migration to the acceptance Warehouse, waits for its Silver SQL endpoint, and
executes the published Gold SQL graph in dependency order. Only the Silver
database identifier is rebound to the acceptance Lakehouse. The existing Gold
schema, reconciliation and atomic-publication guards remain enabled.

## Expected Results

| Scenario | Expected result |
| --- | --- |
| Baseline | Two sales lines, amount 150.00, one order |
| Correction | Existing sales key 1 changes from 100.00 to 110.00 |
| Late sales line | January order arrives in March and uses historical dimension keys |
| SCD2 | Two customer versions; new-period sale uses new customer/product versions |
| Duplicate arrival | Two raw copies of sales key 4 produce one accepted fact |
| Soft DQ | One retained line has invalid ship/due dates and arithmetic mismatch |
| Hard DQ | Customer 999 is rejected, not accepted into fact_sales |
| Late event | Event time precedes arrival time; arrival delay remains observable |
| Replay | Business rows and reject count remain unchanged |
| Gold | Five fact lines, four orders, four eligible lines, eligible amount 230.00 |

Baseline, corrections, late arrivals, both dimension histories, as-of joins,
soft/hard DQ, line grain, replay and reject idempotency are asserted. Output
`output/business_acceptance.json` records job/item IDs, published-code hashes,
Silver evidence, Gold activity names, reconciliation totals and limitations.
Generated evidence is ignored by Git; persist CI output as workflow artifacts.

## Debugging

1. Check the returned Fabric pipeline job ID and Notebook activity in Monitor.
2. Require nonempty `exitValue` with all twelve checks, not only job status.
3. Check ownership-tagged raw Delta tables and acceptance Silver schemas.
4. For SQL endpoint delays, inspect synchronization; do not bypass Gold checks.
5. For a Gold schema mismatch, compare candidate and serving schemas. Correct
   fixture types or the reviewed migration contract, not the publication guard.
6. Inspect failed jobs before rerunning. A retry rebuilds only owned fixture data;
   it does not resume a real ingestion batch or change operational checkpoints.

## Verified Interactive Run

On 2026-10-02, Fabric job `e48d0c03-c23d-42ef-88db-7b8abc02feb7` passed
all twelve Silver checks. The authenticated SQL runner passed all ten published
Gold activities, including candidate audit, atomic publication and published
audit equality. Final totals were five fact lines, four orders, four eligible
lines and eligible sales amount 230.00. There were two customer versions and
one hard reject. Source mutations and ingestion checkpoint updates were zero.

An earlier generated notebook was imported empty and returned a misleading
successful job status. That run is not acceptance evidence. Native notebook
formatting, full-code read-back and mandatory exit-result assertions now prevent
this false positive. Offline tests cover empty results and isolation violations.
GitHub OIDC execution is a separate gate from this interactive result.

## Failure Propagation Gate

```bash
python deploy/test_failure_paths.py --environment test
python deploy/test_failure_paths.py --environment test --execute
```

This separate Test-only harness creates three owned pipeline fixtures. It copies
the reviewed Bronze/Silver Fail activities and the daily parent invocation shape,
substituting constant SQL and deliberate divide-by-zero errors. Both successful
and failed cleanup must produce the intended child error code and a failed
parent. The success-dependent Gold sentinel must never execute. Some Fabric run
queries omit never-started activities, so evidence labels an absent sentinel
`NotExecuted` rather than inventing a recorded Skipped activity. Definition
read-back verifies the sentinel exists with the correct dependencies.

Runtime pattern checks passed for both cases on 2026-10-02. Generated evidence is
`output/failure_acceptance.json`; Test CI preserves it with the business results.
This is not a test of actual Copy failures, physical manifests or cleanup SQL.

## Coverage Limits and Remaining Production Gates

- Fixture landing is direct Delta writing, not the production source Copy path.
- Gold SQL is executed by the authenticated test runner, not a Gold pipeline job.
- Actual physical manifest commits and end-to-end orchestration are not proven
  by metadata-only contract tests or this fixture.
- Semantic-model serving, KPI queries and datasource binding require a separate
  acceptance check before Production approval.
- Local interactive execution is not evidence that GitHub OIDC can execute the
  same job. Verify the acceptance workflow under the Test CI identity separately.
- Keep Production flags disabled until these gates and the workspace deployment
  decision are resolved. Never use acceptance fixtures as retail business data.

## Production Deployment-Pipeline Blocker

The existing retail Production workspace is a template-app workspace. Its stage
assignment returns `ALM_InvalidRequest_TemplateAppWorkspacesNotSupported`.
Microsoft excludes that workspace type from deployment pipelines:
[workspace assignment requirements](https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/assign-pipeline).

Starting the gateway VM cannot change workspace eligibility. Keep the existing
Production workspace with the gated GitHub release path, or approve a separately
planned migration to a normal workspace. Do not delete Production, deploy to the
empty native Production stage, or substitute an unrelated workspace.
