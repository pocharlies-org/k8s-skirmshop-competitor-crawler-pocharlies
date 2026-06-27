# RHO DevOps - F7 history and egress wiring

## Scope
- Implementer: Codex PMO exception after `rho-devops` Claude CLI produced no stdout and no diff.
- Files touched: `k8s/externalsecret.yaml`, `k8s/manifest.yaml`, `k8s/crawler-cronjobs.yaml`, `k8s/crawler-networkpolicy.yaml`.
- Production activation: none. Deployment remains `replicas: 0`; CronJobs remain `suspend: true`.

## Changes
- Added `ExternalSecret/competitor-crawler-db-credentials` in namespace `skirmshop`, sourcing `DB_USER`/`DB_PASSWORD` from Vault key `secret/skirmshop/labels`.
- Added runtime history env to crawler Deployment and CronJobs:
  - `HISTORY_ENABLED=true`
  - `PGHOST=postgres-shared-rw.databases.svc.cluster.local`
  - `PGPORT=5432`
  - `PGDATABASE=competitor_intel`
  - `PGCONNECT_TIMEOUT=10`
  - `PGUSER`/`PGPASSWORD` from `competitor-crawler-db-credentials`
- Added `--fail-on-push-errors` to each crawler CronJob command so history/Brain failures can make the Job fail.
- Replaced crawler default-deny-only egress with explicit allow rules for DNS, Brain API, Firecrawl API, CNPG Postgres, and public TCP 80/443.

## Egress Model
The cluster only exposes standard `networking.k8s.io/v1 NetworkPolicy`; there is no Cilium/FQDN CRD. The compensating control is:
- NetworkPolicy allows only required internal services plus public TCP 80/443, excluding private/link-local ranges.
- Application egress guard enforces approved competitor domains before direct fetch and Firecrawl fallback.

## Checklist
- [x] History DB credentials are referenced by Secret name/key only. Evidence: `ExternalSecret/competitor-crawler-db-credentials`.
- [x] Runtime history env is present in Deployment and all three CronJobs. Evidence: `k8s/manifest.yaml`; `k8s/crawler-cronjobs.yaml`.
- [x] CronJobs fail on push/history failures. Evidence: `--fail-on-push-errors` in all three CronJob commands; scheduler increments failed count on history exception.
- [x] NetworkPolicy allows DNS, Brain, Firecrawl and Postgres explicitly. Evidence: `k8s/crawler-networkpolicy.yaml`.
- [x] External egress is limited to public TCP 80/443 and relies on app-domain guard for FQDN allowlist. Evidence: `ipBlock 0.0.0.0/0` with private/link-local `except`; `backend-egress.report.md`.
- [blocked] FQDN-native enforcement is unavailable in the cluster; this remains a compensating control, not Cilium-style FQDN policy.
