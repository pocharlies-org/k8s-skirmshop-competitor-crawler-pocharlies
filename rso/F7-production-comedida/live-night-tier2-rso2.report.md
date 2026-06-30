# RHO PMO Report - F7 Tier2 Live Data Gate

Timestamp: 2026-06-30T10:05:00+02:00

## Objective
- [blocked: anti-bot blockers] Verify whether tier2 can be promoted from
  suspended to production schedule after a bounded live data gate. Evidence:
  `skirmshop-competitor-crawler-tier2-rso2-20260630074224` failed with
  `failed=2` due `challenge_body` on `begadi.com` and `aa-store.at`.

## Directives
- [x] Do not desuspend tier2 or scale Deployments for the test. Evidence:
  tier2 stayed `suspend=true`; crawler/prober Deployments stayed `replicas=0`.
- [x] Use the live CronJob template and immutable image digest. Evidence:
  rso2 was created with `kubectl create job --from=cronjob/skirmshop-competitor-crawler-tier2`.
- [x] Abort/remediate if crawler touches login/auth routes. Evidence: rso1 was
  aborted after a GET to `https://www.powair6.com/en/authentication`; code now
  skips `/authentication`, `/auth`, `/signin`, `/sign-in`, `/my-account`,
  `/customer`, `/user`, `/password` and `/session`.
- [x] Preserve no retry amplification. Evidence: live tier2 `backoffLimit=0`;
  rso2 left one failed Job/pod and no Kubernetes retry pod.

## Acceptance Criteria
- [x] **Auth/login route remediation PASS.** Evidence: commit `d528b1b`
  `fix(f7): skip auth routes during crawler bfs`; tests
  `.venv/bin/pytest -q tests/test_extractor.py tests/test_crawler_egress_guard.py`
  -> `23 passed`; full suite -> `239 passed`; live rso2 logs did not include
  the previous `powair6.com/en/authentication` GET.
- [x] **Image release/pin PASS.** Evidence: release `28429187546` for tag
  `f7-de04ea5` PASS; Harbor public/LAN digest
  `sha256:4a8d993694dd95007cb6f7f2229b232c0e6764b9fc9bc6fe517e683a3663afeb`;
  commit `fbd03f9` pins crawler Deployment and tier1/tier2/tier3 CronJobs to
  that digest; CI `28429333532` PASS; Argo `Synced Healthy fbd03f9`.
- [x] **Powair6 data path PASS.** Evidence: rso2 logs show
  `powair6.com crawl done - visited=25 products=497`,
  `history write complete: inserted=497 skipped=0`, and
  `push-ingest done: sent=497 failed=0`; SQL for
  `run_id='tier2:20260630T074241130227Z'` returned
  `497|497|0.0000|1999.0000|powair6.com`.
- [blocked: challenge_body] **Tier2 full data gate BLOCKED.** Evidence: rso2 logs
  show `begadi.com` and `aa-store.at` blocked by `challenge_body`; summary
  `run_once complete: tiers=1 pushed=497 failed=2`; pod phase `Failed`,
  container exit `1`; job status failed `1`.
- [x] **Robots/disallow behavior PASS.** Evidence: rso2 logs show
  `patrolbase.co.uk` robots disallow and `kyairsoft.com` robots 403 treated as
  disallow-all; both inserted/pushed 0 and did not trigger retries.
- [x] **Live safety state preserved.** Evidence after final sync: tier1/tier2
  `suspend=true`, tier3 `suspend=false`, all `backoffLimit=0`; crawler/prober
  Deployments `replicas=0`.

## Specialist Checks
- [x] **Backend** - auth route skip and metrics status remediated. Evidence:
  `src/extractor.py`, `src/run_once.py`, focused tests `70 passed`, full suite
  `239 passed`.
- [x] **DevOps** - immutable digest repinned and synced. Evidence: commits
  `6463ada` and `fbd03f9`; CI `28428376946` and `28429333532` PASS; Argo
  `Synced Healthy fbd03f9`.
- [x] **Security** - no new production schedule opened; blocked domains remain
  suspended. Evidence: live CronJob/Deployment readbacks.
- [x] **Verifier/Auditor** - tier2 activation remains BLOCKED. Evidence:
  direct log grep, SQL readback and pod/job status above.

## Status
- 2026-06-30T09:31:01+02:00 - ABORTED: rso1 touched
  `powair6.com/en/authentication`; Job was deleted and gate marked FAIL. It
  had already inserted/pushed 493 `powair6.com` rows, so that run is not valid
  activation evidence.
- 2026-06-30T09:35:20+02:00 - REMEDIATED: auth/account route hints added to
  BFS skip rules; CI `28428131164` PASS; release `28428207849` PASS; digest
  `sha256:e96b5ad3a639134e5ad838915b42b3199b75caac017e748a213252820c767b56`
  was synced before rso2.
- 2026-06-30T09:42:24+02:00 - BLOCKED: rso2 validated the auth-route fix and
  collected 497 `powair6.com` rows, but tier2 failed closed on
  `begadi.com` and `aa-store.at` challenge bodies. Tier2 must remain
  `suspend=true`.
- 2026-06-30T10:05:00+02:00 - HARDENED: partial-failure metrics now record
  `run_total{status="error"}` when a tier returns `failed > 0`; final live
  digest is `sha256:4a8d993694dd95007cb6f7f2229b232c0e6764b9fc9bc6fe517e683a3663afeb`.
