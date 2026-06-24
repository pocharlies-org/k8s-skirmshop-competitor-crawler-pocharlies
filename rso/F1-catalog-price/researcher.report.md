# Researcher Report - F1 Catalog + Price

## Scope

Read-only PMO research for F1 pilot selection after Claude CLI researcher
invocations hung without output. No product code was edited, no commit/push was
performed by the researcher step, and no competitor cart/checkout/login/account
or write request was made.

## Candidate Evidence

Evidence source: `data/competitors/fingerprint.json` entries with `tier=green`.
Probe method: public GET requests with UA
`skirmshop-rso-f1-preflight/0.1 (+research; read-only)` to `/robots.txt`, `/`,
`/products.json?limit=10`, and `/wp-json/wc/store/v1/products?per_page=10`.

| Domain | robots | home | price_hits | product_hits | Shopify JSON | Woo Store API |
|---|---:|---:|---:|---:|---:|---:|
| `airsoft-legends.nl` | 200 / 763 B | 200 / 254301 B | 67 | 45 | 404 | 404 |
| `airsoft2go.de` | 200 / 14 B | 200 / 108520 B | 8 | 3 | 404 | 404 |
| `leopard.es` | 200 / 3416 B | 200 / 299509 B | 357 | 479 | 404 | 404 |
| `specnaarms.com` | 200 / 99 B | 200 / 250065 B | 21 | 11 | 404 | 404 |
| `waffencenter-gotha.de` | 200 / 104 B | 200 / 10434 B | 0 | 0 | 404 | 404 |

## Pilot Decision

Recommended F1 pilot: `leopard.es`.

Reason: it is a F0 `green` domain with by far the strongest public home-page
catalog/price signal in the preflight (`price_hits=357`, `product_hits=479`,
HTTP 200, large HTML body). It should exercise the F1 `generic_html` adapter
without relying on cart, login, checkout, Shopify JSON, or Woo Store API.

Fallback pilot: `airsoft-legends.nl` (`price_hits=67`, `product_hits=45`).

## Allowed GET URLs Touched

- `https://www.airsoft-legends.nl/robots.txt`
- `https://www.airsoft-legends.nl/`
- `https://www.airsoft-legends.nl/products.json?limit=10`
- `https://www.airsoft-legends.nl/wp-json/wc/store/v1/products?per_page=10`
- `https://www.airsoft2go.de/robots.txt`
- `https://www.airsoft2go.de/`
- `https://www.airsoft2go.de/products.json?limit=10`
- `https://www.airsoft2go.de/wp-json/wc/store/v1/products?per_page=10`
- `https://www.leopard.es/robots.txt`
- `https://www.leopard.es/`
- `https://www.leopard.es/products.json?limit=10`
- `https://www.leopard.es/wp-json/wc/store/v1/products?per_page=10`
- `https://www.specnaarms.com/robots.txt`
- `https://www.specnaarms.com/`
- `https://www.specnaarms.com/products.json?limit=10`
- `https://www.specnaarms.com/wp-json/wc/store/v1/products?per_page=10`
- `https://www.waffencenter-gotha.de/robots.txt`
- `https://www.waffencenter-gotha.de/`
- `https://www.waffencenter-gotha.de/products.json?limit=10`
- `https://www.waffencenter-gotha.de/wp-json/wc/store/v1/products?per_page=10`

## Anti-bot/Risk Notes

- No CAPTCHA/challenge was observed in this preflight.
- All tested JSON endpoints returned 404; F1 should prioritize a robust
  `generic_html` adapter for the pilot while keeping Shopify/Woo extension points.
- The researcher step did not run the local extractor count because the base
  interpreter lacks `bs4`; dependency setup belongs to the backend implementation
  and test step.

## Backend Recommendations

- Implement a dry-run command that accepts `--domain leopard.es` and writes
  `rso/F1-catalog-price/pilot-smoke.json`.
- Keep push to Brain opt-in and disabled for the F1 smoke.
- Preserve stable `source_id` format compatible with existing push payloads:
  `competitor:{domain}:{url}`.
- Count and report discarded/failing candidate product cards so the <20% failure
  criterion can be audited.

## Checklist

- [x] Green candidates evaluated. Evidence: table above from F0 fingerprint and GET preflight.
- [x] Pilot selected: `leopard.es`. Evidence: strongest price/product signal.
- [x] Zero write/cart requests. Evidence: only listed GET URLs were touched.
- [blocked] Live extractor count not run in researcher step. Evidence: base interpreter lacks `bs4`; backend step must create/use dependency environment and produce `pilot-smoke.json`.
