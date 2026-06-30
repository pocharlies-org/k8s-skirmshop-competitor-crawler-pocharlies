# Handoff to Claude - F7 Prober Live B1+B2

Relay this exact message to Claude CLI/executor:

```text
ROL: ejecutor F7 prober live B1+B2 en /home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies.

Contexto:
- Codex es RSO/PMO. Tu trabajo es implementar y devolver evidencia. No re-delegues.
- Rama compartida: codex/competitor-crawler-F7-production-comedida.
- Antes de tocar nada: git fetch --all --prune && git rebase origin/codex/competitor-crawler-F7-production-comedida.
- No force-push. No tocar deploy/prod. Commit atomico y push inmediato.
- F7 global NO es PASS. Produccion sigue safe-disabled.

Objetivo:
Ejecuta SOLO B1+B2 para cerrar la preparacion no destructiva del stock-prober live:
- B1 backend: transporte HTTP live acotado, adapter AirsoftQuimera basado en la calibracion F4, runner one-shot, history mapping append-only, tests y reportes.
- B2 DevOps: decision de empaquetado/runtime, CI/release/manifests safe-disabled, server dry-run y evidencia live de que replicas/CronJobs siguen apagados.
- NO ejecutar B3 live smoke salvo que Codex RSO abra explicitamente ese gate despues de revisar B1+B2.

Documentos obligatorios a leer primero:
- RSO-MASTER-PLAN.md
- rso/F7-production-comedida/CHECKLIST.md
- rso/F7-production-comedida/prober-live-gap.report.md
- rso/F7-production-comedida/prober-live-B1B2-checklist.md
- rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md

Directivas duras:
- Dominio aprobado para este trabajo: airsoftquimera.com, y solo con el patron ya evidenciado:
  - add: /cacc_4_50_1_<product_id>_<qty>_0/
  - remove: /cacc_4_50_2_<product_id>_0_0/
- Nada de broad live cart-probe, checkout, login, account, registro, pago, CAPTCHA solving, bypass o Firecrawl fallback.
- Concurrencia 1, muestra <= 10 productos, ceiling de cantidad <= 10, timeouts cortos, cooldown/kill-switch.
- 403/429/503/challenge/captcha => fail closed/BLOCKED; dirty cleanup => ERROR y exit non-zero.
- No logs con raw HTML/body completo, cookies, secretos, API keys o passwords.
- Prober Deployment debe quedar replicas: 0; crawler CronJobs deben quedar suspend: true; no activar produccion.

Scope tecnico esperado:
1. Implementa un ProbeTransport HTTP live acotado con tests mockeados.
2. Implementa un adapter/prober AirsoftQuimera aprobado que derive product_id de target metadata o URL -p-4-50-<id>/.
3. Implementa runner one-shot, por ejemplo python -m src.prober.run_once, con input explicito de targets JSON, run_id, dry-run/history mode y exit codes verificables.
4. Mapea ProbeResult a Observation con probe_result_to_observation y escribe solo append-only si history esta activado y PG env existe.
5. Decide B2: publicar/pinnear imagen skirmshop-stock-prober o usar imagen crawler immutable con command override explicito. Documenta por que.
6. Mantener manifests safe-disabled. NetworkPolicy prober puede seguir default-deny si no se ejecuta live smoke; si propones egress, debe quedar desactivado o compensado por app-domain guard y documentado.

Evidencia obligatoria:
- Crear/actualizar:
  - rso/F7-production-comedida/prober-live-B1B2-architect.report.md
  - rso/F7-production-comedida/prober-live-B1B2-backend.report.md
  - rso/F7-production-comedida/prober-live-B1B2-devops.report.md
  - rso/F7-production-comedida/prober-live-B1B2-security.report.md
  - rso/F7-production-comedida/prober-live-B1B2-verifier.report.md
  - rso/F7-production-comedida/prober-live-B1B2-checklist.md con [x]/[blocked] y Evidence:
- Re-ejecutar y pegar resultados resumidos:
  - git status --short --branch
  - /tmp/crawler-f7-venv/bin/python -m pytest -q
  - /tmp/crawler-f7-venv/bin/python -m compileall src tests
  - git diff --check
  - kubectl kustomize k8s
  - kubectl apply --dry-run=server -k k8s
  - kubectl -n skirmshop get deploy skirmshop-stock-prober -o jsonpath='{.spec.replicas}{" "}{.spec.template.spec.containers[0].image}{"\n"}'
  - kubectl -n skirmshop get cronjob skirmshop-competitor-crawler-tier1 skirmshop-competitor-crawler-tier2 skirmshop-competitor-crawler-tier3 -o custom-columns=NAME:.metadata.name,SUSPEND:.spec.suspend,BACKOFF:.spec.jobTemplate.spec.backoffLimit --no-headers

Criterio de salida:
- Si B1+B2 pasan: commit + push y reporta SHA, CI/release IDs y blockers restantes para B3/F7.
- Si algo falla o requiere live egress/activacion: no improvises; marca [blocked] con evidencia y deja la rama pusheada con los cambios seguros.
```
