# Documentation Index

## Understand the Project

| Document | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Data, metadata control and delivery diagrams |
| [Walkthrough](project-walkthrough.md) | Source-to-report explanation and example |
| [Metrics](metrics.md) | Actual DAX measures, Gold marts and limitations |
| [Status](implementation-status.md) | Recorded outcomes versus open work |
| [Asset catalogue](asset-catalog.md) | Saved item descriptions, pipeline parameters, variables and activities |

## Run and Maintain It

| Document | Purpose |
| --- | --- |
| [Getting started](getting-started.md) | Dependencies, source tools and safety |
| [Delivery](delivery.md) | GitHub Actions, Terraform and environments |
| [Debugging](debugging.md) | Trace failure from source to consumer |
| [Release runbook](release-runbook.md) | Existing guarded release tooling |
| [Business acceptance](business-acceptance-runbook.md) | Fixture coverage and integration limits |
| [Production blockers](production-readiness-blockers.md) | Correctness and cutover gates |
| [Production cutover](production-workspace-cutover.md) | Preserve legacy data while preparing its replacement |

GitHub renders Mermaid diagrams in [architecture.md](architecture.md).
The [editable draw.io file](diagrams/retail_order_intelligence_architecture.drawio)
is an earlier reference snapshot, not a current live inventory.

Documentation must distinguish definitions, tests and live verification. Record
observation dates. Do not publish private screenshots, credentials or source
records. Deployable definitions in `workspace/` are the release authority.
