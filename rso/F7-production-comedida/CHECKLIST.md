# RHO Checklist - F7 Produccion Comedida

> Fase **F7** del `RSO-MASTER-PLAN.md`.
> Gate previo requerido: F0-F6 PASS. Marca `[x]` SOLO con `Evidence:` directa.
> F7 no se cierra hasta tener CronJob nocturno activo, metricas verdes, cero `block_total` sostenido e IP egress no baneada tras una noche real.

## Objective
- [ ] Activar produccion comedida del crawler de competidores con scheduling nocturno escalonado, historico append-only operativo, push a Brain autenticado, controles anti-DoS/anti-bot, observabilidad y evidencia de una noche real. Evidence pendiente: CronJob live + logs + metricas + SQL/API verification.

## Directives
- [x] Codex/RSO abre la fase y define scope; Claude CLI ejecuta implementacion por roles. Evidence: este checklist y `HANDOFF.md`.
- [x] No tocar `deploy/prod` directamente ni forzar ramas. Evidence: rama `codex/competitor-crawler-F7-production-comedida`; cambios GitOps deben prepararse en ramas codex y push inmediato.
- [ ] No activar replicas/CronJob productivo hasta que DevOps+Security+Verifier pasen y Codex re-ejecute evidencia. Evidence pendiente: reports + comandos.
- [ ] Mantener trafico competidor no-DoS: horarios escalonados, concurrencia baja, crawl-delay/robots, kill-switch 403/429/challenge, cooldown por dominio. Evidence pendiente: config/manifests/tests.
- [ ] No publicar secretos. API keys solo via `Secret`/`ExternalSecret`; logs/reportes deben mostrar presencia, nunca valores. Evidence pendiente: grep/report.

## Known Gaps Before Activation
- [ ] `competitor_intel` live no esta aplicado en CNPG. Evidence: `kubectl -n databases get database` no lista `competitor-intel`; infra worktree `_worktrees/k8s-infra-competitor-crawler-F3` contiene commit `a6e64e9 Add competitor intel database CR`.
- [ ] Crawler/prober no estan desplegados live. Evidence: `kubectl -n skirmshop get deploy,cronjob,externalsecret,secret,networkpolicy | rg 'competitor|crawler|prober|stock'` solo muestra `rag-competitor-llm-matcher`, no crawler/prober.
- [ ] Argo app del crawler esta deshabilitada. Evidence: `k8s-gitops-pocharlies/apps-disabled/skirmshop-competitor-crawler.yaml`.
- [ ] Imagenes siguen `:pending`. Evidence: `k8s/manifest.yaml` y `k8s/prober-deployment.yaml`.
- [x] `push_client.py` envia `X-API-Key` a Brain `push-ingest` cuando `BRAIN_API_KEY` esta configurado y puede fallar cerrado con `REQUIRE_BRAIN_API_KEY=true`. Evidence: `src/push_client.py`; `pytest -q tests/test_push_client.py` -> 3 passed.
- [ ] Prober no tiene transporte HTTP live ni egress allowlist. Evidence: `src/prober/transport.py` es `Protocol`; `k8s/prober-networkpolicy.yaml` tiene `egress: []`.
- [ ] Pods carecen de `securityContext` endurecido antes de activacion. Evidence: F4 `security.report.md` recomienda `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, drop capabilities, `seccompProfile`.
- [ ] Observabilidad Prometheus/dashboard no esta preparada para F7. Evidence: metricas F4 son in-memory (`src/prober/metrics.py`), sin endpoint scrape/runtime dashboard.

## Acceptance Criteria
- [ ] **F7 research PASS.** Estado actual de k8s/GitOps/DB/secrets/image/observabilidad auditado y gaps reconciliados. Evidence: `researcher.report.md` + comandos Codex.
- [ ] **Architecture PASS.** Diseno F7 define modo de ejecucion seguro: CronJob vs Deployment scheduler, flujo crawler -> Brain -> historico, flujo prober -> historico, limites por tier, retry/backoff, rollback y criterios de stop. Evidence: `architect.report.md`.
- [x] **Backend auth PASS.** `push_client.py` autentica contra Brain con `X-API-Key` desde env y tiene modo fail-closed con `REQUIRE_BRAIN_API_KEY=true`; batch/retry se conserva. Evidence: `backend.report.md`; `pytest -q tests/test_push_client.py` -> 3 passed; `pytest -q` -> 142 passed; `python3 -m compileall src tests` PASS; `git diff --check` PASS.
- [ ] **Prober live transport PASS.** Existe transporte HTTP controlado para cart-probe solo en dominios aprobados, con cleanup garantizado, kill-switch y no checkout/login. Evidence: tests + sample limitado autorizado.
- [ ] **DevOps PASS.** Manifests CronJob/Deployment/NetworkPolicy/ExternalSecret/image tags preparados; `kubectl kustomize` y `kubectl apply --dry-run=server -k k8s` PASS; Argo app move/enable preparado sin tocar prod directo. Evidence: report + command output.
- [ ] **DB/Migration PASS.** `competitor_intel` existe live y migracion `001_f3_history.sql` aplicada/verificada con query de tablas/vista; credenciales minimas aprobadas. Evidence: `kubectl` + SQL read-only.
- [ ] **Security PASS.** Secrets no expuestos; pod hardening; egress restringido; anti-bot/no-DoS; no CAPTCHA solver; no writes a competidores salvo cart add/remove aprobado; no PII/raw HTML en logs. Evidence: `security.report.md` + grep.
- [ ] **Verifier PASS.** Re-ejecuta tests, dry-run server, auth checks, no dirty diff, no scope creep, y si se activa, una noche real. Evidence: `verifier.report.md`.
- [ ] **Live night PASS.** CronJob nocturno ejecuta una ventana real con metricas verdes, `competitor_crawl_block_total` sin incremento sostenido, logs sin bans, Brain comparison sigue poblado y Postgres historico tiene nueva observacion. Evidence: Prometheus/logs/API/SQL.

## Specialist Checks
- [ ] **rho-researcher** - estado/gaps F7.
- [ ] **rho-architect** - contrato operativo y rollback.
- [x] **rho-backend / Codex PMO exception** - auth push-ingest. Evidence: Claude CLI `rho-backend` timeout sin stdout pero dejo diff; Codex reviso, anadio tests/reporte y re-ejecuto gates en `backend.report.md`. History/prober runtime integration queda en criterios DevOps/Prober.
- [ ] **rho-devops** - k8s/GitOps/image/CronJob/DB apply plan.
- [ ] **rho-security** - secrets/egress/pod hardening/anti-bot.
- [ ] **rho-verifier** - comprobacion independiente.
- [ ] **Codex/RSO auditor** - re-ejecucion de evidencia y decision PASS/BLOCKED.

## Status (log datado, append-only)
- 2026-06-27T00:00:00+02:00 - OPEN: F7 abierta tras F6 PASS. PMO read-only detecta bloqueos pre-activacion: DB `competitor_intel` no live, Argo app disabled, imagenes `:pending`, sin CronJob crawler/prober live, `push_client.py` sin `X-API-Key`, prober sin transporte live/egress allowlist, pod hardening/observabilidad pendientes. F7 queda `[blocked]` para activacion hasta DevOps+Security+Verifier.
- 2026-06-27T00:30:00+02:00 - BACKEND AUTH PASS: `push_client.py` ahora envia `X-API-Key` desde `BRAIN_API_KEY` y falla cerrado con `REQUIRE_BRAIN_API_KEY=true`; tests nuevos cubren header, fail-closed y batching. Evidence: `pytest -q tests/test_push_client.py` -> 3 passed; `pytest -q` -> 142 passed; `python3 -m compileall src tests` PASS; `git diff --check` PASS. Claude `rho-backend` timeout sin stdout; Codex PMO integra como excepcion limitada.
