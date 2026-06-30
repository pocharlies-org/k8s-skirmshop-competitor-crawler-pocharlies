# RHO PMO Report - F7 Prober Live Gap

Timestamp: 2026-06-30T01:35:00+02:00

## Objective
- [blocked] Close the F7 stock-prober live gate. Blocker: the repository has F4 mock/cart-probe primitives and one AirsoftQuimera calibration artifact, but no production-safe live prober runner, no live HTTP transport, no prober image publication, and no approved prober egress allowlist.

## Direct Evidence
- [x] F4 prober primitives exist. Evidence: `src/prober/contract.py`, `src/prober/shopify.py`, `src/prober/woo.py`, `src/prober/generic.py`, `src/prober/service.py`, and tests `tests/test_prober_*`.
- [x] Current prober transport is not live HTTP. Evidence: `src/prober/transport.py` says "mock-only, no live HTTP" and defines only `ProbeTransport`/`ProbeResponse` protocol objects.
- [blocked] There is no prober runner entrypoint. Evidence: no `src/prober/run_once.py` or equivalent CLI; `Dockerfile` default command is `python -m src.main` for the crawler daemon.
- [blocked] Prober image is not published/pinned. Evidence: `.github/workflows/ci.yml` and `.github/workflows/release.yml` build only `skirmshop-competitor-crawler`; `k8s/prober-deployment.yaml` uses `harbor.e-dani.com/homelab/skirmshop-stock-prober:pending`.
- [blocked] Prober live egress remains default-deny. Evidence: `k8s/prober-networkpolicy.yaml` has `egress: []`.
- [x] One approved custom-domain calibration exists. Evidence: `rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md` records approved `airsoftquimera.com` sample-10 behavior: add path `/cacc_4_50_1_<product_id>_<qty>_0/`, remove path `/cacc_4_50_2_<product_id>_0_0/`, LIMIT(N) response text, cleanup HTTP 200, no 403/429/challenge observed.

## Required Next Sub-Gates
- [x] **Architecture gate scoped for B1+B2.** F7 keeps the prober as required but splits it into non-destructive B1+B2 preparation and a later B3 live smoke. Evidence: `rso/F7-production-comedida/prober-live-B1B2-checklist.md` and `rso/F7-production-comedida/HANDOFF-PROBER-LIVE-B1B2.md`.
- [ ] **Backend gate.** Implement only an approved-domain adapter first: `airsoftquimera.com` path-based pattern from F4 evidence, sample <= 10, concurrency 1, low quantity ceiling, honest UA, timeouts, no checkout/login/account/CAPTCHA bypass, and guaranteed cleanup.
- [ ] **HTTP transport gate.** Add a bounded `ProbeTransport` implementation with challenge/403/429 detection, no raw HTML logging, no cookie persistence beyond the single product/session, and deterministic tests.
- [ ] **History gate.** Map `ProbeResult` to F3 `Observation` via `probe_result_to_observation`, write append-only rows only, and fail closed if PG env is missing.
- [ ] **Security gate.** Re-run security against live transport and adapter; prove no checkout/login/account paths, no secret leakage, no raw response dumps, dirty cleanup => `ERROR`.
- [ ] **DevOps gate.** Publish/pin `skirmshop-stock-prober` image or intentionally run the prober entrypoint from the same immutable image with an explicit command override; keep `replicas: 0` until live smoke passes.
- [ ] **Egress gate.** Keep prober default-deny until an approved domain-specific egress mechanism is chosen. Standard Kubernetes NetworkPolicy cannot express FQDN allowlists; any public 443 fallback must be accepted as a compensating control and paired with an application-domain guard.
- [ ] **Live smoke gate.** Run one approved AirsoftQuimera sample only after the gates above, verify cleanup and Postgres history, then return to `replicas: 0`.

## PMO Decision
- [blocked] F7 cannot be marked PASS while the prober gate is required and remains in the state above.
- [x] B1+B2 may proceed without production activation. Evidence: B1/B2 checklist explicitly excludes B3 live smoke and keeps prober `replicas=0` / CronJobs `suspend=true`.
- [x] No autonomous broad live cart-probe is approved from current evidence.
- [x] Safe current state is preserved: prober Deployment is live-present but disabled (`replicas=0`), image remains `:pending`, and egress is default-deny.

## Status
- 2026-06-30T01:35:00+02:00 - BLOCKED: prober needs a dedicated implementation/security/devops subcycle before any F7 prober live pass.
- 2026-06-30T02:05:03+02:00 - B1+B2 OPENED: RSO defined the next non-destructive prober subcycle. B3 live smoke and production activation remain blocked until B1+B2 evidence is implemented and audited.
