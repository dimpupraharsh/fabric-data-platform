# Implementation Status

Publication review: **7 October 2026**. These are saved definitions and recorded
outcomes, not a fresh Fabric health or data-count audit.

| Area | Recorded evidence | Boundary |
| --- | --- | --- |
| Scale | Legacy Gold audit: 15,001,016 sales lines and 5,007,874 orders | Published 29 September; read 3 October; not a new source count |
| Bronze | Metadata-driven PG/S3 definitions and historical run evidence | Publication does not rerun ingestion/recovery |
| Silver | SCD2, deduplication, late-arrival and quality code | Three correctness findings remain open |
| Gold | Candidate audit and transactional publication | Not universal failure/concurrency proof |
| Semantic | 18 DAX measures and historical Warehouse/model comparisons | No deployed report/commercial usage claimed |
| Acceptance | 12 Silver checks and 10 Gold SQL stages recorded in Test | Fixture bypasses physical source Copy; Gold SQL is runner-driven |
| CI/CD | Versioned migrations and recorded Dev/Test delivery | Not completed Production migration/serving |
| Infrastructure | Terraform, private S3 state, normal Production stage assignment | Four empty new foundations; legacy data preserved |

## Open Work

1. Coherent reference-version/as-of semantics for independent S3 arrivals.
2. Recoverable accepted/rejected classification transitions.
3. Silver checkpoints based on a frozen committed input boundary, not completion time.
4. Expanded physical Copy, manifest/recovery and concurrent-arrival tests.
5. Production migration, target bindings, semantic serving and schedule cutover.
6. Dedicated AWS infrastructure OIDC authorization and remaining governance gates.

Read [readiness blockers](production-readiness-blockers.md) and
[business acceptance](business-acceptance-runbook.md). Keep Production gates
disabled and do not close review findings because CI passes.

Supported portfolio claims concern scale, implemented components and bounded
tests. Cost savings, adoption, financial impact and universal exactly-once
behaviour are not established. Generated sales totals are not business impact.
