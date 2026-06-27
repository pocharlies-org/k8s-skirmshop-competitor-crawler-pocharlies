# F7 Activation Runbook - gated

This runbook records the remaining activation sequence. It is not approval to apply production.

## Current safe state

- Branch: `codex/competitor-crawler-F7-production-comedida`
- Crawler Deployment: prepared, `replicas: 0`, image `:pending`.
- Prober Deployment: prepared, `replicas: 0`, image `:pending`.
- NetworkPolicy: crawler and prober default-deny egress.
- Brain push auth: implemented with `BRAIN_API_KEY` and `REQUIRE_BRAIN_API_KEY=true`.
- CI: smoke build and manifest validation passing.
- Live DB: not present.
- CronJob: not present.
- Production activation: blocked.

## Gate 1 - publish image

Required evidence:

- Release workflow available and runnable.
- Release run publishes `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:<tag>` or digest.
- Manifest pins the published tag/digest, not `:pending`.
- CI or release log confirms image push.

Blocked until either the release workflow is merged to the branch/default path where GitHub can run it, or an explicitly approved manual image publish path is used.

## Gate 2 - one-shot runner

Required evidence:

- A bounded crawler command exists and exits 0/1 after one tier/window.
- Tests cover success, failure and no-doc/no-push behavior.
- CronJob command uses the one-shot runner, not `python -m src.main`.
- `concurrencyPolicy: Forbid`, low resources, history limits and backoff are configured.

## Gate 3 - DB and migration

Required evidence:

- CNPG `Database` resource `competitor-intel` exists live in namespace `databases`.
- Migration `db/migrations/001_f3_history.sql` is applied to `competitor_intel`.
- Read-only SQL verifies tables/partitions/view used by F3/F7.
- Credentials are least-privilege and delivered through secrets without value disclosure.

## Gate 4 - secrets

Required evidence:

- `ExternalSecret/competitor-crawler-secrets` is synced.
- Resulting Secret exists and includes required keys by name only.
- No secret value appears in repo, logs, reports or shell output.

## Gate 5 - egress allowlists

Required evidence:

- Crawler can reach only required internal services plus approved competitor egress.
- Prober remains disabled unless a domain-specific allowlist is approved.
- If Kubernetes NetworkPolicy cannot express domain/FQDN egress in this cluster, the alternative control must be documented before activation.

## Gate 6 - observability

Required evidence:

- Metrics/logs expose job success, push sent/failed counts, blocked-domain count, retry/failure reasons and history writes.
- Prometheus/dashboard or equivalent read-only query is captured in F7 evidence.

## Gate 7 - live night

Required evidence:

- One real nocturnal run completes.
- `competitor_crawl_block_total` has no sustained increase.
- Logs show no ban/challenge/CAPTCHA escalation.
- Brain `/prices/comparison` remains populated.
- Postgres history has new observations for the run.

F7 PASS requires all gates above.
