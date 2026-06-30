# RHO PMO Report - F7 Prober Live Gap

Timestamp: 2026-06-30T01:35:00+02:00

## Objective
- [blocked] Close the F7 stock-prober live gate. B1+B2 are now prepared and safe-disabled, but the gate remains blocked until B3 live smoke/egress is explicitly opened and audited.

## Direct Evidence
- [x] F4 prober primitives exist. Evidence: `src/prober/contract.py`, `src/prober/shopify.py`, `src/prober/woo.py`, `src/prober/generic.py`, `src/prober/service.py`, and tests `tests/test_prober_*`.
- [x] B1 bounded HTTP transport exists. Evidence: `src/prober/http_transport.py`; `tests/test_prober_http_transport.py`; full suite `234 passed`.
- [x] B1 prober runner entrypoint exists. Evidence: `src/prober/run_once.py`; `tests/test_prober_run_once.py`.
- [x] B2 prober runtime is published/pinned safe-disabled. Evidence: `k8s/prober-deployment.yaml` uses `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697` with `command: python -m src.prober.run_once`; live Deployment replicas `0`.
- [blocked] Prober live egress remains default-deny. Evidence: `k8s/prober-networkpolicy.yaml` has `egress: []`.
- [x] One approved custom-domain calibration exists. Evidence: `rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md` records approved `airsoftquimera.com` sample-10 behavior: add path `/cacc_4_50_1_<product_id>_<qty>_0/`, remove path `/cacc_4_50_2_<product_id>_0_0/`, LIMIT(N) response text, cleanup HTTP 200, no 403/429/challenge observed.

## Required Next Sub-Gates
- [x] **Architecture gate scoped for B1+B2.** F7 keeps the prober as required but splits it into non-destructive B1+B2 preparation and a later B3 live smoke. Evidence: `rso/F7-production-comedida/prober-live-B1B2-checklist.md` and `rso/F7-production-comedida/HANDOFF-PROBER-LIVE-B1B2.md`.
- [x] **Backend gate.** Implement only an approved-domain adapter first: `airsoftquimera.com` path-based pattern from F4 evidence, sample <= 10, concurrency 1, low quantity ceiling, honest UA, timeouts, no checkout/login/account/CAPTCHA bypass, and guaranteed cleanup. Evidence: `prober-live-B1B2-backend.report.md`.
- [x] **HTTP transport gate.** Add a bounded `ProbeTransport` implementation with challenge/403/429/503 detection, no raw body logging, no cross-run cookie persistence, and deterministic tests. Evidence: `prober-live-B1B2-backend.report.md`; `prober-live-B1B2-security.report.md`.
- [x] **History gate.** Map `ProbeResult` to F3 `Observation` via `probe_result_to_observation`, write append-only rows only, and fail closed if PG env is missing. Evidence: `tests/test_prober_run_once.py`.
- [x] **Security gate.** Re-run security against live transport and adapter; prove no checkout/login/account paths, no secret leakage, no raw response dumps, dirty cleanup => `ERROR`. Evidence: `prober-live-B1B2-security.report.md`.
- [x] **DevOps gate.** Publish/pin `skirmshop-stock-prober` image or intentionally run the prober entrypoint from the same immutable image with an explicit command override; keep `replicas: 0` until live smoke passes. Evidence: `prober-live-B1B2-devops.report.md`; `prober-live-B1B2-verifier.report.md`.
- [ ] **Egress gate.** Keep prober default-deny until an approved domain-specific egress mechanism is chosen. Standard Kubernetes NetworkPolicy cannot express FQDN allowlists; any public 443 fallback must be accepted as a compensating control and paired with an application-domain guard.
- [ ] **Live smoke gate.** Run one approved AirsoftQuimera sample only after the gates above, verify cleanup and Postgres history, then return to `replicas: 0`.

## PMO Decision
- [blocked] F7 cannot be marked PASS while the prober gate is required and remains in the state above.
- [x] B1+B2 may proceed without production activation. Evidence: B1/B2 checklist explicitly excludes B3 live smoke and keeps prober `replicas=0` / CronJobs `suspend=true`.
- [x] No autonomous broad live cart-probe is approved from current evidence.
- [x] Safe current state is preserved: prober Deployment is live-present but disabled (`replicas=0`), image is immutable digest-pinned, and egress is default-deny.

## Status
- 2026-06-30T01:35:00+02:00 - BLOCKED: prober needs a dedicated implementation/security/devops subcycle before any F7 prober live pass.
- 2026-06-30T02:05:03+02:00 - B1+B2 OPENED: RSO defined the next non-destructive prober subcycle. B3 live smoke and production activation remain blocked until B1+B2 evidence is implemented and audited.
- 2026-06-30T02:42:00+02:00 - B1+B2 PASS: bounded AirsoftQuimera adapter, HTTP transport, runner, history mapping, digest-pinned prober command override and live safe-disabled state verified. F7 remains BLOCKED for B3 live smoke/egress and clean live-night evidence.
