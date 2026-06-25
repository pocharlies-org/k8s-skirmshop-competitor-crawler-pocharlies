# RHO F4c Target Expansion and Endpoint-Scoped Re-Fingerprint

**Role:** Codex RSO/PMO with delegated `rho-researcher`, `rho-architect`, `rho-backend`, `rho-security`, and `rho-verifier`.
**Scope:** read-only target expansion plus GET-only fingerprint heuristic fix.
**Decision:** **PASS for F4c fingerprint/read-discovery.** Live cart-probe calibration remains **BLOCKED** until an explicit cart-write gate is approved.

## What Changed
- `scripts/fingerprint_domains.py` now computes antibot per endpoint.
- Shopify/Woo platform relief applies only when the data endpoint is HTTP 200, valid JSON shape, and contains no antibot markers.
- Root/homepage antibot is preserved as evidence (`root_antibot`) but no longer poisons a clean Shopify/Woo data endpoint.
- Generic/unknown/html-inferred platforms still use the root antibot.
- Any 403/429/captcha/cloudflare/challenge on the relevant data endpoint is fail-closed to `red`.

## Delegated Evidence
- `rho-researcher`: generated 40 provisional ES/EU airsoft candidates in `/tmp/f4c-candidate-targets.json`; old heuristic found 3 Shopify/Woo with JSON 200 but `red/captcha` due root-page markers.
- `rho-architect`: approved endpoint-scoped antibot as additive/backward-compatible, with fail-closed security invariants.
- `rho-backend`: implemented the script change, added `tests/test_fingerprint_domains.py`, and wrote `backend-fingerprint.report.md`.
- `rho-security`: PASS; confirmed GET-only, fail-closed data endpoint handling, generic/no relief, and that fingerprint green does **not** authorize cart-probe POST.
- `rho-verifier`: PASS; re-ran tests, compileall, diff-check, scope audit, and no-cart grep.

## Codex Re-Run Evidence
Commands:
```text
pytest -q tests/test_fingerprint_domains.py
pytest -q
python3 -m compileall scripts src tests
git diff --check
python3 scripts/fingerprint_domains.py --input data/competitors/target-domains.autopilot.json --output /tmp/f4c-top30-endpoint-scoped.json
python3 scripts/fingerprint_domains.py --input /tmp/f4c-candidate-targets.json --output /tmp/f4c-expanded-endpoint-scoped.json
```

Results:
```text
20 passed in 0.12s
118 passed in 0.42s
compileall exit 0
git diff --check clean
top30: FINGERPRINT_OK 30 {'yellow': 9, 'red': 12, 'green': 9}
expanded: FINGERPRINT_OK 40 {'yellow': 26, 'red': 9, 'green': 5}
```

## GET-Only Green Shopify/Woo Candidates

Top30 after endpoint-scoped re-fingerprint:
```text
novritsch.com             woocommerce  antibot=none  platform_source=endpoint  root_antibot=captcha  root=403  woo=200
silverback-airsoft.com    woocommerce  antibot=none  platform_source=endpoint  root_antibot=captcha  root=200  woo=200
```

Expanded provisional candidates:
```text
airsoftmania.eu           shopify      antibot=none  platform_source=endpoint  root_antibot=captcha  root=200  shopify=200
justbbguns.co.uk          woocommerce  antibot=none  platform_source=endpoint  root_antibot=captcha  root=200  woo=200
socomtactical.net         shopify      antibot=none  platform_source=endpoint  root_antibot=captcha  root=200  shopify=200  crawl_delay=10.0
```

## Security Boundary
- [x] GET product endpoint green means read-only product JSON is crawlable.
- [x] It does **not** authorize live POST cart-probe.
- [x] Root `captcha` remains visible in evidence.
- [x] Live calibration sample-10 remains `[blocked]` until a separate RSO gate approves a specific cart-write target, low limits, honest UA, cleanup verification, and no-checkout log.

## Recommendation
Do not open F6 yet. The next autonomous-safe step is to prepare a live calibration approval dossier for one candidate, preferably one with least cart-write risk. A reasonable order for review:
1. `justbbguns.co.uk` (Woo Store API GET open, root 200, no crawl-delay; cart-write still unverified).
2. `socomtactical.net` (Shopify GET open, crawl-delay 10s; Shopify robots disallow cart/checkout paths, so security review required before any cart POST).
3. `silverback-airsoft.com` / `novritsch.com` only with extra caution because root has captcha/403 history.

## Residual Risks
- Candidates from F4c expansion are business-unvalidated.
- Endpoint-scoped green is a read-tier, not a write-tier.
- `data/competitors/fingerprint.json` is not refreshed in this report; `/tmp` evidence proves the behavior but should be promoted as a separate data artifact if accepted.
