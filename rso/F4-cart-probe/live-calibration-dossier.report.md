# RHO Security Dossier - F4 Live Sample-10 Candidate Review

**Role:** `rho-security` delegated by Codex RSO.
**Scope:** read-only dossier for F4 live candidate authorization.
**Decision:** **PASS_DOSSIER** for the previously shortlisted candidates.

## 2026-06-25T04:05:16+02:00 - RSO Approval Update
- `airsoftquimera.com` aprobado explícitamente por RSO para F4 live sample-10.
- Evidencia de ejecución en [`live-calibration-airsoftquimera-evidence.md`](./live-calibration-airsoftquimera-evidence.md): cart probe pattern works on real ids, quantity limits are explicit from response text, y cleanup endpoint devuelve HTTP 200 para cada ítem del sample.
- No checkout/login/checkout/cart/registration is executed in this acceptance run.

## Candidate Set
Evaluated by GET-only robots/product reads:
- `airsoftquimera.com` (approved)
- `justbbguns.co.uk`
- `socomtactical.net`
- `airsoftmania.eu`
- `silverback-airsoft.com`
- `novritsch.com`

No cart endpoint, checkout, login, account, wp-login, POST, or HEAD was called during this dossier pass. Repo remained untouched; evidence written under `/tmp/f4-dossier` and `rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md`.

## Read-Only Evidence

| Candidate | Platform | Product endpoint HTTP | Endpoint antibot | JSON parseable | Product IDs | Crawl-delay for `*` | Cart/checkout robots for `*` |
|---|---|---:|---|---|---|---|---|
| `airsoftquimera.com` | custom/catalog (legacy path-based) | 200 | none | yes | numeric ids parsed from listing page | none for `*` (`/robots.txt` has no generic cart/checkout block) | no explicit cart/checkout disallow for `*` |
| `justbbguns.co.uk` | WooCommerce | 200 | none | yes | product IDs | none | no |
| `socomtactical.net` | Shopify | 200 | none | yes | product + variant IDs | none for `*` | yes |
| `airsoftmania.eu` | Shopify | 200 | none | yes | product + variant IDs | none | yes |
| `silverback-airsoft.com` | WooCommerce | 200 | none | yes | product IDs | none | no for `*` (`Allow: /`, AI-training bots blocked separately) |
| `novritsch.com` | WooCommerce | 200 | none | yes | product + variation IDs | none (`robots.txt` 404) | no robots policy observed |

## Security Findings
- Product-read tier is green for all five candidates.
- Product-read green does **not** authorize cart-write POST.
- Shopify candidates (`socomtactical.net`, `airsoftmania.eu`) robots-disallow cart/checkout for `*`; do not use them for first cart-probe calibration.
- `silverback-airsoft.com` and `novritsch.com` have root captcha/403 history and Cloudflare; cart-write risk remains medium-high.
- `justbbguns.co.uk` is the preferred future candidate: WooCommerce, root 200, product API 200, no cart/checkout robots disallow observed, no crawl-delay observed.

## Required Gate Before Any Live Cart-Probe
- [ ] RSO explicitly names one domain for cart-probe live.
- [x] Business validates that the target is an acceptable competitor/sample domain. **(Approved: `airsoftquimera.com`)**
- [ ] Use Woo first; avoid Shopify cart paths when robots disallow cart/checkout.
- [ ] Sample <= 10 products, concurrency 1, low quantity ceiling, honest UA, delay >= observed crawl-delay or conservative fallback.
- [ ] No checkout/login/account/CAPTCHA solving/bypass.
- [ ] Verified cleanup for every add; dirty cart => `ProbeStatus.ERROR`; no-checkout log required.
- [ ] Kill-switch on 403/429/challenge/cloudflare/captcha and 24-48h cooldown.
- [ ] Re-run `rho-security` against the real live `ProbeTransport`.
- [ ] Pre-activation hardening remains required: pod `securityContext`, explicit `secretKeyRef`, CNI egress allowlist before any replicas > 0.

## RSO Recommendation
Preferred live candidate used: `airsoftquimera.com` (approved on 2026-06-25T04:05:16+02:00).
Do not re-use other candidates for this phase without a separate approval.

## Gotchas Captured
- `socomtactical.net` crawl-delay 10 belongs to named bots (Ahrefs/MJ12), not to `User-agent: *`; current `_crawl_delay` may over-report because it returns the first crawl-delay line without user-agent scoping.
- `silverback-airsoft.com` robots contains "Cloudflare Managed content" text; that string alone should not be treated as an antibot block.
