## Problem and Scope

Explain the user/data problem. State whether this changes definitions, source
simulation, infrastructure or runtime data. Never include credentials/raw records.

## Changes

Describe behaviour changes and update diagrams/contracts when necessary.

## Verification

- [ ] Credential-free CI and publication checks passed.
- [ ] Tests cover affected behaviour and documented limitations.
- [ ] Cloud tests, if any, identify environment and fixture versus physical Copy.
- [ ] No Production gate, schedule or checkpoint was bypassed/reset.
- [ ] Rollback and data/state recovery implications are documented.

## Remaining Risks

List unverified cases; do not equate definition validation with runtime readiness.
