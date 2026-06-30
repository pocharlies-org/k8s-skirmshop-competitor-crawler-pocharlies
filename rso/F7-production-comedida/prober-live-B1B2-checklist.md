# RHO Checklist - F7 Prober Live B1+B2

Timestamp: 2026-06-30T02:05:03+02:00

## Objective
- [ ] Close the non-destructive F7 prober live preparation gate with **B1+B2 only**: B1 backend live-prober implementation for the single approved domain `airsoftquimera.com`, and B2 DevOps/release wiring in a safe-disabled state. Evidence required: code/tests/reports for B1; image or command-override decision, k8s dry-run, CI/release evidence and live disabled-state proof for B2.

## Directives
- [x] Codex is RSO/PMO only for this subcycle; no product-code implementation in this artifact. Evidence: this file defines scope, gates and evidence only.
- [ ] Claude/executor implements directly inside the existing F7 branch after `git fetch` + rebase. Evidence: executor report must include branch, commit, files touched and tests.
- [ ] Do **not** run broad live cart-probe or unsuspend CronJobs/replicas. Evidence: live `skirmshop-stock-prober` remains `replicas=0`; crawler CronJobs remain `suspend=true`.
- [ ] Use only the already evidenced AirsoftQuimera pattern from `rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md`. Evidence: add path `/cacc_4_50_1_<product_id>_<qty>_0/`, remove path `/cacc_4_50_2_<product_id>_0_0/`, no checkout/login/account/CAPTCHA bypass.
- [ ] Keep quantity ceilings conservative for B1: sample <= 10 products, concurrency 1, per-product quantity ceiling <= 10, timeouts and cooldown enabled. Evidence: tests and runtime config/CLI defaults.
- [ ] Preserve fail-closed behavior: 403/429/503/challenge/captcha => `BLOCKED` or non-zero runner, no Firecrawl fallback, no retry storm. Evidence: tests and logs from bounded smoke only after RSO approval.
- [ ] No raw HTML, cookies, API keys, DB passwords or full response bodies in logs/reports. Evidence: security grep and report.
- [ ] No `deploy/prod`, no force-push, push immediately after atomic commit. Evidence: `git status --short --branch`, commit SHA, remote branch.

## Acceptance Criteria
- [ ] **B1 architecture contract.** Executor documents the chosen runtime contract: target input JSON schema, runner command, history write mode, metrics, rollback and stop conditions. Evidence: `rso/F7-production-comedida/prober-live-B1B2-architect.report.md`.
- [ ] **B1 AirsoftQuimera adapter.** Implement an approved-domain adapter that derives product id from explicit target metadata or the known `-p-4-50-<id>/` URL shape, uses only the documented add/remove paths, probes bounded quantities, and always attempts cleanup after a successful add. Evidence: adapter code + deterministic tests.
- [ ] **B1 HTTP transport.** Add a bounded `ProbeTransport` implementation with honest UA, short connect/read timeouts, same-domain guard, challenge/403/429/503 detection, no cross-run cookie persistence and no raw body logging. Evidence: transport tests with mocked responses.
- [ ] **B1 runner.** Add a one-shot prober entrypoint, for example `python -m src.prober.run_once`, that accepts explicit targets, run id, dry-run/history flags, and exits non-zero on dirty cleanup, missing DB env when history is requested, or blocked domain. Evidence: runner unit tests and CLI help/invalid-target command.
- [ ] **B1 history mapping.** Map successful `ProbeResult` through `probe_result_to_observation` into F3 append-only history only; never overwrite graph history and never invent price. Evidence: tests using `probe_result_to_observation` and `history_runtime`/writer fixtures.
- [ ] **B1 metrics.** Emit prober metrics or a documented minimal equivalent for attempted/probed/blocked/error/dirty cleanup counts. Evidence: metrics tests or explicit report if deferred.
- [ ] **B1 security PASS.** Prove no checkout/login/account/registration/payment paths, no CAPTCHA solving, no credential leakage, no raw body dumps, no broad-domain probing, no unbounded quantity search. Evidence: `rso/F7-production-comedida/prober-live-B1B2-security.report.md` plus `rg` commands.
- [ ] **B1 tests PASS.** Full local suite passes after implementation. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q`, `/tmp/crawler-f7-venv/bin/python -m compileall src tests`, `git diff --check`.
- [ ] **B2 image/runtime decision.** Choose and document exactly one runtime packaging path:
  - publish/pin `harbor.e-dani.com/homelab/skirmshop-stock-prober@sha256:...`; or
  - run the prober entrypoint from the already published crawler image by explicit command override, keeping logical Deployment isolation.
  Evidence: DevOps report, workflow diff, rendered manifest.
- [ ] **B2 safe-disabled manifests.** `skirmshop-stock-prober` remains `replicas: 0`; crawler CronJobs remain `suspend: true`; prober NetworkPolicy remains default-deny or documents a still-disabled egress plan. Evidence: `kubectl kustomize k8s` and live `kubectl -n skirmshop get deploy,cronjob`.
- [ ] **B2 CI/release PASS.** CI validates Python/tests/manifests/build for the chosen runtime path, and release/pin is verified if a new image is published. Evidence: GitHub Actions run URL/id, digest command, commit SHA.
- [ ] **B2 server dry-run PASS.** Rendered k8s is accepted by the API without applying activation. Evidence: `kubectl apply --dry-run=server -k k8s`.
- [ ] **B3 explicitly not executed.** Any live prober smoke remains a later RSO-controlled gate after B1+B2 PASS. Evidence: no Job created for prober live smoke in this subcycle unless Codex RSO opens B3 separately.

## Required Evidence Commands
- [ ] `git status --short --branch` before and after implementation.
- [ ] `rg -n "checkout|login|account|register|payment|captcha|raw html|response.text|print\\(|logger\\." src/prober tests rso/F7-production-comedida`.
- [ ] `/tmp/crawler-f7-venv/bin/python -m pytest -q`.
- [ ] `/tmp/crawler-f7-venv/bin/python -m compileall src tests`.
- [ ] `git diff --check`.
- [ ] `kubectl kustomize k8s`.
- [ ] `kubectl apply --dry-run=server -k k8s`.
- [ ] `kubectl -n skirmshop get deploy skirmshop-stock-prober -o jsonpath='{.spec.replicas}{" "}{.spec.template.spec.containers[0].image}{"\\n"}'`.
- [ ] `kubectl -n skirmshop get cronjob skirmshop-competitor-crawler-tier1 skirmshop-competitor-crawler-tier2 skirmshop-competitor-crawler-tier3 -o custom-columns=NAME:.metadata.name,SUSPEND:.spec.suspend,BACKOFF:.spec.jobTemplate.spec.backoffLimit --no-headers`.

## Specialist Checks
- [ ] **Architect** - runtime contract, state flow, packaging decision and rollback.
- [ ] **Backend** - adapter, transport, runner, history mapping, unit tests.
- [ ] **DevOps** - image/workflow/manifests/dry-run, safe-disabled live state.
- [ ] **Security** - anti-bot, egress, forbidden paths, secrets/log hygiene.
- [ ] **Verifier/Auditor** - independent re-run of commands and PASS/BLOCKED decision.

## Status
- 2026-06-30T02:05:03+02:00 - OPEN: RSO scoped B1+B2 as the next non-destructive prober subcycle. F7 remains NOT PASS. B3 live smoke and any production activation are outside this checklist until B1+B2 evidence is real.
