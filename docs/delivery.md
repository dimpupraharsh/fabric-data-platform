# Git, GitHub Actions and Terraform

## Three Different Responsibilities

| Plane | Owner | What it manages |
| --- | --- | --- |
| Infrastructure | Terraform under `infra/` | Stable Fabric/identity/deployment infrastructure |
| Application delivery | GitHub Actions and `deploy/` | Versioned item definitions and SQL migrations |
| Data processing | Fabric pipelines/notebooks/SQL | Bronze, Silver, Gold and runtime control state |

Terraform state lives in a separate private, encrypted/versioned S3 bucket with
native lockfiles. It does not belong in the reference-data bucket, Git or a
OneLake business-data directory. Watermarks, manifests and run history belong
in the control Warehouse, not Terraform seeds.

## Workflows

- **CI:** PR/branch definition checks, tests and backend-free Terraform validation.
  No cloud credentials are required.
- **OIDC Readiness:** explicitly dispatched identity/read-access verification.
- **Dev/Test release:** explicitly dispatched non-production delivery and gates.
- **Promote Fabric Release:** packages one main commit and verifies the same
  artifact digest through Dev, Test and gated Production promotion.

Inspect `.github/workflows/` for actual triggers; committing source code does
not itself run a data pipeline or automatically promote Production.

## Environment Isolation

Dev/Test have independent bindings and checkpoints; their schedules are disabled.
The new normal Production workspace is assigned to the native stage, but its
four foundations are empty. Legacy runtime/data remain intact until migration,
bindings, serving, recovery and schedule cutover pass. Current Production
release flags remain disabled. A trial capacity is not a paid-production SLA.

GitHub authentication, Fabric Git integration, Actions validation and application
deployment are separate checks. The documented delivery uses Actions/API; do not
describe that as live native workspace Git synchronization without evidence.

## Code Change Example

1. Change an eligibility rule on a feature branch and update its metric contract.
2. Add positive/negative tests and record whether they use fixtures or physical Copy.
3. Open a PR and pass checks/review; unresolved correctness gates remain blockers.
4. Publish an approved artifact to Dev/Test, run integration acceptance and inspect results.
5. Promote only when Production flags, migration and approval gates are genuinely ready.

Rollback of a definition does not automatically undo business data already
written by that definition. Recovery needs an explicit data/state strategy.
See [release](release-runbook.md), [acceptance](business-acceptance-runbook.md)
and [cutover](production-workspace-cutover.md).
