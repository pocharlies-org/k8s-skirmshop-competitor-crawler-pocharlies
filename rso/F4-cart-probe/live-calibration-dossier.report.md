# RHO Security Dossier - F4 Live Sample-10 Candidate Review

**Role:** `rho-security` delegated by Codex RSO.
**Scope:** read-only dossier for possible future F4 live sample-10 approval.
**Decision:** **PASS_DOSSIER**. Live cart-probe remains **BLOCKED / NOT AUTHORIZED**.

## Candidate Set
Evaluated by GET-only robots/product API reads:
- `justbbguns.co.uk`
- `socomtactical.net`
- `airsoftmania.eu`
- `silverback-airsoft.com`
- `novritsch.com`

No cart endpoint, checkout, login, account, wp-login, POST, or HEAD was called. Repo remained untouched by the delegated security lane; evidence was written only under `/tmp/f4-dossier`.

## Read-Only Evidence

| Candidate | Platform | Product endpoint HTTP | Endpoint antibot | JSON parseable | Product IDs | Crawl-delay for `*` | Cart/checkout robots for `*` |
|---|---|---:|---|---|---|---|---|
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
- [ ] Business validates that the target is an acceptable competitor/sample domain.
- [ ] Use Woo first; avoid Shopify cart paths when robots disallow cart/checkout.
- [ ] Sample <= 10 products, concurrency 1, low quantity ceiling, honest UA, delay >= observed crawl-delay or conservative fallback.
- [ ] No checkout/login/account/CAPTCHA solving/bypass.
- [ ] Verified cleanup for every add; dirty cart => `ProbeStatus.ERROR`; no-checkout log required.
- [ ] Kill-switch on 403/429/challenge/cloudflare/captcha and 24-48h cooldown.
- [ ] Re-run `rho-security` against the real live `ProbeTransport`.
- [ ] Pre-activation hardening remains required: pod `securityContext`, explicit `secretKeyRef`, CNI egress allowlist before any replicas > 0.

## RSO Recommendation
Preferred future live candidate: `justbbguns.co.uk`.

Do not execute the live sample-10 cart-probe yet. The project now has a dossier and a preferred candidate, but the F4 acceptance item remains blocked until the user/RSO explicitly approves a named cart-write probe.

## Gotchas Captured
- `socomtactical.net` crawl-delay 10 belongs to named bots (Ahrefs/MJ12), not to `User-agent: *`; current `_crawl_delay` may over-report because it returns the first crawl-delay line without user-agent scoping.
- `silverback-airsoft.com` robots contains "Cloudflare Managed content" text; that string alone should not be treated as an antibot block.
