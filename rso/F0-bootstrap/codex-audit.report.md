# Codex Audit Report - F0 Bootstrap

## Scope

Codex/RSO audit of the F0 execution performed by Claude CLI implementers. This is
not a global F0 PASS. It records verified partial progress and the blockers that
prevent opening F1.

## Claude CLI Roles Run

- `rho-researcher`: produced `rso/F0-bootstrap/researcher.report.md`.
- `rho-backend`: imported the existing crawler source from `sauvage` and produced
  `rso/F0-bootstrap/backend.report.md`.
- `rho-security`: produced `rso/F0-bootstrap/security.report.md`.
- `rho-architect`: first free-form invocation timed out; second invocation wrote
  `rso/F0-bootstrap/architect.report.md` from closed PMO evidence.
- `rho-verifier`: initially blocked by Claude session limit, then rerun
  successfully in the continuation; produced
  `rso/F0-bootstrap/verifier.report.md`.

## PMO Evidence Re-run

- `git diff --check` returned clean before staging.
- Imported source md5 matched `sauvage` for:
  `.gitignore`, `Dockerfile`, `config.yaml`, `docker-compose.yml`,
  `requirements.txt`, `src/*.py`, and `tests/*.py`.
- `python3 -m py_compile src/*.py tests/*.py` succeeded.
- `python3 -m pytest tests/ -q` failed in the base interpreter because `bs4` was
  not installed, then the fallback venv installed `requirements.txt` and
  `pytest`; tests passed: `11 passed in 0.08s`.
- Security report verified no F0 cart/write requests to competitors; deployment
  remains dormant with `replicas: 0`.

## Result

Partial progress is valid to commit:

- Source imported into the local clone.
- Reports created for researcher/backend/security/architect.
- Unit tests pass in an isolated dependency environment.

F0 remains blocked and F1 must not open:

- SimilarWeb MCP is not exposed to Claude CLI, so ranking remains provisional;
  user delegated autopilot PMO curation and the list is recorded in
  `data/competitors/target-domains.autopilot.json`.
- `fingerprint.json` was generated for 30/30 target domains.
- `silverback-airsoft.com = red` is verified in `data/competitors/fingerprint.json`
  (`antibot=captcha`, `http_status=200`).
- `CompetitorSource` has a prepared idempotent migration in `skirmshopshopifyapp`
  commit `e275329`, but the migration has not been applied to a DB in this cycle.
- Brain index code for `CompetitorProduct`/`CompetitorStore` is now implemented
  and pushed in `skirmshop-brain-v2` commit `f53b552` on branch
  `codex/product-recommendations-20260616`, but runtime/Cypher verification or a
  deployed Brain boot has not been performed.
- The imported crawler does not yet honor `robots.txt`/`Crawl-delay` and still
  uses the legacy hardcoded 14-domain config instead of `CompetitorSource`.

## Checklist

- [x] Source import verified. Evidence: md5 local vs `sauvage` matched.
- [x] Tests verified. Evidence: venv pytest `11 passed`.
- [x] Zero F0 cart/write requests verified. Evidence: `security.report.md`.
- [x] F0 marked PARTIAL/BLOCKED, not PASS. Evidence: `CHECKLIST.md`.
- [x] Independent `rho-verifier` report completed. Evidence:
  `rso/F0-bootstrap/verifier.report.md`.
- [blocked: ranking provisional] Autopilot target list prepared but not a final
  SimilarWeb MCP ranking. Evidence:
  `data/competitors/target-domains.autopilot.json` and
  public Similarweb URLs in `source_urls`.
- [blocked: DB not applied] `CompetitorSource` migration prepared, not populated
  in a verified DB. Evidence: `skirmshopshopifyapp` commit `e275329` migration
  artifact.
- [x] Fingerprint gate met for static read-only artifact. Evidence:
  `data/competitors/fingerprint.json` count=30, required fields present,
  `silverback-airsoft.com=red`.
- [blocked: brain runtime verification] Competitor graph index code is
  implemented in `skirmshop-brain-v2` commit `f53b552`, but live index creation
  has not been verified with Cypher/rollout.
