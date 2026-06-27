# F7 Security Report - independent read-only audit

**Owner:** `rho-security` independent read-only pass, reconciled by Codex RSO/PMO.
**Date:** 2026-06-27T16:56:37+02:00.
**Branch/commit audited:** `codex/competitor-crawler-F7-production-comedida` at `18f869f`.

## Verdict

- Current disabled F7 security posture: **PASS**.
- Production activation security posture: **BLOCKED** until remaining gates close.

The prepared state is safe because nothing runs: crawler/prober Deployments are at `replicas: 0`, CronJobs are `suspend: true`, images are `:pending`, egress is default-deny, and secrets are referenced by name only.

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
- [x] No secret values in manifests/code/reports. Evidence: secrets are env names/references; `ExternalSecret` points to Vault key `secret/skirmshop/competitor-crawler`; `test-secret` is only a test fixture.
- [x] Brain auth fail-closes. Evidence: `BRAIN_API_KEY` is read from env; `REQUIRE_BRAIN_API_KEY=true` raises before any POST when key is absent; key is not logged.
- [x] Workloads are inactive. Evidence: `replicas: 0`; CronJobs `suspend: true`; images `:pending`.
- [x] Pod hardening present. Evidence: non-root uid/gid/fsGroup 10001, `RuntimeDefault`, no privilege escalation, read-only root filesystem, drop all capabilities, no service-account token, `/tmp` emptyDir.
- [x] Egress restricted. Evidence: crawler and prober NetworkPolicies have `egress: []`.
- [x] No CAPTCHA/login/checkout/payment bypass. Evidence: crawler skips login/account/cart/checkout paths; prober boundary states no checkout/login/CAPTCHA; no CAPTCHA solver present.
- [x] Prober production blast radius is controlled by being disabled. Evidence: transport is a `Protocol` stub and NetworkPolicy is default-deny.

## Activation blockers

- [blocked] Egress allowlist is missing. Plain Kubernetes NetworkPolicy cannot express FQDN allowlists; activation needs a documented cluster-specific control before any `suspend: false`.
- [blocked] Prober live transport and per-domain allowlist are absent.
- [blocked] Images are still `:pending`; no production tag/digest is pinned.
- [blocked] `competitor_intel` DB and least-privilege runtime credentials are not live.
- [blocked] Observability for `competitor_crawl_block_total` is not scrapeable yet.

## Notes

- Dockerfile does not set `USER 10001`; Kubernetes `securityContext` currently enforces non-root. Adding `USER` later would improve defense in depth but is not a blocker while pods are governed by the hardened manifests.
