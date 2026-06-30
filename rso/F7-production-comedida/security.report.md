# F7 Security Report - independent read-only audit

**Owner:** `rho-security` independent read-only pass, reconciled by Codex RSO/PMO.
**Date:** 2026-06-27T16:56:37+02:00.
**Branch/commit audited:** `codex/competitor-crawler-F7-production-comedida` at `18f869f`.
**PMO update:** 2026-06-30T02:56:00+02:00 after crawler/prober image pins,
history runtime, compensating NetworkPolicies, Brain secret source-path fix and
the one-target AirsoftQuimera prober B3 smoke.

## Verdict

- Current disabled F7 security posture: **PASS**.
- Production activation security posture: **BLOCKED** until remaining gates close.

The prepared state remains safe because steady-state production remains disabled:
crawler/prober Deployments are at `replicas: 0`, crawler CronJobs are
`suspend: true`, crawler and prober images are pinned by digest, permanent
prober egress is default-deny, and secrets are referenced by name only. B3 used
one deleted temporary NetworkPolicy for a single approved AirsoftQuimera target.

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
- `src/prober/http_transport.py`
- `src/prober/airsoftquimera.py`
- `src/prober/run_once.py`
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
- [x] Workloads are inactive. Evidence: `replicas: 0`; crawler CronJobs
  `suspend: true`; prober Deployment is digest-pinned to
  `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.
- [x] Pod hardening present. Evidence: non-root uid/gid/fsGroup 10001, `RuntimeDefault`, no privilege escalation, read-only root filesystem, drop all capabilities, no service-account token, `/tmp` emptyDir.
- [x] Egress restricted. Evidence: crawler NetworkPolicy allows only DNS, Brain, Firecrawl, Postgres and public TCP 80/443 with private ranges excluded; prober NetworkPolicy remains `egress: []`.
- [x] No CAPTCHA/login/checkout/payment bypass. Evidence: crawler skips login/account/cart/checkout paths; prober boundary states no checkout/login/CAPTCHA; no CAPTCHA solver present.
- [x] Prober production blast radius is controlled by being disabled in
  steady-state. Evidence: `src/prober/http_transport.py` enforces approved host
  before HTTP, B3 temporary Job touched only add/remove paths for product
  `22046`, permanent NetworkPolicy is default-deny, and the Deployment remains
  `replicas=0`.

## Activation blockers

- [blocked] Native FQDN egress allowlist is not available in standard Kubernetes NetworkPolicy. Activation relies on documented compensating controls: app-level domain guard plus restricted network egress.
- [blocked] Live night/job evidence is not captured yet.
- [blocked] Metrics scrape and block/failure evidence still require a real CronJob pod.

## Notes

- Dockerfile does not set `USER 10001`; Kubernetes `securityContext` currently enforces non-root. Adding `USER` later would improve defense in depth but is not a blocker while pods are governed by the hardened manifests.
