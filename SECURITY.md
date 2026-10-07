# Security Policy

Never open a public issue containing credentials, source records, Terraform
state, connection exports, database dumps or private run output. Use GitHub's
private vulnerability reporting when available, or contact the maintainer
privately. Do not include a working exploit against someone else's cloud account.

## Credential Handling

- Use environment variables, AWS profiles/SSO and GitHub OIDC; never hardcode keys.
- Keep populated `.env`, `secrets`, generated datasets and state outside Git.
- Rotate any credential previously pasted into a chat or exposed publicly.
  Removing a file does not revoke a credential or erase Git history.
- The publication scanner is a defence in depth, not a guarantee of no secrets.
- Workspace IDs and deployment bindings are configuration, not authentication.
- Source simulation has write privileges only because this is an owned project
  source. Fabric ingestion must use read-only source credentials.

The local PostgreSQL example binds to loopback by default. A Windows gateway VM
needs an explicitly chosen reachable private interface, firewall restrictions
and PostgreSQL authentication rules. Do not expose port 5432 to the internet.

## Scope

This portfolio demonstrates production-style patterns; it is not an assertion
of a production SLA, independently enforced approvals or completed Production
cutover. Read the readiness blockers before any cloud execution.
