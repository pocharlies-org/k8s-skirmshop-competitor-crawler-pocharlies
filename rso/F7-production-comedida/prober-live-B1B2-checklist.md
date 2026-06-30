# RHO Checklist - F7 Prober Live B1+B2

Timestamp: 2026-06-30T02:05:03+02:00

## Objective
- [x] Close the non-destructive F7 prober live preparation gate with **B1+B2 only**: B1 backend live-prober implementation for the single approved domain `airsoftquimera.com`, and B2 DevOps/release wiring in a safe-disabled state. Evidence: B1 reports/tests; B2 release digest `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`; Argo/live disabled verification in verifier report.

## Directives
- [x] Codex is RSO/PMO only for this subcycle; no product-code implementation in this artifact. Evidence: this file defines scope, gates and evidence only.
- [x] Codex/PMO implements directly in this turn per active harness after `git fetch` + rebase. Evidence: branch up to date before edits; B1 reports below; no Claude CLI used in this turn.
- [x] Do **not** run broad live cart-probe or unsuspend CronJobs/replicas. Evidence: no live prober Job executed; live prober/crawler Deployments remain `replicas=0`; CronJobs remain `suspend=true`.
- [x] Use only the already evidenced AirsoftQuimera pattern from `rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md`. Evidence: `src/prober/airsoftquimera.py`; tests assert `/cacc_4_50_1_<product_id>_<qty>_0/` and `/cacc_4_50_2_<product_id>_0_0/`.
- [x] Keep quantity ceilings conservative for B1: sample <= 10 products, concurrency 1, per-product quantity ceiling <= 10, timeouts and cooldown enabled. Evidence: `src/prober/run_once.py` default/hard `DEFAULT_MAX_TARGETS=10`; `AirsoftQuimeraProber` rejects `max_qty > 10`; tests cover both.
- [x] Preserve fail-closed behavior: 403/429/503/challenge/captcha => `BLOCKED` or non-zero runner, no Firecrawl fallback, no retry storm. Evidence: `ANTIBOT_REASONS` includes `503`; AirsoftQuimera tests cover 503 cooldown; runner returns non-zero on blocked result.
- [x] No raw HTML, cookies, API keys, DB passwords or full response bodies in logs/reports. Evidence: `prober-live-B1B2-security.report.md`; grep review found only challenge marker/docs/test hits and metadata-only logger calls.
- [ ] No `deploy/prod`, no force-push, push immediately after atomic commit. Evidence: `git status --short --branch`, commit SHA, remote branch.

## Acceptance Criteria
- [x] **B1 architecture contract.** Executor documents the chosen runtime contract: target input JSON schema, runner command, history write mode, metrics, rollback and stop conditions. Evidence: `rso/F7-production-comedida/prober-live-B1B2-architect.report.md`.
- [x] **B1 AirsoftQuimera adapter.** Implement an approved-domain adapter that derives product id from explicit target metadata or the known `-p-4-50-<id>/` URL shape, uses only the documented add/remove paths, probes bounded quantities, and always attempts cleanup after a successful add. Evidence: `src/prober/airsoftquimera.py`; `tests/test_prober_airsoftquimera.py`.
- [x] **B1 HTTP transport.** Add a bounded `ProbeTransport` implementation with honest UA, short connect/read timeouts, same-domain guard, challenge/403/429/503 detection, no cross-run cookie persistence and no raw body logging. Evidence: `src/prober/http_transport.py`; `tests/test_prober_http_transport.py`.
- [x] **B1 runner.** Add a one-shot prober entrypoint, for example `python -m src.prober.run_once`, that accepts explicit targets, run id, dry-run/history flags, and exits non-zero on dirty cleanup, missing DB env when history is requested, or blocked domain. Evidence: `src/prober/run_once.py`; `tests/test_prober_run_once.py`.
- [x] **B1 history mapping.** Map successful `ProbeResult` through `probe_result_to_observation` into F3 append-only history only; never overwrite graph history and never invent price. Evidence: `tests/test_prober_run_once.py::test_runner_writes_history_with_fake_connection`.
- [x] **B1 metrics.** Emit prober metrics or a documented minimal equivalent for attempted/probed/blocked/error/dirty cleanup counts. Evidence: existing `Metrics` counters used by adapter/service; targeted prober tests assert status/block increments.
- [x] **B1 security PASS.** Prove no checkout/login/account/registration/payment paths, no CAPTCHA solving, no credential leakage, no raw body dumps, no broad-domain probing, no unbounded quantity search. Evidence: `rso/F7-production-comedida/prober-live-B1B2-security.report.md` plus `rg` command review.
- [x] **B1 tests PASS.** Full local suite passes after implementation. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `234 passed in 3.00s`; `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS; `git diff --check` PASS.
- [x] **B2 image/runtime decision.** Choose and document exactly one runtime packaging path:
  - publish/pin `harbor.e-dani.com/homelab/skirmshop-stock-prober@sha256:...`; or
  - run the prober entrypoint from the already published crawler image by explicit command override, keeping logical Deployment isolation.
  Evidence: `prober-live-B1B2-devops.report.md`; chosen path is existing crawler image digest with command override.
- [x] **B2 safe-disabled manifests.** `skirmshop-stock-prober` remains `replicas: 0`; crawler CronJobs remain `suspend: true`; prober NetworkPolicy remains default-deny or documents a still-disabled egress plan. Evidence: `prober-live-B1B2-verifier.report.md`; live prober replicas `0`, CronJobs `true 0`, NetworkPolicy no egress rules.
- [x] **B2 CI/release PASS.** CI validates Python/tests/manifests/build for the chosen runtime path, and release/pin is verified if a new image is published. Evidence: CI `28412072803` success on B1 code; release `28412115494` success; digest `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`; CI `28412232953` success on manifest pin commit `87b69bb`.
- [x] **B2 server dry-run PASS.** Rendered k8s is accepted by the API without applying activation. Evidence: `kubectl apply --dry-run=server -k k8s` PASS after digest pin.
- [x] **B3 explicitly not executed.** Any live prober smoke remains a later RSO-controlled gate after B1+B2 PASS. Evidence: no prober Job or live target ConfigMap created; Deployment remains `replicas=0`; egress default-deny.

## Required Evidence Commands
- [ ] `git status --short --branch` before and after implementation.
- [x] `rg -n "checkout|login|account|register|payment|captcha|raw html|response.text|print\\(|logger\\." src/prober tests rso/F7-production-comedida`. Evidence: reviewed in `prober-live-B1B2-security.report.md`.
- [x] `/tmp/crawler-f7-venv/bin/python -m pytest -q`. Evidence: `234 passed`.
- [x] `/tmp/crawler-f7-venv/bin/python -m compileall src tests`. Evidence: PASS.
- [x] `git diff --check`. Evidence: PASS before B1/B2 commits.
- [x] `kubectl kustomize k8s`. Evidence: rendered digest/command/replicas/suspend/backoff/egress checks passed.
- [x] `kubectl apply --dry-run=server -k k8s`. Evidence: PASS after digest pin.
- [x] `kubectl -n skirmshop get deploy skirmshop-stock-prober -o jsonpath='{.spec.replicas}{" "}{.spec.template.spec.containers[0].image}{"\\n"}'`. Evidence: verifier report, replicas `0`, digest `sha256:b5ceac...`.
- [x] `kubectl -n skirmshop get cronjob skirmshop-competitor-crawler-tier1 skirmshop-competitor-crawler-tier2 skirmshop-competitor-crawler-tier3 -o custom-columns=NAME:.metadata.name,SUSPEND:.spec.suspend,BACKOFF:.spec.jobTemplate.spec.backoffLimit --no-headers`. Evidence: all `true 0`.

## Specialist Checks
- [x] **Architect** - runtime contract, state flow, packaging decision and rollback. Evidence: `prober-live-B1B2-architect.report.md`.
- [x] **Backend** - adapter, transport, runner, history mapping, unit tests. Evidence: `prober-live-B1B2-backend.report.md`.
- [x] **DevOps** - image/workflow/manifests/dry-run, safe-disabled live state. Evidence: `prober-live-B1B2-devops.report.md`.
- [x] **Security** - anti-bot, egress, forbidden paths, secrets/log hygiene. Evidence: `prober-live-B1B2-security.report.md`.
- [x] **Verifier/Auditor** - independent re-run of commands and PASS/BLOCKED decision. Evidence: `prober-live-B1B2-verifier.report.md`.

## Status
- 2026-06-30T02:05:03+02:00 - OPEN: RSO scoped B1+B2 as the next non-destructive prober subcycle. F7 remains NOT PASS. B3 live smoke and any production activation are outside this checklist until B1+B2 evidence is real.
- 2026-06-30T02:32:57+02:00 - B1 LOCAL PASS / B2 PENDING: Codex implemented AirsoftQuimera adapter, HTTP transport, one-shot runner, history mapping path and security tests. Evidence: targeted prober suite `59 passed`; full suite `234 passed`; compileall/diff-check/server dry-run PASS. B2 runtime release/pin and live safe-disabled verification still pending.
- 2026-06-30T02:42:00+02:00 - B1+B2 PASS / B3 NOT OPENED: release `28412115494` published digest `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`; commit `87b69bb` pins prober Deployment to that digest with `python -m src.prober.run_once`; CI `28412232953` PASS; Argo live `Synced Healthy`; prober/crawler remain `replicas=0`, CronJobs `suspend=true backoffLimit=0`, prober egress default-deny. F7 remains NOT PASS pending B3/clean live night.
