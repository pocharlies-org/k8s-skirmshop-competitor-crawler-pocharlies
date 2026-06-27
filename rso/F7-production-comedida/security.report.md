# F7 Security Report - independent read-only audit

**Owner:** `rho-security` independent read-only pass, reconciled by Codex RSO/PMO.
**Date:** 2026-06-27T16:56:37+02:00.
**Branch/commit audited:** `codex/competitor-crawler-F7-production-comedida` at `18f869f`.
**PMO update:** 2026-06-27T21:20:16+02:00 after image pin, history runtime, compensating NetworkPolicy and Brain secret source-path fix.

## Verdict

- Current disabled F7 security posture: **PASS**.
- Production activation security posture: **BLOCKED** until remaining gates close.

The prepared state remains safe because nothing runs: crawler/prober Deployments are at `replicas: 0`, crawler CronJobs are `suspend: true`, the crawler image is pinned by digest, the prober image is still `:pending`, egress is constrained, and secrets are referenced by name only.

## Evidence inspected

- `k8s/manifest.yaml`
- `k8s/prober-deployment.yaml`
- `k8s/crawler-cronjobs.yaml`
- `k8s/crawler-networkpolicy.yaml`
- `k8s/prober-networkpolicy.yaml`
- `k8s/externalsecret.yaml`
- `k8s/kustomization.yaml`
- `src/push_client.py`
- `src/prober/killswitch.py`
- `src/prober/transport.py`
- `src/prober/shopify.py`
- `src/prober/woo.py`
- `src/extractor.py`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `Dockerfile`

## Security checklist

- [x] Read-only audit; no production write/activation.
- [x] No secret values in manifests/code/reports. Evidence: secrets are env names/references; `competitor-crawler-secrets` maps only key name `BRAIN_API_KEY` from Vault path `skirmshop-brain/prod/app` property `dashboard_api_key`; `test-secret` is only a test fixture.
- [x] Brain auth fail-closes. Evidence: `BRAIN_API_KEY` is read from env; `REQUIRE_BRAIN_API_KEY=true` raises before any POST when key is absent; key is not logged.
- [x] Workloads are inactive. Evidence: `replicas: 0`; crawler CronJobs `suspend: true`; prober image remains `:pending`.
- [x] Pod hardening present. Evidence: non-root uid/gid/fsGroup 10001, `RuntimeDefault`, no privilege escalation, read-only root filesystem, drop all capabilities, no service-account token, `/tmp` emptyDir.
- [x] Egress restricted. Evidence: crawler NetworkPolicy allows only DNS, Brain, Firecrawl, Postgres and public TCP 80/443 with private ranges excluded; prober NetworkPolicy remains `egress: []`.
- [x] No CAPTCHA/login/checkout/payment bypass. Evidence: crawler skips login/account/cart/checkout paths; prober boundary states no checkout/login/CAPTCHA; no CAPTCHA solver present.
- [x] Prober production blast radius is controlled by being disabled. Evidence: transport is a `Protocol` stub and NetworkPolicy is default-deny.

## Activation blockers

- [blocked] Native FQDN egress allowlist is not available in standard Kubernetes NetworkPolicy. Activation relies on documented compensating controls: app-level domain guard plus restricted network egress.
- [blocked] Prober live transport and per-domain allowlist are absent.
- [blocked] Prober image is still `:pending`.
- [blocked] Live night/job evidence is not captured yet.
- [blocked] Metrics scrape and block/failure evidence still require a real CronJob pod.

## Notes

- Dockerfile does not set `USER 10001`; Kubernetes `securityContext` currently enforces non-root. Adding `USER` later would improve defense in depth but is not a blocker while pods are governed by the hardened manifests.
