# F7 Backend Report - crawler domain egress guard

**Role:** `rho-backend` implementer lane produced the core code diff but returned no report after repeated CLI stalls.  
**PMO exception:** Codex/RSO added the network-free tests and this evidence report because Claude CLI attempts for tests/report repeatedly exited without output. Product logic was limited to the Claude-produced diff plus PMO verification.
**Date:** 2026-06-27.

## Objective

Close the crawler-side substring egress bug before any production activation:
`domain in parsed.netloc` allowed hosts such as `evilgunfire.com` or
`gunfire.com@evil.com` for a configured `gunfire.com` store.

This is an application guard only. The cluster still needs a real egress control
for approved competitor domains before activation, because the live cluster
currently exposes only standard Kubernetes `NetworkPolicy`, not Cilium/FQDN
policy.

## Changes

- `src/egress_guard.py`
  - New stdlib-only guard.
  - Allows only `http`/`https`.
  - Allows exact configured host or dot-delimited subdomain.
  - Uses `urlsplit().hostname`, so userinfo/port tricks do not pass.
  - Rejects suffix/prefix spoofing (`evilgunfire.com`,
    `gunfire.com.evil.com`) and non-HTTP schemes.
- `src/fetcher.py`
  - `fetch_page(client, url, domain=None)` remains backward compatible.
  - When `domain` is supplied, forbidden URLs return `None` before direct fetch
    or Firecrawl fallback.
  - Final post-redirect URL is checked; off-domain redirect bodies are discarded
    and Firecrawl is not called for that URL.
- `src/crawler.py`
  - Passes the store domain into `fetch_page`.
  - BFS link enqueue now uses `is_allowed_url(full, domain)` instead of
    substring matching.
- `tests/test_crawler_egress_guard.py`
  - Network-free tests for exact/subdomain allow, suffix/prefix/userinfo/scheme
    deny, pre-fetch block, off-domain redirect block, off-domain start URL, and
    BFS filtering.

## RHO checklist

### Directives

- [x] No live traffic. Evidence: all new tests use fakes/monkeypatches; no real
  HTTP calls.
- [x] No production activation. Evidence: no `k8s/**`, Argo, secrets, image tags
  or `deploy/prod` changes in this gate.
- [x] Preserve backward compatibility. Evidence: `fetch_page` keeps `domain=None`
  default and existing suite passes.
- [x] Document PMO exception. Evidence: this report records Claude CLI stalls and
  PMO test/evidence completion.

### Acceptance criteria

- [x] URL target is `http`/`https` and exact store host or safe subdomain before
  direct fetch or Firecrawl. Evidence: `src/egress_guard.py`;
  `tests/test_crawler_egress_guard.py::test_is_allowed_url_*`.
- [x] Redirects off-domain are blocked. Evidence:
  `test_fetch_page_discards_off_domain_redirect_without_firecrawl`.
- [x] BFS has no substring matching. Evidence: `src/crawler.py` uses
  `is_allowed_url`; `test_crawl_store_bfs_rejects_evil_suffix_and_userinfo`.
- [x] Off-domain `start_url` fails closed without network. Evidence:
  `test_crawl_store_off_domain_start_url_does_not_fetch`.
- [x] Firecrawl fallback is not called for prohibited URLs. Evidence:
  `test_fetch_page_blocks_forbidden_url_before_direct_or_firecrawl`.
- [x] Full suite remains green. Evidence:
  `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 198 passed.

### Specialist checks

- [blocked] `rho-backend` report: Claude CLI produced code changes but no stdout
  report/checklist after repeated attempts.
- [x] Codex/RSO verification pass. Evidence: targeted tests 6 passed, full suite
  198 passed, compileall PASS, `kubectl apply --dry-run=server -k k8s` PASS,
  `git diff --check` PASS.

## Evidence commands

```bash
/tmp/crawler-f7-venv/bin/python -m pytest -q tests/test_crawler_egress_guard.py
# 6 passed in 0.14s

/tmp/crawler-f7-venv/bin/python -m pytest -q
# 198 passed in 1.92s

/tmp/crawler-f7-venv/bin/python -m compileall src tests
# PASS

kubectl apply --dry-run=server -k k8s
# PASS, including 3 suspended CronJobs and VMPodScrape

git diff --check
# PASS
```

## Residual risks

- This is not a full cluster egress allowlist. Standard Kubernetes
  `NetworkPolicy` cannot express FQDN allowlists; activation still needs an
  egress proxy, Cilium/FQDN-capable policy, or another approved control.
- The guard prevents off-domain fetches initiated by the crawler. It does not
  replace DNS/egress network enforcement.
- Prober live transport remains disabled and still needs its own domain-specific
  allowlist before any cart-probe activation.
