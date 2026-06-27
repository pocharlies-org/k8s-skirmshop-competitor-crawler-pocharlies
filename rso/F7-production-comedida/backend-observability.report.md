# F7 Backend Report — one-shot crawler observability (opt-in /metrics)

**Role:** `rho-backend` (implementer lane, delegated by Codex PMO).
**Date:** 2026-06-27.
**Objective:** Prepare observability for the one-shot crawler runner **without
activating production** — an optional Prometheus `/metrics` endpoint the future
CronJob can expose, off by default for local/test runs.

**Scope (exact, as assigned):**
- `src/run_once.py` — wire the opt-in endpoint + metric recording.
- `src/metrics_exporter.py` — **new** dependency-free registry + HTTP exposition.
- `tests/test_run_once.py` — extend with metrics-wiring tests.
- `tests/test_metrics_exporter.py` — **new** unit tests.
- This report + `CHECKLIST.md`.

**Out of scope / untouched (verified `git status --porcelain`):** `k8s/**`,
`deploy/prod`, secrets, live network, Argo, image. `src/scheduler.py` was **not**
modified — `crawl_tier` already returns `(pushed, failed)` from the prior F7
runner work, so it is reused as-is. `src/main.py` daemon left intact.

**No production activation:** no `kubectl`, no CronJob created/unsuspended, no
Brain `push-ingest`, no live crawl, no manifest references the endpoint yet.

## What was built

### `src/metrics_exporter.py` (new, stdlib only)
- `CrawlerMetrics` — a thread-safe in-memory registry (lock-guarded; updated from
  the asyncio runner thread, read from the HTTP server thread) exposing exactly
  the four contract families:

  | Metric | Type | Labels |
  |---|---|---|
  | `competitor_crawler_run_total` | counter | `tier`, `status` (`ok`/`error`/`skipped`) |
  | `competitor_crawler_push_sent_total` | counter | `tier` |
  | `competitor_crawler_push_failed_total` | counter | `tier` |
  | `competitor_crawler_run_active` | gauge | `tier` |

- Typed lifecycle API used by the runner: `ensure_tier()` (pre-creates the
  always-present 0 series so a mid-run scrape is meaningful), `start_run()`
  (gauge→1), `finish_run(status, pushed, failed)` (gauge→0 + counters).
- `render()` emits Prometheus text exposition format 0.0.4: `# HELP`/`# TYPE` per
  family in a fixed order, labels sorted, label values escaped (`\`, `"`, `\n`),
  integer values without trailing `.0`, trailing newline.
- `MetricsServer` — a backgrounded `http.server.ThreadingHTTPServer` serving
  `GET /metrics` (200 `text/plain; version=0.0.4`) and `404` for anything else.
  Binds on construction (so a bind failure surfaces to the caller), `start()`
  runs `serve_forever` on a daemon thread, `stop()` shuts down + closes the
  socket. `port` reflects the actually-bound port (useful with `port=0`).

**No `prometheus_client`.** Rationale: short-lived CronJob process exposing four
families, no multiprocess/registry sharing. Mirrors the existing F4 stdlib-only
choice in `src/prober/metrics.py`. `requirements.txt` is unchanged.

### `src/run_once.py` (wiring)
- New CLI flags + env fallbacks, **off by default**:
  - `--metrics-port PORT` / `METRICS_PORT` — enable the endpoint (`0` = ephemeral).
    Unset → endpoint never constructed.
  - `--metrics-linger-seconds SECONDS` / `METRICS_LINGER_SECONDS` — keep `/metrics`
    serving this long after the run so a CronJob run stays scrapeable at the end.
    **Default 0.**
- `run_selected(selected, metrics=None)` records each tier's lifecycle when a
  registry is supplied; with `metrics=None` (the default / disabled path) the
  behavior is byte-for-byte identical to before.
- The endpoint is **pure observability**: a metrics bind failure (`OSError`) is
  logged and the job continues; linger only runs when the server is up; exit-code
  semantics (`0`/`1`/`2`, `--fail-on-push-errors`) are untouched. A tier that
  raises records `status="error"`, resets the gauge, and re-raises so the existing
  abort→exit-1 behavior is preserved.

## RHO Checklist

### Directives
- [x] Stay strictly within assigned scope. Evidence: `git status --porcelain` →
  `M src/run_once.py`, `M tests/test_run_once.py`, `?? src/metrics_exporter.py`,
  `?? tests/test_metrics_exporter.py` only. No `k8s/**`, `deploy/prod`, `main.py`,
  `scheduler.py`.
- [x] Do not activate production. Evidence: no `kubectl`/apply/CronJob/Brain
  calls; endpoint is inert opt-in code; `grep -rn metrics_exporter k8s/` → none.
- [x] Root cause, no workarounds. Evidence: reuses `crawl_tier`'s existing
  `(pushed, failed)` return rather than re-deriving; typed lifecycle API; errors
  logged, never swallowed; metrics never alter control flow.
- [x] No secrets exposed. Evidence: endpoint renders only aggregate counts/gauge
  (tier name + status), no URLs/PII/secrets; runner reads no secrets here.

### Acceptance criteria (from task)
- [x] **(1) Opt-in `/metrics` via `--metrics-port` / `METRICS_PORT`, off by
  default.** Evidence: `src/run_once.py` `parse_args` adds `--metrics-port`
  (default `None`); `_resolve_metrics_port` returns `None` when unset →
  `_maybe_start_metrics` returns `(None, None)` and never constructs the server.
  Tests `test_metrics_disabled_by_default`, `test_metrics_enabled_via_env`,
  `test_metrics_server_started_and_stopped_when_port_given`.
- [x] **(2) Prometheus text format exposing the 4 named families/labels.**
  Evidence: `src/metrics_exporter.py` `_FAMILIES` + `render()`; constants
  `RUN_TOTAL`/`PUSH_SENT_TOTAL`/`PUSH_FAILED_TOTAL`/`RUN_ACTIVE`. Tests
  `test_render_exposes_all_four_required_families`,
  `test_http_endpoint_serves_metrics_over_loopback`.
- [x] **(3) Optional linger via `--metrics-linger-seconds` /
  `METRICS_LINGER_SECONDS`, default 0.** Evidence: `_resolve_linger_seconds`
  (default 0, negative clamped, invalid env → 0); `run()` `finally` sleeps then
  `server.stop()`. Tests `test_metrics_linger_sleeps_then_stops`,
  `test_metrics_no_linger_by_default_does_not_sleep`, `test_metrics_linger_via_env`.
- [x] **(4) No new dependencies.** Evidence: `requirements.txt` unchanged;
  `grep -nE '^(import|from) ' src/metrics_exporter.py src/run_once.py` shows only
  stdlib (`logging`, `threading`, `http.server`, `typing`, `argparse`, `asyncio`,
  `os`, `time`, `pathlib`) + internal `src.*`.
- [x] **(5) Unit tests, no external network (loopback/port 0 only).** Evidence:
  `tests/test_metrics_exporter.py` binds `127.0.0.1:0`; `tests/test_run_once.py`
  metrics tests use a `_FakeServer` (no socket) and monkeypatched
  `crawl_tier`/`time.sleep`. No external host contacted. Authored & network-free
  by construction. **Green-run pending PMO** (see blocker below).
- [x] **(6) Does not break `src.main` daemon nor `run_once` exit codes.**
  Evidence: `src/main.py` untouched; `src/scheduler.py` untouched; the disabled
  path passes `metrics=None` so prior behavior is unchanged; exit-code branches in
  `_run_and_status` are the original logic. Test
  `test_metrics_does_not_change_exit_code_on_push_errors` asserts
  `EXIT_RUNTIME_ERROR` is still returned with `--fail-on-push-errors`.
- [x] **(7) Report with checklist, evidence, risks.** Evidence: this report.

### Verification
- [x] **Tests run green by Codex PMO.** Evidence:
  `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `192 passed in 1.97s`.
- [x] **Compile and manifest dry-run passed by Codex PMO.** Evidence:
  `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS;
  `kubectl apply --dry-run=server -k k8s` PASS.
- [x] **Delegated lane execution blocker documented.** Evidence: the
  `rho-backend` lane could not execute Python itself; PMO supplied the green run.
  Code was statically reviewed in-lane; one real defect was found and fixed
  (`MetricsServer.stop()` would hang via `BaseServer.shutdown()` if
  `serve_forever` was never started -> now only calls `shutdown()` when the
  thread is running).

## Verification commands (for PMO / CI)
```bash
cd /home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies
/tmp/crawler-f7-venv/bin/python -m compileall src/metrics_exporter.py \
    src/run_once.py tests/test_metrics_exporter.py tests/test_run_once.py
/tmp/crawler-f7-venv/bin/python -m pytest -q          # PMO observed 192 passed
/tmp/crawler-f7-venv/bin/python -m pytest -q \
    tests/test_metrics_exporter.py tests/test_run_once.py
# functional sanity (no real crawl): endpoint off by default, on with a port
/tmp/crawler-f7-venv/bin/python -m src.run_once --tier nope --config config.yaml ; echo $?  # 2
# manual scrape (uses a real tier config; ephemeral port + short linger):
#   python -m src.run_once --all --metrics-port 9090 --metrics-linger-seconds 5 --config config.yaml
#   curl -s localhost:9090/metrics | grep competitor_crawler_
```

## Files touched
- `src/metrics_exporter.py` — **new**, stdlib-only registry + HTTP `/metrics`.
- `src/run_once.py` — opt-in metrics wiring (CLI/env flags, resolvers,
  `_maybe_start_metrics`, `_run_and_status`, lifecycle recording in
  `run_selected`); exit-code logic preserved.
- `tests/test_metrics_exporter.py` — **new**, 12 tests (render, escaping, gauge
  toggle, counters, HTTP over loopback, 404, ephemeral port).
- `tests/test_run_once.py` — **new** 21 tests (disabled-by-default, server
  lifecycle, env enable, linger, bind-failure tolerance, exit-code invariance,
  `run_selected` ok/error/skipped recording, resolver edge cases).

## Residual risks
- **CI after commit still required** before the branch is considered green after
  this diff; PMO local verification is green.
- **DevOps wiring still required (out of scope).** The CronJob must set
  `--metrics-port` (or `METRICS_PORT`) + a non-zero `--metrics-linger-seconds`
  (CronJob pods are not long-lived, so a scrape needs the linger window — or a
  push-gateway/textfile-collector alternative), expose a container port, and add a
  `ServiceMonitor`/scrape annotation. Until then the endpoint is inert.
- **Endpoint is unauthenticated** (standard for `/metrics`). It exposes only
  aggregate run counts — no secrets/PII/URLs. Exposure must be bounded by the
  crawler NetworkPolicy at activation (DevOps/Security scope, not activated here).
- **Default bind host is `0.0.0.0`** so an in-cluster Prometheus can reach the pod
  IP; tests bind `127.0.0.1`. If a tighter bind is wanted, add `METRICS_HOST`
  later (not in this scope).
- **Linger blocks the process** for the configured seconds at the end of a run
  (foreground `time.sleep`); keep it small (e.g. 5–15s) so the CronJob finishes
  promptly. Default 0 means no impact unless explicitly enabled.
- **No live night evidence.** This only prepares backend observability; the F7
  "Live night PASS" / Prometheus-scrape verification remain open.
