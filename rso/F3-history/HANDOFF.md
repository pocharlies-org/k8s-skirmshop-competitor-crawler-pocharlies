# HANDOFF - F3 History Append-Only

ROL: Claude CLI = EJECUTOR. Codex = RSO/PMO/auditor.

OBJETIVO F3:
Implementar y demostrar histórico temporal append-only para el crawler de competidores:
DB/schema `competitor_intel`, tabla `price_stock_observation` particionada por mes, vista `estimated_sales_daily`, y 2 corridas con evidencia SQL de >=2 observaciones por producto, delta correcto y gaps `indeterminate`.

GATES PREVIOS:
- F0 PASS.
- F1 PASS.
- F2 PASS.
- F5 PASS en commit RSO `f0fbdf9`.
- Baseline viva F5 para futuras fases: `PRODUCT_MATCH=437`, `0` duplicados, tras prune externo. F3 no debe modificar esta baseline.

SCOPE:
- Repo RSO/crawler: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`
- Infra/GitOps si hace falta DB/migración: `/home/dibanez/k8s/k8s-infra-pocharlies`
- Brain/RAG solo si hace falta leer contratos o integrar ingest vigente: `/home/dibanez/k8s/skirmshop-brain-v2`
- Shopify app solo para descubrir DB/secret/migration pattern si hace falta: `/home/dibanez/k8s/k8s-skirmshopshopifyapp-pocharlies`

DIRECTIVAS:
- Trabaja en rama `codex/competitor-crawler-F3-history` en el repo RSO/crawler, y ramas `codex/*` equivalentes en repos tocados.
- `git fetch` + rebase antes de cada commit; push inmediato; nunca force-push.
- No tocar `deploy/prod` directamente.
- No implementar F4: nada de cart-probe, carrito, checkout, login, cantidad exacta por carrito ni bypass CAPTCHA.
- No implementar F6: no arreglar `prices.py`/`intel.py` salvo lectura/research. `intel.py` queda para F6.
- No implementar F7: no activar cron nocturno ni scheduling productivo.
- Histórico solo Postgres append-only; no usar FalkorDB/Brain graph para simular histórico.
- Prohibido `DROP`, `TRUNCATE`, `DELETE` o `UPDATE` destructivo sobre datos reales.
- No exponer secretos. En reports usa nombres de Secret/ExternalSecret, nunca valores.
- Si no hay target DB seguro para aplicar, implementa migración/tests y marca apply `[blocked]` con blocker exacto.

CRITERIOS DE ACEPTACIÓN:
- `rso/F3-history/CHECKLIST.md` actualizado con `[x]` solo si hay Evidence directa.
- Research identifica DB/CNPG, migraciones, secretos por nombre y ruta de datos.
- Architect define contrato SQL:
  - `domain`
  - `product_key` (= `source_id` del nodo grafo)
  - `run_id`
  - `observed_at`
  - `price`
  - `currency`
  - `vat_incl`
  - `stock_qty`
  - `stock_status in_stock|out_of_stock|unknown`
  - `stock_method visible|cart_probe|unknown`
  - `is_promotion`
  - `raw_snapshot_s3`
  - columnas extra solo si justificadas para `last_success`/errores/gaps.
- Tabla `price_stock_observation` particionada por mes.
- Idempotencia `(domain, product_key, run_id)`.
- Índice `(domain, product_key, observed_at DESC)`.
- Vista `estimated_sales_daily`:
  - usa `LAG(stock_qty)` por `domain/product_key`
  - venta estimada solo si ambas observaciones son exitosas y `prev_qty - curr_qty > 0`
  - reposición, gaps, nulos o fallo => `indeterminate`.
- Writer/ingest append-only desde resultados F1/F2 o fixtures equivalentes.
- Dos corridas verificadas con SQL/output:
  - producto A: delta positivo => ventas estimadas correctas
  - producto B: reposición/stock creciente => `indeterminate`
  - producto C: gap/fallo/nulo => `indeterminate`
  - re-run mismo `run_id` no duplica.
- Tests locales y `git diff --check` pasan en todos los repos tocados.
- Security y DevOps reports PASS o `[blocked]` con motivo exacto.

SUBAGENTES/ROLES A USAR:
1. `rho-researcher` read-only: topología DB/migrations/secrets/rutas.
2. `rho-architect`: contrato SQL, particiones, vista, idempotencia, frontera F3.
3. `rho-backend`: writer/ingest/tests/fixtures.
4. `rho-devops`: CNPG/Postgres/GitOps/dry-run/apply seguro.
5. `rho-security`: secretos/snapshots/anti-bot/no-cart/no-PII.
6. `rho-verifier` read-only: re-ejecutar evidencia y PASS/FAIL.

ENTREGA:
- Reports por rol en `rso/F3-history/<rol>.report.md`.
- Checklist F3 reconciliado.
- Commits atómicos y push inmediato.
- No abrir F4/F6/F7. Codex audita F3 después.
