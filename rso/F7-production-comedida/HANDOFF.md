# HANDOFF - F7 Produccion Comedida

ROL: Claude CLI = EJECUTOR. Codex = PMO/RSO/AUDITOR.

REPO: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`
RAMA: `codex/competitor-crawler-F7-production-comedida`

ANTES DE EJECUTAR:
1. `git fetch origin && git rebase origin/codex/competitor-crawler-F7-production-comedida --autostash` si la rama remota existe; si no, rebase contra `origin/codex/competitor-crawler-F6-live-comparison`.
2. Lee `RSO-MASTER-PLAN.md`, `rso/F7-production-comedida/CHECKLIST.md`, y checklists F3/F4/F5/F6.
3. No hagas `kubectl apply` real, no muevas Argo a prod, no cambies `deploy/prod`, no actives CronJob/replicas sin approval de Codex.

OBJETIVO F7:
Preparar produccion comedida del crawler: scheduling nocturno escalonado, push a Brain autenticado, historico append-only listo, prober seguro, GitOps/DB/image/observabilidad preparados, y gates para una noche real.

SCOPE INICIAL PERMITIDO:
- `rso/F7-production-comedida/**`
- `src/push_client.py` y tests asociados
- `src/scheduler.py`, `src/main.py`, `config.yaml` si se necesitan limites/operacion F7
- `k8s/**` para manifests F7 preparados en dry-run
- `db/migrations/**` solo si hace falta runbook/idempotencia, no schema drift innecesario
- NO tocar `deploy/prod`

CRITERIOS MINIMOS:
- `push_client.py` debe enviar `X-API-Key` desde env (`BRAIN_API_KEY` o equivalente) y fallar cerrado si falta en runtime productivo.
- CronJob/Deployment debe quedar con concurrencia baja, horarios escalonados, recursos, securityContext y no-DoS rails.
- Prober solo se activa para dominio(s) aprobados o queda explicitamente disabled hasta allowlist.
- `competitor_intel` live debe estar en plan GitOps/DB antes de nocturno.
- Todos los cambios deben tener tests y `kubectl apply --dry-run=server -k k8s` cuando aplique.

ENTREGABLES:
- Reports por rol en `rso/F7-production-comedida/<rol>.report.md`.
- Checklist F7 actualizado con `[x]` solo con evidencia.
- Diff minimo, tests, dry-run, y riesgos residuales.

CIERRE:
- No declarar F7 PASS hasta una noche real con logs/metricas/API/SQL verificados por Codex.
