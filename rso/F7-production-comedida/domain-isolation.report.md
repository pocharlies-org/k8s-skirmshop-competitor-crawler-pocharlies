# RHO PMO Report - F7 Domain Isolation

Timestamp: 2026-06-30T10:25:00+02:00

## Objective
- [ ] Prepare a safe path to run clean domains without activating a full tier
  that contains known anti-bot blockers. Evidence pending: released image,
  digest-pinned isolated CronJob, and optional live gate.

## Directives
- [x] Do not activate tier1 or full tier2. Evidence: this subcycle only adds
  runner filtering support; no `suspend=false` change is made here.
- [x] Keep crawler behavior identical when no domain filter is supplied.
  Evidence: existing runner tests still pass.
- [x] Do not crawl blocked domains as part of this preparation. Evidence:
  tests are in-memory; no live Job is launched by this report.

## Acceptance Criteria
- [x] Runner can limit selected tier(s) to configured domain(s). Evidence:
  `src/run_once.py` adds repeatable `--domain`; tests cover tier and `--all`
  filtering.
- [x] Unknown domains fail as usage errors before any crawl. Evidence:
  `tests/test_run_once.py::test_unknown_domain_exits_usage_error`.
- [x] Isolated windows can use a distinct run/metrics label. Evidence:
  `--run-label` is accepted only when a single window remains after filtering;
  tests cover success and rejection.
- [x] No scheduler/crawler/push/history behavior is forked. Evidence:
  `run_selected()` still calls `crawl_tier(tier_name, stores)`.
- [ ] Image with these flags is released and pinned. Evidence pending:
  GitHub Actions release, Harbor digest, manifest pin.
- [ ] Optional `powair6.com` isolated live gate is run from the pinned image.
  Evidence pending: Job logs, SQL, metrics, and post-run safe state.

## Specialist Checks
- [x] **Backend** - scoped CLI filtering only. Evidence:
  `.venv/bin/pytest -q tests/test_run_once.py` -> `42 passed`.
- [x] **Verifier** - regression suite unchanged. Evidence:
  `.venv/bin/pytest -q` -> `246 passed`; `.venv/bin/python -m compileall src tests`
  PASS.
- [ ] **DevOps** - CronJob/digest pin pending after image release.
- [ ] **Security** - live gate pending; blocked domains must not be included.

## Status
- 2026-06-30T10:25:00+02:00 - PREPARED IN CODE: `src.run_once` supports
  domain-filtered execution and isolated run labels. No production schedule was
  opened in this step.
