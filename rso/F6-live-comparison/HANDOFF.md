# HANDOFF - F6 Live Comparison

ROL: Claude CLI = EJECUTOR (RSO harness: `/home/dibanez/k8s/.claude/rules/CLAUDE.md` + RHO).  
Codex = PMO/RSO/AUDITOR.

REPO RSO: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`  
RAMA RSO: `codex/competitor-crawler-F6-live-comparison`

Rama a tocar en Brain si aplica: `skirmshop-brain-v2` en `codex/competitor-crawler-F6-live-comparison`.

ANTES DE EJECUTAR:
1. En cada repo a tocar: `git fetch origin && git rebase origin/<rama-activa> --autostash`.
2. Lee `RSO-MASTER-PLAN.md`, `rso/F6-live-comparison/CHECKLIST.md` y
   `rso/F5-product-match/codex-audit.report.md`.
3. Mantén el alcance de F6 (consumo vivo de `PRODUCT_MATCH`): sin F7, sin cambios de manifests/prod, sin scheduling.

OBJETIVO F6:
- Habilitar comparación viva en `skirmshop-brain-v2/src/api/prices.py` para que `competitor_min`, `competitor_max`, `competitor_count` y `competitors[]` salgan reales desde `PRODUCT_MATCH`.
- Extender filtros por competidor (`has_comp`, `comp_cheaper`, `comp_dearer`) y conservar filtros/orden existentes de F6 pre-válido (N/L filtros + `sort` por `margin_*`, status).
- Mantener `/prices/position/{slug}` con métricas reales de competidor y `position` computada (cheapest/mid/most_expensive/unknown).
- Documentar evidencia y dejar pass/bloqueos explícitos en `CHECKLIST.md`.

SCOPE PERMITIDO:
- `skirmshop-brain-v2/src/api/prices.py`
- `skirmshop-brain-v2/tests/unit/test_prices.py`
- `skirmshop-brain-v2/tests/unit/test_http_feedback_surfaces.py`
- `rso/F6-live-comparison/CHECKLIST.md`

PROHIBIDO EN F6:
- Cambios de F7 (CronJob, infra nocturna), F4 (cart-probe), F3 histórico, ni tocar `deploy/prod`.
- Escribir `PRODUCT_MATCH` o `CompetitorProduct` desde esta fase.
- Publicar sin evidencia verificable en `git` y sin actualizar estado de checklist.

COMANDOS ESPERADOS:
- Verificar estado previo: `git status --short`, `git log --oneline -n 5`.
- Lectura de contratos/consumidores: `sed`/`rg` sobre `src/api/prices.py`, `src/api/intel.py`, `tests/unit`.
- Lógica viva: `git diff`, `python3 -m compileall src/api/prices.py tests/unit/test_prices.py tests/unit/test_http_feedback_surfaces.py`.
- Tests de superficie: `pytest -q tests/unit/test_http_feedback_surfaces.py tests/unit/test_prices.py` (o versión equivalente si faltan plugins; registrar fallback).
- (Opcional, si hay entorno API disponible) smoke `prices/comparison` y `prices/position` contra `RAG` service con clave/instance correcta.

ENTREGABLES:
- `rso/F6-live-comparison/CHECKLIST.md` con `[x]/[blocked]` y evidencia.
- Opcional en esta etapa: `rso/F6-live-comparison/{architect,backend,verifier,security}.report.md` si ejecutas roles especializados.

CIERRE:
- No abrir F7 hasta PASS completo y `codex-rso-audit` de endpoint vivo.
