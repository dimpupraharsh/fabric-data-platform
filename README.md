# Retail Order Intelligence: Fabric Delivery

This repository contains deployable Fabric definitions, additive Warehouse
migrations, environment bindings, and infrastructure as code. It contains no
source datasets, credentials, Terraform state, or production run history.

## Environments

- Dev: development and bounded test data; schedules disabled.
- Test: release verification and isolated checkpoints; schedules disabled.
- Production: normal replacement assigned to the native stage; four empty
  foundation containers. Legacy retail runtime/data are preserved until verified
  migration and cutover. Release gates remain disabled.

See [Production cutover](docs/production-workspace-cutover.md) and
`config/production_cutover.json`. `config/environments.json` intentionally keeps
legacy runtime bindings until the replacement is ready to serve data.

Infrastructure is Terraform-managed. Fabric application definitions are published
using pinned `fabric-cicd`; Warehouse schemas use checksum-locked SQL migrations.
The existing trial capacity is for evaluation, not a paid production SLA.

## Delivery

`CI` validates pull requests without credentials. `OIDC Readiness` verifies
GitHub-to-Entra authentication and read-only Fabric/SQL access. `Promote Fabric
Release` packages a tested main commit once and promotes the same SHA-256-verified
artifact through Dev, Test and an approved Production environment.

Application release flags remain fail-closed until connectors and integration
gates pass. A successful deployment smoke test is not an end-to-end ingestion,
replay, schema-drift or failure-recovery test. No workflow resets watermarks,
copies Production run history, deletes Fabric items or enables schedules.

## Commands

```bash
python -m pip install -r requirements.txt
python deploy/check_repository.py
pytest -q
python deploy/migrate.py --environment dev
python deploy/smoke.py --environment dev
python deploy/release.py --environment dev --stage application
```

`release.py` prepares only unless `--execute` is supplied. Operators use Azure CLI
sign-in; CI uses GitHub OIDC, without client secrets. S3 state is private,
versioned, encrypted and lock-protected in a dedicated bucket, separate from the
retail reference source. Never add local `secrets`, `.env`, state or plan files.
