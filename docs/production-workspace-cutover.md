# Production Workspace Cutover

Verified 2026-10-03. The user authorized replacing the template-app workspace.

## Completed

- Terraform created `Retail Order Intelligence Platform - Production`
  (`300b8bbe-ee03-4a93-913f-16293c6117e4`) on the existing trial capacity.
- The Production deployment identity and its new workspace identity each have
  Contributor on the replacement. The reviewed apply added three resources,
  changed zero existing resources and destroyed zero resources.
- Created four empty foundation items: `lh_retail_bronze`, `lh_retail_silver`,
  `wh_retail_control`, `wh_retail_gold`. Two SQL endpoints were auto-generated.
- Assigned the normal workspace to Production stage
  `2a7292c1-0e30-426c-9e71-6c9d64a7a77f` in deployment pipeline
  `36eae116-42d0-498d-a280-8060a4aecccb`. Read-back confirms all three stages.
- Preserved all 29 legacy workspace item IDs. No legacy data, definitions,
  checkpoints, schedules, source records or S3 source files were changed.

## Not Yet Completed

Attachment is not data migration or a Production release. The new four items
are empty containers, not deployed Warehouse schemas or populated Lakehouses.
The old template workspace remains data-bearing and must not be deleted yet.
Its Gold audit, read on 3 October, records 15,001,016 sales lines and 5,007,874
orders at publication time 29 September 2026 20:11:11 UTC. This is the recorded
audit population, not a fresh full-table count of PostgreSQL or every layer.

`config/environments.json` deliberately retains old Production runtime bindings
while its release/migration/semantic flags remain false. The new stage target
is recorded separately in `config/production_cutover.json`. This temporary
difference is intentional: switching IDs before schema/data/connector migration
would route tooling into empty containers. GitHub remains the sole application
promotion authority; native stages are for comparison, not a second release path.

## Safe Cutover Order

1. Correct and regression-test the three open Production correctness findings
   in `production-readiness-blockers.md`; passing a limited fixture is not enough.
2. Inventory and preserve business data, control configuration and runtime
   checkpoint/history rows, model bindings, schedules and monitoring dependencies.
   Item definitions and this inventory are not data backups.
3. Deploy reviewed schemas and application definitions to the replacement with
   schedules off; create destination-specific SQL/Lakehouse connections.
4. Pause legacy writers for a controlled cutover. Copy consistent Bronze/Silver
   Delta data and Warehouse data/control state using supported Fabric mechanisms.
   Rebuilding from current PostgreSQL alone cannot recover all historic snapshots.
5. Reconcile keys, counts, SCD2 history, rejects, manifests, checkpoints, Gold
   totals and semantic queries. Verify rollback/recovery before deleting anything.
6. Update environment config and GitHub bindings to the new IDs; enable release
   gates only after review, then activate exactly one daily schedule. Keep the
   old workspace for a defined recovery period with writers stopped.
7. Retire the old workspace only after acceptance, monitoring/reports have been
   handled, and a reviewed Terraform change removes its protected resources.
   Do not bypass `prevent_destroy` or manipulate state to hide deletion.

## Operator Files

- `infra/fabric/production_replacement.tf`: additive IaC, remote S3 state.
- `deploy/bootstrap_production_replacement.py`: idempotent operator bootstrap
  for four empty items and stage assignment, not data transfer or code promotion.
- `config/production_cutover.json`: nonsecret transitional mapping and gates.
- Private evidence: root `output/cicd-evidence/production-replacement-bootstrap.json`.

Microsoft excludes template-app workspaces from native stage assignment:
https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/assign-pipeline
