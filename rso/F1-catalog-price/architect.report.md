# Architect Report - F1 Catalog + Price

## Scope

Architecture note for the F1 implementation lane. Claude `rho-architect`
invocations hung without output, so Codex/PMO wrote this documentation-only
report to keep the phase moving. No product code was edited here.

## Contract

F1 needs a small adapter contract for public catalog + price extraction only:

- `list_products(store, *, limit=None) -> list[dict]` or equivalent async API.
- Each product record must include `domain`, `url`, `title`, `price`,
  `source_id`, and optional `brand`, `sku_raw`, `image`, `description`,
  `availability`.
- `source_id` stays stable and compatible with the existing ingest shape:
  `competitor:{domain}:{url}`.
- Push to Brain remains opt-in; the F1 smoke is dry-run only.

## Suggested File Shape

- `src/adapters/base.py` - protocol/base class and shared product normalization.
- `src/adapters/generic_html.py` - F1 pilot implementation using existing
  `fetch_page`, `extract_products`, and safe link discovery.
- Optional extension points only, not mandatory for pilot: `shopify.py`,
  `woocommerce.py`.
- A small CLI/dry-run entrypoint, for example `src/dry_run.py` or a `src.main`
  subcommand, that writes `rso/F1-catalog-price/pilot-smoke.json`.

## Boundaries

F1 must not implement:

- Stock visible semantics (`stock_status`, F2).
- Historical append-only observations (F3).
- Cart-probe, quantity probing, cart cleanup, checkout/login/account (F4).
- `PRODUCT_MATCH` matching (F5).
- Live comparison API behavior (F6).
- CronJob/nocturnal production activation (F7).

## Pilot

Use `leopard.es` as the primary pilot from `researcher.report.md`.
Fallback: `airsoft-legends.nl`.

## Acceptance-Oriented Design

- The dry-run should report both total candidates and successfully normalized
  priced products so `<20%` failure/discard ratio is auditable.
- Tests should cover adapter normalization and at least one HTML fixture with
  multiple product cards/prices.
- External smoke must use GET-only public pages and should be capped by `--limit`
  to avoid broad crawling during F1.

## Checklist

- [x] Adapter contract defined. Evidence: Contract section above.
- [x] F1/F2/F4/F5/F6/F7 boundaries stated. Evidence: Boundaries section above.
- [x] Pilot aligned with researcher evidence. Evidence: `leopard.es` selected from `researcher.report.md`.
- [blocked] No code architecture review from Claude. Evidence: `rho-architect` CLI invocations hung; PMO documentation exception only.
