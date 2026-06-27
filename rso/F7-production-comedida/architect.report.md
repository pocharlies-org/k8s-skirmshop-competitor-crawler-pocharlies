# F7 Architecture Report - produccion comedida

**Owner:** Codex RSO/PMO architecture pass.  
**Date:** 2026-06-27T16:24:50+02:00.  
**Claude status:** `rho-architect` CLI was retried with a reduced read-only prompt and exited `124` without stdout. This report is a PMO architecture exception; it does not implement product code or activate production.

## Scope inspected

- `RSO-MASTER-PLAN.md`
- `rso/F7-production-comedida/CHECKLIST.md`
- `rso/F7-production-comedida/HANDOFF.md`
- `src/main.py`
- `src/scheduler.py`
- `src/crawler.py`
- `src/push_client.py`
- `config.yaml`
- `k8s/manifest.yaml`
- `k8s/prober-deployment.yaml`
- `k8s/crawler-networkpolicy.yaml`
- `k8s/prober-networkpolicy.yaml`
- `k8s/kustomization.yaml`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

## Architecture decision

F7 must not create an active CronJob yet.

Current container command is `python -m src.main`. That starts APScheduler, writes `/tmp/healthy`, then waits for SIGTERM/SIGINT. A Kubernetes CronJob that runs this command would not naturally finish; it would behave like a long-running scheduler pod and make job success/failure evidence ambiguous.

Safe F7 options:

1. **Preferred next implementation:** add a one-shot batch entrypoint such as `python -m src.run_tier --tier tier1 --once` or `python -m src.run_all --once`. A CronJob can then run one bounded batch, exit 0/1, and produce clear job history.
2. **Alternative:** run the existing scheduler as a Deployment with `replicas: 1`, but then F7 evidence must be scheduler uptime, APScheduler job execution logs, and a manual rollback to `replicas: 0`. This is less auditable than a one-shot CronJob.

Codex RSO recommendation: implement the one-shot batch entrypoint before adding an unsuspended CronJob. Keep existing Deployments at `replicas: 0` until image, DB, secrets, egress and verification gates are complete.

## Target data/control flow

- Crawler one-shot job reads `config.yaml` tiers and runs stores sequentially with low concurrency.
- Crawler pushes current competitor documents to Brain `push-ingest` using `X-API-Key` from `BRAIN_API_KEY`.
- Brain graph remains the current-state store for comparison reads.
- Postgres `competitor_intel` remains append-only history and estimated-sales source.
- Prober remains a separate blast-radius component and must stay disabled until each target domain is explicitly allowlisted.
- F7 activation starts with crawler-only production comedida. Prober activation is a later sub-gate after live transport, allowlist, cleanup and kill-switch evidence.

## Required activation gates

- **Image:** publish a real crawler image tag/digest and replace `:pending` before activation.
- **DB:** create live CNPG `competitor_intel` and apply `db/migrations/001_f3_history.sql`; verify tables/views with read-only SQL.
- **Secrets:** verify `competitor-crawler-secrets` syncs and contains `BRAIN_API_KEY` presence only, never value disclosure.
- **Egress:** replace default-deny-only policies with explicit, minimal allow rules. Crawler needs internal Brain/Firecrawl/Postgres plus approved competitor egress; prober needs domain-specific egress only when approved.
- **Batch entrypoint:** implement bounded one-shot runner before active CronJob.
- **Observability:** expose or scrape F7 metrics/log evidence for `competitor_crawl_block_total`, job success/failure, push-ingest counts and history writes.
- **Night evidence:** one real nocturnal window with logs, metrics, Brain comparison and SQL observations.

## Rollback/stop criteria

- Any sustained 403/429/challenge/CAPTCHA signal increments block metrics and stops that domain.
- Any missing `BRAIN_API_KEY` in production fail-closes before POST.
- Any DB migration/apply failure blocks CronJob activation.
- Any image pull failure, non-zero one-shot exit, or sustained push failure suspends the CronJob or returns Deployment replicas to `0`.
- Any ban/egress-IP issue blocks further probing and requires manual review.

## Checklist

- [x] Current entrypoint behavior inspected. Evidence: `src/main.py` waits on a signal after scheduler start.
- [x] Scheduler behavior inspected. Evidence: `src/scheduler.py` uses APScheduler cron triggers and no one-shot CLI.
- [x] Safer F7 architecture selected. Evidence: recommendation above is one-shot batch runner before CronJob activation.
- [x] Current manifests remain inactive. Evidence: `k8s/manifest.yaml` and `k8s/prober-deployment.yaml` use `replicas: 0`; no CronJob resource exists.
- [blocked] Active CronJob architecture cannot pass until a bounded one-shot runner exists.
- [blocked] Full F7 architecture cannot close production until image, DB, secrets, egress, observability and night evidence gates pass.
