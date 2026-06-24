# RHO Security Verification - F4 Cart-Probe

**Role:** `rho-security` delegated by Codex RSO.
**Mode:** read-only; no implementation, no file edits, no live cart-probe, no re-delegation.
**Verdict:** **PASS for F4 mock-only scope**. Live sample-10 calibration remains **BLOCKED**.

## Scope Inspected
- `src/prober/{__init__,contract,transport,killswitch,metrics,shopify,woo,generic,service}.py`
- `tests/test_prober_{contract,generic,shopify,woo,service}.py`
- `k8s/{prober-deployment,prober-networkpolicy,kustomization,externalsecret}.yaml`
- `rso/F4-cart-probe/{CHECKLIST,HANDOFF,devops.report}.md`

## Checklist
- [x] No live HTTP client in F4 prober code. Evidence: `rg` scan in `src/prober/` found no `requests`, `httpx`, `urllib`, `aiohttp`, `socket`, `selenium`, or `playwright` imports; `transport.py` is a `ProbeTransport` protocol and tests inject fake transports.
- [x] No checkout, login, accounts, CAPTCHA solver, anti-bot bypass, or purchase flow. Evidence: forbidden-flow scan only found boundary documentation; F4 probers only add-to-cart and cleanup/remove through injected transport.
- [x] Anti-bot fails closed. Evidence: `shopify.py` and `woo.py` map `403`, `429`, and `is_challenge` to block reasons; `killswitch.py` records 36h cooldown and refuses later probes without network.
- [x] Cleanup is verified and dirty carts are not hidden. Evidence: Shopify cleanup uses `/cart/clear.js`; Woo cleanup uses `/wp-json/wc/store/v1/cart/remove-item`; cleanup failure returns `ProbeStatus.ERROR` with `CleanupStatus.DIRTY`.
- [x] Generic/unknown platforms are default-deny. Evidence: `GenericProber` returns `SKIPPED/no_safe_pattern` and tests assert `transport.calls == []`.
- [x] No secrets, cookies, raw HTML, or PII exposure in F4 prober logs/reports. Evidence: `src/prober/` has no logging/print; `ProbeResponse` stores status/json/challenge only; metrics labels are domain/platform/status/reason.
- [x] K8s prober is disabled and isolated. Evidence: `k8s/prober-deployment.yaml` has `replicas: 0`, `automountServiceAccountToken: false`, `enableServiceLinks: false`; `k8s/prober-networkpolicy.yaml` has `egress: []`; no Service/CronJob.
- [blocked] Live sample-10 calibration. Blocker: no approved green Shopify/Woo target exists in the current fingerprint; all green domains are `generic_html`, while Woo domains are red/captcha.

## Residual Pre-Activation Risks
- Add pod/container `securityContext` before changing `replicas: 0` to active (`runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, drop capabilities, `seccompProfile: RuntimeDefault`).
- Replace broad `envFrom secretRef` with explicit `secretKeyRef` entries when the live transport exists and required keys are known.
- Verify the future live egress allowlist is enforced by CNI before activation.
- Re-run security against the future real `ProbeTransport` implementation; F4 currently validates only the mock/injected transport boundary.

## Notes
- `rho-security` could not re-run pytest in its first read-only harness because the Claude-side classifier blocked Python commands. Codex RSO and `rho-verifier` re-ran the executable gates separately.
