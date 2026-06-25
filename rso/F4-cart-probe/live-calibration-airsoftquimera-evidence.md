# F4 Live Calibration Evidence - airsoftquimera.com

Timestamp: 2026-06-25T04:05:16+02:00

## Scope
- Domain approved by RSO for F4 live sample-10 cart-probe run.
- Read-only checks + live probe pattern tests, no checkout/login executed.

## Readiness Checks (evidence captured via curl)
- `curl -sSL https://www.airsoftquimera.com/robots.txt` => HTTP 200.
- `/robots.txt` for `User-agent: *` contains:
  - `Disallow: /tunel-ht-4-50/`
  - `Disallow: /reg-4-50/`
  - `Disallow: /login-4-50/`
  - `Disallow: /c-4-50-1/`
  - `Disallow: /md-4-50-mis_datos/`
  - `Disallow: /c-4-50-1-productos/`
  - other dated listing disallow patterns; **no cart/checkout path explicitly disallowed**.
- `curl -I https://www.airsoftquimera.com/sitemaps/sitemap_4_50.xml` => HTTP 200.
- Product list page `https://www.airsoftquimera.com/8fields-lp-4-50-marca-4/` cache downloaded and parsed.

## Probe Pattern / Path Behavior
- Product add URL pattern observed: `/cacc_4_50_1_<product_id>_<qty>_0/`.
- Remove URL tested: `/cacc_4_50_2_<product_id>_0_0/`.

## Sample-10 Calibration Results
IDs are real product ids extracted from the chosen sample page.

| product_id | visible_stock_label | q1 | q2 | q5 | q10 | inferred_max_stock |
|---|---|---|---|---|---|---:|
| 22046 | ÚLTIMAS UNIDADES | ADDED | LIMIT(1) | LIMIT(1) | LIMIT(1) | 1 |
| 22024 | EN STOCK | ADDED | ADDED | ADDED | LIMIT(6) | 6 |
| 19037 | EN STOCK | ADDED | ADDED | LIMIT(4) | LIMIT(4) | 4 |
| 19046 | EN STOCK | ADDED | ADDED | LIMIT(4) | LIMIT(4) | 4 |
| 19039 | EN STOCK | ADDED | ADDED | LIMIT(3) | LIMIT(3) | 3 |
| 18188 | EN STOCK | ADDED | ADDED | LIMIT(2) | LIMIT(2) | 2 |
| 13041 | EN STOCK | ADDED | ADDED | LIMIT(4) | LIMIT(4) | 4 |
| 17663 | EN STOCK | ADDED | ADDED | LIMIT(2) | LIMIT(2) | 2 |
| 17531 | EN STOCK | ADDED | ADDED | LIMIT(3) | LIMIT(3) | 3 |
| 13035 | ÚLTIMAS UNIDADES | ADDED | LIMIT(1) | LIMIT(1) | LIMIT(1) | 1 |

### Detailed evidence notes
- For ids where response text contains `Producto añadido a su selección`, probe state classified as `ADDED`.
- For quota exhaustion, response contains `No tenemos tantas unidades en stock de ese producto` and `Actualmente tenemos en stock N`.
- **No 403/429/Cloudflare/challenge observed** in sample-10 execution.

## Cleanup Evidence
- For each probed id, `/cacc_4_50_2_<id>_0_0/` returned HTTP 200 (`cleanup_http=200`), confirming cart-clear attempts are reachable and executed for all 10 products.
