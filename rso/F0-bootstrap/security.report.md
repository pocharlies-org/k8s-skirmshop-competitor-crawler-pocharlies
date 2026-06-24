# Security Report - F0 Bootstrap

> Role: `rho-security` (delegated implementer/auditor). PMO/verifier: Codex.
> Branch: `codex/competitor-crawler-F0-bootstrap`. Generated (UTC): 2026-06-24.
> Read-only audit. No code changed, no commit/push, **no requests to competitors**.
> This report does **not** assert a global PASS — it covers the security/anti-bot lane only.

## Scope

Security + anti-bot posture review of the F0 bootstrap of `skirmshop-competitor-crawler`.
F0 is documentation/import-only: the existing crawler source was rsync-imported from
`sauvage` into this clone (per `backend.report.md`) and the GitOps deploy wrapper lives
here. My job: verify (a) **zero cart/write requests to competitor domains during F0**,
(b) the **anti-bot/robots posture** the F0 directives demand, and (c) **source-code
security risk** carried by the imported (currently dormant) crawler for future phases.

Inputs read: `researcher.report.md`, `backend.report.md`, `CHECKLIST.md`.
Source/config inspected: `src/{crawler,fetcher,extractor,push_client,scheduler,main}.py`,
`config.yaml`, `Dockerfile`, `docker-compose.yml`, `k8s/manifest.yaml`,
`k8s/externalsecret.yaml`.

## Commands run (read-only)

```bash
# Mandated keyword scan
rg -n 'cart|checkout|login|POST|PUT|DELETE|requests\.post|httpx\.post|client\.post|add\.js|wp-json|products\.json|firecrawl|robots' \
   src tests config.yaml Dockerfile k8s rso/F0-bootstrap/*.report.md
git status --short

# Targeted confirmations
rg -ni 'robotparser|robots\.txt|crawl-delay|crawl_delay|RobotFileParser|captcha|cloudflare|fingerprint|silverback|x-catalog-token|api/competitors' src config.yaml
rg -ni 'add-to-cart|/cart/add|add\.js|cart\.js|\.json\?|/checkout|wp-json|products\.json|\.post\(|\.put\(|\.delete\(' src
```

All commands are `rg`/`git status` only. No network calls to competitor domains were made.

## Evidence

### A. No cart/write requests to competitors during F0 (CONFIRMED)
- **Deployment is dormant:** `k8s/manifest.yaml:8` → `replicas: 0`. The crawler is not
  running in-cluster; no scheduled tier crawl has fired. → zero live egress in F0.
- **F0 work was import + unit tests only:** `backend.report.md` (lines 126-137) shows
  `py_compile` + `pytest 11 passed`; **no live crawl executed**. `git status --short`
  shows only untracked source/report files + a marking edit to `CHECKLIST.md` — no run
  artifacts, no logs of outbound requests.
- **Only outbound `.post()` calls target INTERNAL services, never competitors:**
  - `src/fetcher.py:37` → `fc.post(f"{FIRECRAWL_URL}/v1/scrape", ...)` (internal Firecrawl).
  - `src/push_client.py:30` → `client.post(f"{BRAIN_URL}/instances/{INSTANCE}/push-ingest")`
    (internal brain).
  - Toward competitor domains the code uses **only** `client.get()`
    (`src/crawler.py:51` → `fetch_page` → `src/fetcher.py:23 client.get(url, ...)`).
- **No cart-probe / write primitives exist:** scan for `add-to-cart|/cart/add|add.js|
  cart.js|products.json|wp-json|.put(|.delete(` → **no matches** in `src`. The only
  `/cart`,`/checkout`,`/login` strings are in `src/extractor.py:134` `SKIP_PATH_HINTS`,
  which **exclude** those paths from BFS (`is_product_url()` returns `False`) — the
  opposite of a cart probe.

### B. Anti-bot / robots posture (PARTIAL — code does NOT yet honor robots)
- **Honest User-Agent, no challenge bypass (GOOD):** `src/crawler.py:43`
  `User-Agent: skirmshop-competitor-crawler/1.0 (+research)`. Scan for
  `captcha|cloudflare` → **no matches** (`rc=1`): there is **no CAPTCHA-solving or
  Cloudflare/challenge-evasion code**. Satisfies the directive "UA honesto, sin eludir
  challenges, sin resolver CAPTCHAs".
- **Polite fixed delay:** `src/crawler.py:96` `await asyncio.sleep(0.5)` between fetches.
- **robots.txt / Crawl-delay NOT enforced (GAP):** scan for
  `robotparser|robots.txt|crawl-delay|RobotFileParser` → **no matches** (`rc=1`). The
  imported crawler does **not** fetch or honor `robots.txt` nor any per-host
  `Crawl-delay`; the 0.5s sleep is a hardcoded constant, not robots-derived. The F0
  directive (`CHECKLIST.md:14`) explicitly requires "respetando `robots.txt`/`Crawl-delay`".
- **Fingerprint tiers / `silverback=red` NOT present (GAP):** scan for
  `fingerprint|silverback` → **no matches**. `config.yaml` `tier1/tier2/tier3` are
  **cron schedule cadences**, NOT antibot risk tiers (green/yellow/red), and
  `silverback-airsoft.com` is not in the config at all. The `fingerprint.json`
  green/yellow/red machinery the F0 checklist demands does not exist in the imported
  source (it is architect/implementer future work, out of this dormant code).
- **Net F0 risk = LOW** because `replicas: 0` keeps the crawler from ever issuing live
  requests. The gap becomes a **hard blocker before any live crawl (F1+)**.

### C. Source-code security risk carried by the imported crawler (for future phases)
1. **Unauthenticated write into the brain graph** — `src/push_client.py:30-33` POSTs
   documents to `/instances/{instance}/push-ingest` with **no `Authorization`/token
   header**. Researcher noted `x-catalog-token` guards `GET /api/competitors`, but the
   *push* path here is unauthenticated. Mitigation today: `BRAIN_URL` is a cluster-internal
   ClusterIP Service (`k8s/manifest.yaml:35`). **Residual:** depends on a NetworkPolicy /
   brain-side auth that is unverified here — anyone able to reach the Service can inject
   graph documents. Recommend authn on push-ingest or a NetworkPolicy restricting source.
2. **Hardcoded non-production placeholder Firecrawl key default** — `src/fetcher.py:16`
   and `docker-compose.yml:9` define an `os.getenv("FIRECRAWL_KEY", <placeholder>)`
   fallback literal in source. Low severity (internal Firecrawl, clearly a local
   placeholder, not a real prod secret), but it is a credential literal in the repo.
   Must be overridden in prod via the ExternalSecret and the placeholder must never be
   valid against prod Firecrawl. (Value intentionally not reprinted here.)
3. **Allowlist authority is hardcoded, not the single source of truth** —
   `config.yaml` hardcodes 14 competitor domains; the crawler reads this YAML
   (`src/scheduler.py:16-17 load_config`), **not** Prisma `CompetitorSource` /
   `GET /api/competitors`. This violates the F0 directive "No re-hardcodear dominios"
   (`CHECKLIST.md:15`). Security-relevant because the *authoritative* list of who we may
   lawfully crawl is bypassed; an operator editing YAML could crawl a non-approved domain.
   Reconciliation to the API allowlist is required before phase advance.
4. **Container runs as root, no securityContext** — `Dockerfile` has no `USER` directive
   (runs as UID 0); `k8s/manifest.yaml` sets `automountServiceAccountToken: false` and
   `enableServiceLinks: false` (GOOD) but defines **no** `securityContext`
   (`runAsNonRoot`, `readOnlyRootFilesystem`, `drop ALL capabilities`, `seccompProfile`).
   Hardening gap to close before `replicas > 0`.
5. **Untrusted-input parsing of competitor HTML/JSON-LD** — `src/extractor.py` parses
   attacker-influenced HTML with `BeautifulSoup(html, "html.parser")` (stdlib parser,
   no lxml/XXE/network entity expansion) and `json.loads` wrapped in `try/except`
   (lines 73-77) → reasonable, no obvious RCE/XXE. Extracted strings are forwarded into
   brain documents (`src/crawler.py:62-81` `source_id`/`content`/`metadata`), so this is
   a **stored-content path into the RAG/graph**; bounded (`description[:200]`) but
   downstream sanitization/escaping of competitor-controlled text is advisable. Low risk.

### D. Secrets handling (GOOD)
- `k8s/externalsecret.yaml` sources `competitor-crawler-secrets` from Vault via
  `ClusterSecretStore vault-backend`, `dataFrom extract key secret/skirmshop/competitor-crawler`
  — **no plaintext secrets in manifests**; `manifest.yaml:44-47` `envFrom secretRef optional:true`.
- No secret literals found in `k8s/` or `src/` other than the placeholder noted in C.2.

## Checklist — rho-security scope (`CHECKLIST.md:33`)

### Directives (security-relevant subset)
- [x] **Cero requests de escritura/cart contra competidores en F0.**
  Evidence: §A — `replicas:0`; only `.post()` calls hit internal Firecrawl/brain
  (`fetcher.py:37`, `push_client.py:30`); competitor egress is `client.get` only;
  no cart/add/products.json/wp-json/PUT/DELETE primitives (`rg rc=1`); `/cart`,`/checkout`,
  `/login` only in `extractor.py:134` SKIP list; `git status` shows no run artifacts.
- [x] **UA honesto, sin eludir challenges, sin resolver CAPTCHAs.**
  Evidence: §B — `crawler.py:43` honest UA; `rg captcha|cloudflare` → no matches.
- [x] **Secretos vía ExternalSecret/Vault, no en claro en manifests.**
  Evidence: §D — `externalsecret.yaml` Vault `secret/skirmshop/competitor-crawler`;
  no plaintext secrets in `k8s/`.
- [blocked] **Fingerprint con Firecrawl respetando `robots.txt`/`Crawl-delay`.**
  Blocker: imported source has **no** robots.txt/Crawl-delay enforcement
  (`rg robotparser|robots.txt|crawl-delay` → no matches). Safe in F0 only because
  `replicas:0`; **must be implemented before any live crawl (F1+)**. Not security-exec
  fixable here (F0 is import-only; logic is architect/backend future work).

### Acceptance criteria (rho-security lane)
- [x] **Cero cart/escritura a competidores en F0 — verificado.** Evidence: §A (full).
- [x] **Sin código de evasión de challenges/CAPTCHA.** Evidence: §B (`rg` no matches).
- [x] **Postura de secretos sin literales en manifests (Vault ExternalSecret).** Evidence: §D.
- [x] **Riesgo de código fuente para fases futuras inventariado.** Evidence: §C items 1-5
  (unauth push-ingest, placeholder key, hardcoded allowlist, root container, untrusted HTML).
- [blocked] **`Crawl-delay`/`robots.txt` honrado por el crawler.** Blocker: not implemented
  in code (§B); cannot be marked `[x]` — no evidence exists. Gate before live crawl.
- [blocked] **Tiers antibot green/yellow/red + `silverback-airsoft.com = red`.** Blocker:
  no `fingerprint.json`/tier(green|yellow|red)/`silverback` exists in the F0 source
  (`rg fingerprint|silverback` → no matches). Owned by rho-architect; no security evidence
  to assert. Reported unresolved, not weakened.

### Specialist check
- [x] **rho-security — anti-bot/robots posture + zero cart/write in F0.**
  Scope: read-only audit of imported source + manifests. Files inspected listed under Scope.
  Checks: 4 `rg` scans + `git status` (all read-only). Result for security lane:
  **zero cart/write to competitors in F0 = VERIFIED**; **robots/Crawl-delay + fingerprint
  tiers = NOT MET (blocked)**, safe only due to `replicas:0`. No global PASS asserted.

## Residual security risks
1. **robots.txt / `Crawl-delay` NOT honored in code** — hard gate before `replicas>0`;
   live crawling without it risks ToS/abuse violations. (BLOCKER for F1+, not F0.)
2. **Unauthenticated `push-ingest`** into the brain graph — relies on cluster-internal
   reachability; verify brain-side authn or a restricting NetworkPolicy.
3. **Hardcoded competitor allowlist in `config.yaml`** bypasses the `CompetitorSource`
   authoritative list — an operator could crawl a non-approved domain. Reconcile to
   `GET /api/competitors` before phase advance.
4. **Container runs as root, no `securityContext`** — harden (`runAsNonRoot`,
   `readOnlyRootFilesystem`, drop caps, seccomp) before deployment.
5. **Placeholder Firecrawl key default** in source/compose — ensure prod overrides via
   ExternalSecret; placeholder must be invalid against prod Firecrawl.
6. **Competitor-controlled HTML/text flows into brain documents** — add downstream
   sanitization/escaping; current parser is XXE-safe but content is stored verbatim
   (truncated to 200 chars).
7. **Fingerprint anti-bot tiering (`silverback=red`) absent** — risk classification that
   would prevent crawling CAPTCHA/Cloudflare-protected sites does not yet exist
   (architect scope); without it the crawler has no guardrail against hammering hard
   targets once enabled.

> Verification limits: assessment is static (code/manifests + reports). No runtime/
> NetworkPolicy state was queried, no live crawl observed (correct for F0). Brain-side
> push-ingest authz and cluster NetworkPolicies are **unverified** and listed as residual.
