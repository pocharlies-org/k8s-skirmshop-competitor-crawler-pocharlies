# DevOps Secret Report - F7

Date: 2026-06-27T21:20:16+02:00
Role: `rho-devops` implementer via Claude CLI; PMO review required because the CLI timed out without stdout after writing a diff.

## Objective

Unblock F7 Gate 4 by making `ExternalSecret/competitor-crawler-secrets` sync the Brain API key from an existing Vault path without exposing secret values.

## Directives

- [x] Do not print or hardcode secret values. Evidence: only key names and Vault references are documented.
- [x] Keep DB credentials separate. Evidence: `competitor-crawler-db-credentials` is unchanged.
- [x] Do not activate production. Evidence: no CronJob suspension or replica change in this diff.
- [x] Do not touch `deploy/prod`. Evidence: change is limited to crawler repo branch `codex/competitor-crawler-F7-production-comedida`.

## Acceptance Criteria

- [x] `competitor-crawler-secrets` no longer references the missing Vault key `secret/skirmshop/competitor-crawler`. Evidence: `k8s/externalsecret.yaml` uses `spec.data`, not `spec.dataFrom.extract`.
- [x] `competitor-crawler-secrets` maps exactly `BRAIN_API_KEY`. Evidence: `spec.data[0].secretKey: BRAIN_API_KEY`.
- [x] Remote source matches the existing Brain auth source used by other Skirmshop services. Evidence: `remoteRef.key: skirmshop-brain/prod/app`; `remoteRef.property: dashboard_api_key`.
- [x] Server dry-run accepts the changed manifest. Evidence: `kubectl apply --dry-run=server -k k8s` -> `externalsecret.external-secrets.io/competitor-crawler-secrets configured (server dry run)`.
- [ ] Live ExternalSecret syncs and Secret exists by key name only. Evidence pending: `kubectl -n skirmshop get externalsecret competitor-crawler-secrets`; `kubectl -n skirmshop get secret competitor-crawler-secrets -o json | jq -r '.data | keys[]'`.

## Files Touched

- `k8s/externalsecret.yaml`
- `rso/F7-production-comedida/activation-runbook.md`
- `rso/F7-production-comedida/devops-secret.report.md`

## Residual Risks

- Live sync still depends on Vault path `skirmshop-brain/prod/app` and property `dashboard_api_key` being readable by `vault-backend`.
- Argo will remain Degraded until the branch change is pushed and reconciled into the live Application target revision.
