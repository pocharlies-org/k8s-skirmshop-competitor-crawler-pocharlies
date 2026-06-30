# RHO Verifier Report - F7 Prober Live B1+B2

Timestamp: 2026-06-30T02:42:00+02:00

## Claims Verified
- [x] B1 code exists and is tested. Evidence: `src/prober/airsoftquimera.py`, `src/prober/http_transport.py`, `src/prober/run_once.py`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `234 passed in 3.00s`.
- [x] B1 release artifact exists. Evidence: Release Production `28412115494` success on tag `f7-5c19b85`; Harbor public and LAN digest both `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.
- [x] B2 manifest pin is deployed safe-disabled. Evidence: Argo `skirmshop-competitor-crawler` -> `Synced Healthy 87b69bbb85d51a43424051a0d8920954d544c02c`.
- [x] Live prober is not active. Evidence: `kubectl -n skirmshop get deploy skirmshop-stock-prober -o jsonpath=...` returned `0`, image `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`, command `["python","-m","src.prober.run_once"]`, args `["--targets","/app/prober-targets/targets.json"]`.
- [x] Live crawler remains safe-disabled. Evidence: crawler Deployment `replicas=0`, CronJobs tier1/tier2/tier3 `suspend=true`, `backoffLimit=0`.
- [x] Prober egress remains default-deny. Evidence: live NetworkPolicy has `policyTypes: [Egress]` and no egress rules in YAML output.
- [x] B3 was not executed. Evidence: no prober Job/ConfigMap target was created in this subcycle; only GitOps sync of disabled Deployment was verified.

## PASS / FAIL
- [x] B1+B2 non-destructive preparation: PASS.
- [blocked] F7 global: still NOT PASS. Blockers: B3 live smoke/egress decision, clean live-night crawler run with metrics/SQL/Brain evidence.

## Residual Risks
- B2 uses the crawler image artifact with a command override, not a separate `skirmshop-stock-prober` image pipeline. This is accepted for B1+B2 to avoid a second release pipeline while preserving Deployment isolation.
- The prober Deployment has no mounted target file; accidental scaling exits non-zero rather than probing. This is intentional until B3 supplies an approved target ConfigMap/Job.
