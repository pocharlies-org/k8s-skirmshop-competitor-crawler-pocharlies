# RHO Architect Report - F7 Prober Live B1+B2

Timestamp: 2026-06-30T02:32:57+02:00

## Scope
- [x] Define the B1 runtime contract without B3 live smoke. Evidence: code implements an explicit target-file one-shot runner in `src/prober/run_once.py`; no schedule/replica activation was added.
- [x] Preserve logical microservice isolation. Evidence: prober code lives under `src/prober/*`; crawler runner `src/run_once.py` and scheduler flow are unchanged.
- [x] Keep approved-domain boundaries. Evidence: `src/prober/run_once.py` rejects any domain other than `airsoftquimera.com`; `src/prober/http_transport.py` enforces exact/subdomain host guard before HTTP.
- [x] Keep B3 separate. Evidence: no live Job, no CronJob unsuspend, no replica change; B1 only adds offline-testable code.

## Runtime Contract
- Target input: JSON list or `{"targets":[...]}` with `domain`, `product_key`, `url`, optional `platform`, optional `variant_id`.
- Runner: `python -m src.prober.run_once --targets <targets.json> --run-id <id> [--write-history]`.
- Target cap: default and hard cap `10` targets; quantity ceiling default and hard cap `10`.
- Domain/platform: only `airsoftquimera.com` / `airsoftquimera` accepted in B1.
- History: opt-in via `--write-history`; PG env is validated before any probe traffic.
- Exit codes: `0` all targets PROBED/UNAVAILABLE; `1` blocked/error/runtime failure; `2` setup/usage error.

## Packaging Decision For B2
- [x] Use the existing Dockerfile/image artifact as the prober runtime, but run it as the separate `skirmshop-stock-prober` Deployment with explicit `python -m src.prober.run_once` command override. Evidence pending for B2: release digest and manifest pin after CI/release.

## Residual Risks
- [blocked] B2 is not complete in this report: image digest is not yet published/pinned for the new code.
- [blocked] B3 live smoke is not opened: prober NetworkPolicy remains default-deny and no live target ConfigMap/Job has been approved.

## Checklist
- [x] Architecture contract documented. Evidence: this report.
- [x] B1 code boundaries are separate from crawler scheduling. Evidence: touched code is `src/prober/*` and tests.
- [blocked] B2 runtime proof pending release/pin.
