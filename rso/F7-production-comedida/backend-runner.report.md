# F7 Backend Report — bounded one-shot tier runner

**Role:** `rho-backend` (implementer lane, delegated by Codex PMO).
**Date:** 2026-06-27.
**Scope (exact, as assigned):** `src/scheduler.py`, new `src/run_once.py`,
`tests/test_run_once.py`, `tests/test_scheduler.py`, this report + `CHECKLIST.md`.
**Out of scope / untouched:** `k8s/**`, `deploy/prod`, secrets, live network,
`src/main.py` (daemon left intact), Argo, image publish.
**No production activation:** no `kubectl apply`, no CronJob created/unsuspended,
no Brain `push-ingest`, no live crawl.

This implements the architect's required pre-activation gate (`architect.report.md`):
> *"add a one-shot batch entrypoint such as `python -m src.run_tier --tier tier1`
> … A CronJob can then run one bounded batch, exit 0/1, and produce clear job
> history."*

## What was built

`python -m src.run_once` — a bounded runner that runs one or more tiers
*sequentially to completion* and exits with a CronJob-friendly status code,
reusing the existing `crawl_tier` coroutine (identical crawl/push behavior;
only the trigger differs from the cron daemon).

CLI surface:

| Invocation | Behavior |
|---|---|
| `python -m src.run_once --tier tier1` | run a single tier |
| `python -m src.run_once --tier tier2 --tier tier1` | run several, in CLI order |
| `python -m src.run_once --all` | run every configured tier, declaration order |
| `--config /path/config.yaml` | override config path (also env `CONFIG_PATH`, default `/app/config.yaml`) |
| `--fail-on-push-errors` | opt-in: exit non-zero if any doc failed to push |

Exit codes (stable for CronJob backoff/alerting):
`0` = all selected tiers completed · `1` = unhandled crawl error, or push
failures with `--fail-on-push-errors` · `2` = usage/config error (unknown tier,
empty selection, missing/invalid config; also argparse's own bad-usage code).

`--tier` and `--all` are a **required mutually-exclusive** argparse group, so
running with neither (or both) fails fast with exit 2 before any I/O.

`src/scheduler.py::crawl_tier` now **returns `(total_pushed, total_failed)`**
(previously returned `None`). This is additive and backward-compatible:
`build_scheduler` hands `crawl_tier` to APScheduler's `add_job`, which ignores
the coroutine's return value (verified: `grep -rn crawl_tier` shows only
`build_scheduler` and `run_once` as callers). The daemon path (`src.main`) is
unchanged and still imports the unmodified `build_scheduler`/`load_config`.

## RHO Checklist

### Directives
- [x] Stay strictly within assigned scope. Evidence: `git status --porcelain` →
  `M src/scheduler.py`, `?? src/run_once.py`, `?? tests/test_run_once.py`,
  `?? tests/test_scheduler.py` only. No `k8s/**`, `deploy/prod`, `main.py`.
- [x] Do not activate production. Evidence: no `kubectl`/apply/CronJob/Brain
  calls issued; runner is inert code + tests; no manifest references it
  (`grep -rn run_once k8s/` → no matches).
- [x] Root-cause, no workarounds. Evidence: reuses `crawl_tier` instead of
  duplicating crawl/push logic; exit codes are typed constants; errors logged
  explicitly, never swallowed.
- [x] No secrets exposed. Evidence: runner reads no secrets; auth stays in
  `push_client` (`BRAIN_API_KEY`), untouched here.

### Acceptance criteria (from task)
- [x] **(1) `--tier <name>` and `--all`, reading config.yaml / configurable path.**
  Evidence: `src/run_once.py` `parse_args` mutually-exclusive `--tier`(append)/
  `--all` + `--config` (default `CONFIG_PATH` env → `/app/config.yaml`);
  tests `test_run_single_tier`, `test_run_multiple_tier_flags_in_order`,
  `test_run_all_runs_every_tier_in_declaration_order` assert config-path loading.
- [x] **(2) Runs the existing sequential `crawl_tier` and exits when done.**
  Evidence: `run_selected` iterates selected tiers and `await crawl_tier(...)`
  (`src/run_once.py:144`); `main` → `raise SystemExit(run())`; returns `EXIT_OK`
  after completion.
- [x] **(3) Unknown tier → non-zero exit.** Evidence: `_select` returns `None`
  for unknown tiers → `run` returns `EXIT_USAGE_ERROR` (2); test
  `test_unknown_tier_exits_nonzero_and_does_not_crawl` asserts `rc == 2` and
  that `crawl_tier` was never called.
- [x] **(4) Unit tests with no real network — authored & network-free by design.**
  Evidence: `tests/test_run_once.py` (14 tests) monkeypatches `run_once.crawl_tier`;
  `tests/test_scheduler.py` (3 tests) monkeypatches `scheduler.crawl_store` /
  `scheduler.push_documents`. No `httpx`/socket import in either test; zero real
  HTTP. PMO later executed these tests in a temp venv; see PMO verification below.
- [x] **(5) `src.main` daemon kept working.** Evidence: `src/main.py` untouched
  (`git status` shows it unmodified); only consumes `build_scheduler`/`load_config`,
  both unchanged; `crawl_tier` return change is ignored by APScheduler `add_job`.
- [x] **(6) Returns summary, checklist, files, risks, commands.** Evidence: this
  report.

### PMO verification
- [x] **Tests executed green by Codex PMO.** Evidence: the host Python lacked
  `apscheduler`, so Codex created `/tmp/crawler-f7-venv`, installed
  `requirements.txt` plus `pytest`, and ran
  `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `159 passed in 0.41s`.
- [x] **Compile and CLI exit checks passed by Codex PMO.** Evidence:
  `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS;
  `/tmp/crawler-f7-venv/bin/python -m src.run_once --tier nope --config config.yaml`
  exits `2`; `/tmp/crawler-f7-venv/bin/python -m src.run_once --config config.yaml`
  exits `2`.
- [x] **Delegated lane execution blocker documented.** Evidence: the `rho-backend`
  lane could not run Python code execution itself (`python3 -m pytest`,
  `python3 -c`, `python3 -m py_compile` required approval), so PMO supplied the
  green-run evidence.

## Verification commands (for PMO / CI — could not run here)
```bash
cd /home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies
python3 -m py_compile src/run_once.py src/scheduler.py \
    tests/test_run_once.py tests/test_scheduler.py
python3 -m pytest -q                       # full suite, PMO observed 159 passed
python3 -m pytest -q tests/test_run_once.py tests/test_scheduler.py
# functional dry sanity (still no real crawl — unknown tier path):
python3 -m src.run_once --tier nope --config config.yaml ; echo "exit=$?"   # -> 2
python3 -m src.run_once --config config.yaml ; echo "exit=$?"               # -> 2 (no selection)
```

## Files touched
- `src/scheduler.py` — `crawl_tier` now returns `(total_pushed, total_failed)`;
  docstring documents the contract. No behavior change for the daemon.
- `src/run_once.py` — **new** bounded one-shot runner.
- `tests/test_run_once.py` — **new** 14 tests (CLI, selection, exit codes,
  config path, fail-on-push-errors, mutual exclusion, `main`).
- `tests/test_scheduler.py` — **new** 3 tests locking the `crawl_tier` return
  contract + per-store failure isolation.

## Residual risks
- **CI after commit still required** before the branch is considered green after
  this diff; PMO local verification is green.
- **No CronJob wiring done** (out of scope): DevOps must set the CronJob
  `command` to `["python","-m","src.run_once","--tier","tierN"]` (or `--all`),
  `restartPolicy: Never`, low `backoffLimit`, `concurrencyPolicy: Forbid`,
  staggered `schedule` per tier, and pass `BRAIN_API_KEY` +
  `REQUIRE_BRAIN_API_KEY=true`. Until then this is inert.
- **Exit-code policy choice:** push failures do **not** fail the job by default
  (partial degradation is normal); operators opt in with `--fail-on-push-errors`.
  If F7 wants strict alerting on any push loss, enable that flag in the manifest.
- **Config schedule ignored on purpose:** the one-shot path selects tiers
  explicitly and never reads `schedule`; cron timing is owned by the K8s CronJob,
  not `config.yaml`. The daemon (`src.main`) still uses `schedule`.
- Runner does not itself add anti-DoS rails beyond the existing `crawl_store`
  polite-delay/sequential behavior; tier-level rate limits remain a separate F7
  item.
