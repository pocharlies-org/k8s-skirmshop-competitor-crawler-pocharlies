# RHO F4b Target Discovery - Cart-Probe Calibration

**Role:** Codex RSO/PMO with delegated `rho-researcher`.
**Scope:** read-only target discovery for F4 live sample-10 calibration.
**Decision:** **BLOCKED**. No safe green Shopify/Woo candidate exists in the current top-30 competitor list.

## Objective
Find an approved green Shopify/Woo target for F4 live calibration, or prove the blocker with reproducible evidence.

## Directives
- [x] No cart-probe live. Evidence: only `scripts/fingerprint_domains.py` was run; it performs public GET requests and writes only to `/tmp`.
- [x] No checkout/login/CAPTCHA solving/POST/external writes. Evidence: script scan found one request builder with `method="GET"` and one `urlopen`; no `POST`, no `data=`, no cart/checkout/login endpoint actions.
- [x] Do not open F6 while calibration remains blocked. Evidence: `CHECKLIST.md` Objective and calibration criterion remain `[blocked]`.

## Evidence From Current Artifact
Source: `data/competitors/fingerprint.json` (`count=30`, generated 2026-06-24T12:02:19Z).

Tier counts:
```text
tier=green count=5
tier=red count=16
tier=yellow count=9
```

Platform counts:
```text
platform=generic_html count=24
platform=unknown count=4
platform=woocommerce count=2
```

Green domains:
```text
airsoft-legends.nl        generic_html  none  true
airsoft2go.de             generic_html  none  false
leopard.es                generic_html  none  true
specnaarms.com            generic_html  none  false
waffencenter-gotha.de     generic_html  none  false
```

Shopify/Woo domains:
```text
novritsch.com             woocommerce   red   captcha  403
silverback-airsoft.com    woocommerce   red   captcha  200
```

Intersection `tier=green AND platform in {shopify, woocommerce}`: empty.

## Script Safety Review
Command:
```text
rg -n "method=|urlopen|Request|POST|cart|checkout|login|data=|requests|httpx|aiohttp|cookie|password|captcha" scripts/fingerprint_domains.py
```

Relevant output:
```text
34: urllib.request.Request(..., method="GET")
36: urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX)
72: "captcha" body marker detection
107: "add to cart" body marker detection
```

Conclusion: `scripts/fingerprint_domains.py` is GET-only fingerprinting. The `captcha` and `add to cart` strings are content detectors, not actions.

## Codex Re-Run
Command:
```text
python3 scripts/fingerprint_domains.py --input data/competitors/target-domains.autopilot.json --output /tmp/f4b-fingerprint-refresh-codex.json
```

Output:
```text
FINGERPRINT_OK 30 {'yellow': 9, 'red': 16, 'green': 5} ... silverback-airsoft.com ... platform='woocommerce' tier='red' antibot='captcha'
```

Drift comparison:
```text
jq -S '[.fingerprints[] | {domain,tier,platform,antibot,http_status}]' data/competitors/fingerprint.json > /tmp/f4b-committed.summary.json
jq -S '[.fingerprints[] | {domain,tier,platform,antibot,http_status}]' /tmp/f4b-fingerprint-refresh-codex.json > /tmp/f4b-refresh.summary.json
diff -u /tmp/f4b-committed.summary.json /tmp/f4b-refresh.summary.json
```

Result: no diff.

Refresh intersection `tier=green AND platform in {shopify, woocommerce}`: empty.

Refresh Shopify/Woo domains:
```text
novritsch.com             woocommerce   red   captcha  403
silverback-airsoft.com    woocommerce   red   captcha  200
```

## Delegated Researcher Result
`rho-researcher` independently inspected the same artifacts, verified the script as GET-only, ran a refresh to `/tmp/f4b-fingerprint-refresh.json`, found no drift, and returned **BLOCKED**.

## RSO Decision
- [blocked] Safe green Shopify/Woo live calibration target exists. Blocker: none in current top-30.
- [x] F4 mock/dry-run artifacts remain acceptable as disabled code.
- [x] F6 remains closed.

## Valid Unblock Paths
1. Expand and business-validate the competitor target list to source a genuine green Shopify/Woo domain, then run limited sample-10 calibration with cleanup evidence.
2. Amend the master acceptance criteria to accept mock-only F4 and move live calibration to a named later phase before production activation.

## Residual Risk
The fingerprint heuristic can false-negative a Shopify/Woo storefront if anti-bot blocks its JSON endpoint. In the current data, the five green domains return clean generic signatures, while the only Woo domains are explicitly red/captcha.
