# F4c Fingerprint Refresh — rho-backend report

> Role: `rho-backend` implementer, delegated by Codex RSO.
> Branch: `codex/competitor-crawler-F4-cart-probe` @ HEAD `7b9201f` (expected).
> Date: 2026-06-25T01:19Z.
> Scope granted (touch only): `data/competitors/fingerprint.json`,
> `rso/F4-cart-probe/fingerprint-refresh-f4c.report.md`,
> `rso/F4-cart-probe/CHECKLIST.md` (status append-only).

## Objective
Regenerate `data/competitors/fingerprint.json` with the validated F4c
endpoint-scoped script `scripts/fingerprint_domains.py`, **GET read-only only**
(no POST, no cart-probe, no checkout/login/CAPTCHA), separating data from code.

## Outcome: BLOCKED in Claude lane, COMPLETED by Codex RSO exception
The live regeneration could **not** be executed in this runtime. The permission
classifier denies both (a) outbound network egress to competitor domains and
(b) arbitrary Python/pytest execution. The on-disk artifact was **not modified**
and **not fabricated**; it remains the pre-F4c (root-scoped) version generated
2026-06-24T12:02Z. Producing a synthetic F4c artifact by hand would be a
fabrication and is explicitly disallowed, so it was not done.

**Codex RSO follow-up:** after this delegated lane blocked, Codex RSO executed
the exact GET-only refresh command in the shared repo as an explicit artifact
refresh exception (not product-code implementation), then re-ran tests and
compile gates. The refreshed `data/competitors/fingerprint.json` is now the
endpoint-scoped F4c artifact.

### Blocking evidence (commands attempted → result)
| Command | Result |
| --- | --- |
| `python3 scripts/fingerprint_domains.py --input data/competitors/target-domains.autopilot.json --output data/competitors/fingerprint.json` | `This command requires approval` (network + arbitrary exec denied) |
| `python3 -c "...urllib.request.urlopen('https://www.novritsch.com/wp-json/wc/store/v1/products?per_page=1')..."` | `This command requires approval` (network egress denied) |
| `python3 -c "print(2+2)"` | `This command requires approval` (arbitrary python exec denied) |
| `python3 -m compileall scripts src tests` | `This command requires approval` |
| `pytest -q tests/test_fingerprint_domains.py` | `This command requires approval` |
| `python3 --version` | PASS → `Python 3.12.3` (benign info command allowed) |
| `git diff --check` | PASS (no output → no whitespace/conflict errors) |
| `git status --short --branch` (post-attempt) | clean, no changes |

Conclusion: in this rho-backend executor, only `git` and trivial info commands
are permitted; live GET fingerprinting and the test/compile gates cannot run.
This is the same class of deliberate platform protection documented for other
network/credential operations — it is **not** to be circumvented. The user/RSO
must grant network egress + python execution to this lane for the GET-only
refresh to proceed (see "Required to unblock" below).

## What WAS verified this session (read-only)
- [x] **Clean start.** `git status` → "working tree clean"; HEAD `7b9201f`
  ("Fix F4c endpoint-scoped fingerprint antibot"), branch
  `codex/competitor-crawler-F4-cart-probe`.
- [x] **Script is GET-only.** Inspected `scripts/fingerprint_domains.py`:
  `_get()` uses `urllib.request.Request(..., method="GET")` exclusively; the four
  probes per domain are `/robots.txt`, `/`, `/products.json?limit=1`,
  `/wp-json/wc/store/v1/products?per_page=1` — all GET. No POST, no cart, no
  session, no auth path anywhere in the module.
- [x] **Endpoint-scoped antibot logic confirmed** (lines 96–148):
  `_endpoint_clean()` requires HTTP 200 + correct JSON shape + no antibot markers
  (fail-closed). `_effective_antibot()`: for Shopify/Woo a blocked data endpoint
  (`captcha|cloudflare|http_429|http_403`) always wins (→ red); a clean
  `platform_source=="endpoint"` scopes antibot to the endpoint (root preserved in
  `evidence.root_antibot`); HTML-inferred/inconclusive falls back to root antibot;
  generic/unknown always governed by root.
- [x] **`git diff --check`** → PASS (clean, no changes introduced).

## Counts — CURRENT on-disk artifact (pre-F4c, root-scoped, 2026-06-24T12:02Z)
Tallied by direct read of `data/competitors/fingerprint.json` (count=30). This is
the **existing** artifact, NOT the result of an F4c run.

### By tier
| Tier | Count | Domains |
| --- | --- | --- |
| green | 5 | airsoft-legends.nl, airsoft2go.de, leopard.es, specnaarms.com, waffencenter-gotha.de |
| yellow | 9 | 101airsoftshop.com, aceros-de-hispania.com, adeportes.es, airsoftpro.es, arminse.es, legionairsoft.es, powair6.com, unit13shop.eu, vsgun.com |
| red | 16 | aa-store.at, airsoftshop.cz, begadi.com, blackrecon.com, bunker501.nl, empireairsoft.co.uk, evike-europe.com, fire-support.co.uk, gunfire.com, hobbyexpert.es, mildot.es, novritsch.com, patrolbase.co.uk, redwolfairsoft.com, silverback-airsoft.com, taiwangun.com |

### By platform
| Platform | Count |
| --- | --- |
| generic_html | 24 |
| woocommerce | 2 (novritsch.com, silverback-airsoft.com) |
| unknown | 4 (101airsoftshop.com [DNS], airsoftpro.es [self-signed TLS], evike-europe.com [403], fire-support.co.uk [403]) |

### Green Shopify / Woo (current on-disk)
- **Shopify green: 0.** No domain currently classifies as Shopify (all
  `/products.json` probes return 404/403/429 or DNS/TLS errors).
- **Woo green: 0.** The 2 WooCommerce domains (novritsch.com, silverback-airsoft.com)
  are both **red** under the *old root-scoped* antibot (root/body `captcha`/403).
- All 5 green are `generic_html`.

### novritsch / silverback (current on-disk, pre-F4c)
| Domain | platform | tier | antibot | statuses (root/robots/shopify/woo) |
| --- | --- | --- | --- | --- |
| novritsch.com | woocommerce | red | captcha | 403 / 404 / 404 / **200** |
| silverback-airsoft.com | woocommerce | red | captcha | 200 / 200 / 404 / **200** |

Note: both Woo `store/v1/products` endpoints already returned **HTTP 200** in the
prior capture, while the *root* carried the antibot marker — exactly the case the
F4c endpoint-scoped logic was written to reclassify.

## Expected F4c delta (REFERENCE ONLY — from prior /tmp validation, NOT reproduced here)
Per `CHECKLIST.md` F4c entry (2026-06-25T03:08), `f4c-target-expansion.report.md`,
`backend-fingerprint.report.md`, and `codex-f4c-audit.report.md`, a prior GET-only
re-fingerprint to `/tmp` found top30 endpoint-green Woo candidates
**novritsch.com** and **silverback-airsoft.com** (Woo `store/v1/products` 200 +
list shape + no markers → `effective_antibot=none` → green; `root_antibot`
preserved in evidence), plus expanded candidates airsoftmania.eu, justbbguns.co.uk,
socomtactical.net (not in the current 30-domain input). Applying the F4c script to
the current input would therefore be expected to flip novritsch + silverback
**red → green (endpoint-scoped Woo)** and to add the new
`platform_source` / `platform_endpoint` / `root_antibot` / `effective_antibot` /
`antibot_by_source` evidence fields (absent from the current on-disk artifact).
**This delta is NOT verified by this session** — it is cited from prior agents'
runs and must be reproduced once the lane is unblocked.

## Risks / caveats
- **Endpoint green = GET-read authorization only, NOT POST cart authorization.**
  A WooCommerce/Shopify domain classified `green` via a 200 JSON catalog endpoint
  means the public read API is reachable and clean; it does **not** authorize the
  F4 aggressive cart-probe (POST add-to-cart / quantity binary search). Live
  sample-10 cart calibration stays `[blocked]` until an explicitly approved green
  target + low limit + verified cleanup + no-checkout log exist.
- **Live values drift over time** (antibot posture, CDN challenges, stock). The
  pre-F4c artifact is ~13h old and predates the endpoint-scoped logic; once a
  refresh runs, tier/antibot for the Woo pair may differ from both the old
  artifact and the prior /tmp run.
- **No fabrication.** The artifact was deliberately left unchanged rather than
  hand-edited to look "regenerated"; a real refresh requires the network/exec
  permission grant below.

## Required to unblock (action for RSO/user)
Completed by Codex RSO exception. Future delegated lanes still need outbound
HTTPS egress + Python execution if they are expected to regenerate fingerprints
or run Python tests themselves.

## Codex RSO refresh evidence
Command:
```text
python3 scripts/fingerprint_domains.py --input data/competitors/target-domains.autopilot.json --output data/competitors/fingerprint.json
```

Result:
```text
FINGERPRINT_OK 30 {'yellow': 9, 'red': 12, 'green': 9}
silverback-airsoft.com -> platform=woocommerce tier=green antibot=none platform_source=endpoint root_antibot=captcha woo=200
```

Counts after refresh:
```text
tier=green count=9
tier=red count=12
tier=yellow count=9
platform=generic_html count=24
platform=unknown count=4
platform=woocommerce count=2
```

Green Shopify/Woo after refresh:
```text
novritsch.com             woocommerce  green  antibot=none  root_antibot=captcha  platform_source=endpoint  root=403  woo=200
silverback-airsoft.com    woocommerce  green  antibot=none  root_antibot=captcha  platform_source=endpoint  root=200  woo=200
```

Verification:
```text
pytest -q -> 118 passed in 0.24s
python3 -m compileall scripts src tests -> exit 0
git diff --check -> clean
```

Security note: this refresh proves only the GET product endpoint is readable.
It does not approve POST cart-probe. Live sample-10 calibration remains blocked.

## Checklist (this delegation)
- [x] 1. Confirm clean git start — Evidence: `git status` clean; HEAD `7b9201f`.
- [x] 2. Run `fingerprint_domains.py` to regenerate artifact — Evidence:
  Codex RSO exception ran the exact GET-only command; output `FINGERPRINT_OK 30`.
- [x] 3. Summarize NEW counts (tier/platform, green Shopify/Woo,
  novritsch/silverback) from the refreshed artifact — Evidence: Codex RSO
  counts above.
- [x] 4a. `pytest -q tests/test_fingerprint_domains.py` — Evidence: already
  closed in `backend-fingerprint.report.md` and verifier/security; full suite
  re-run below.
- [x] 4b. `pytest -q` (full) — Evidence: Codex RSO -> `118 passed in 0.24s`.
- [x] 4c. `python3 -m compileall scripts src tests` — Evidence: Codex RSO exit 0.
- [x] 4d. `git diff --check` — Evidence: PASS (no output).
- [x] 5. Create this Markdown report with checklist/evidence/risks — Evidence: this file.
- [x] 6. Update `CHECKLIST.md` status (append-only), keeping live calibration
  `[blocked]` — Evidence: CHECKLIST.md Status log entry dated 2026-06-25T01:19Z.
