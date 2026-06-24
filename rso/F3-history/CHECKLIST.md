# RHO Checklist - F3 History Append-Only

> Fase **F3** del `RSO-MASTER-PLAN.md`.
> Gate previo requerido: F0 PASS, F1 PASS, F2 PASS y F5 PASS. Orden aprobado: `F0 -> F1 -> (F2 || F5) -> F3 -> F4 -> F6 -> F7`.
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/SQL output). No abrir F4/F6/F7 sin PASS de Codex.

## Objective
- [ ] Crear y validar histórico temporal append-only de competidores en Postgres: DB/schema `competitor_intel`, tabla mensual particionada `price_stock_observation`, vista `estimated_sales_daily`, y prueba con 2 corridas que produzcan >=2 observaciones por producto, delta correcto, y gaps `indeterminate`. Evidence:

## Directives
- [ ] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Claude implementa/prueba; Codex re-ejecuta evidencia antes de cerrar F3. Evidence:
- [ ] F3 es **histórico append-only**. Prohibido cart-probe/cantidad exacta/carrito (F4), fixes de comparación viva `prices.py`/`intel.py` (F6), scheduling nocturno/CronJob activo (F7) y cambios no relacionados. Evidence:
- [ ] Histórico vive solo en Postgres append-only. El grafo Brain/FalkorDB queda solo para precio/stock vigente; F3 no debe sobrescribir nodos/edges de grafo para simular histórico. Evidence:
- [ ] No inferir ventas ni agotados por ausencia de dato. Gaps, reposición o datos incompletos deben quedar `indeterminate`, nunca ventas estimadas inventadas. Evidence:
- [ ] DDL/infra solo aditivo y reversible por migración nueva; prohibido drop/truncate/delete/update destructivo sobre datos reales. Evidence:
- [ ] Idempotencia por `(domain, product_key, run_id)`: repetir la misma corrida no duplica observaciones ni modifica rows append-only salvo conflicto no-op documentado. Evidence:
- [ ] Snapshots crudos, si se implementan, deben apuntar a MinIO/S3 por URI/key sin exponer credenciales ni volcar HTML sensible en logs/RSO. Evidence:
- [ ] Hacia competidores, F3 no añade nuevas acciones HTTP respecto a F1/F2 para el piloto; solo usa datos públicos de catalogo/precio/stock visible. Evidence:
- [ ] Git: rama `codex/competitor-crawler-F3-history`; `fetch`+rebase antes de commit; push inmediato; nunca force-push ni tocar `deploy/prod` directamente. Evidence:

## Acceptance Criteria
- [ ] **Gates previos verificados.** F0/F1/F2/F5 tienen Objective `[x]` y F5 baseline viva actual `PRODUCT_MATCH=437` queda registrada como contexto, aunque F3 no depende de modificarla. Evidence:
- [ ] **Topology research completo.** Repos/servicios afectados identificados: crawler, Postgres/CNPG o DB compartida, secretos por nombre (no valor), jobs/migrations existentes, y flujo desde dry-run/crawl a observaciones. Evidence:
- [ ] **Contrato SQL definido.** `price_stock_observation` incluye como mínimo: `domain`, `product_key` (= `source_id` del grafo), `run_id`, `observed_at`, `price`, `currency`, `vat_incl`, `stock_qty`, `stock_status`, `stock_method`, `is_promotion`, `raw_snapshot_s3`; cualquier columna extra necesaria para `last_success`/errores queda justificada por architect. Evidence:
- [ ] **Particionado mensual.** Tabla particionada por `observed_at` con partición del mes actual y mecanismo documentado para crear siguientes meses. Evidence:
- [ ] **Constraints e índices.** Checks/enums para `stock_status in ('in_stock','out_of_stock','unknown')`, `stock_method in ('visible','cart_probe','unknown')` o contrato equivalente; unique/idempotency `(domain, product_key, run_id)`; índice `(domain, product_key, observed_at DESC)`. Evidence:
- [ ] **Vista `estimated_sales_daily`.** Usa `LAG(stock_qty) OVER (PARTITION BY domain, product_key ORDER BY observed_at)` o equivalente; ventas estimadas solo cuando `prev_qty` y `curr_qty` existen, ambas observaciones son exitosas, y `prev_qty - curr_qty > 0`; reposición (`delta < 0`), gaps o nulos => `indeterminate`. Evidence:
- [ ] **Writer append-only implementado.** El crawler o módulo de ingest F3 escribe observaciones desde resultados F1/F2 sin tocar cart/probe ni grafo histórico; repetir mismo `run_id` no duplica. Evidence:
- [ ] **Dos corridas verificadas.** En entorno de prueba o target aprobado se insertan 2 corridas con >=3 productos; cada producto tiene >=2 observaciones o el caso gap intencionado; queries demuestran delta correcto para venta, reposición/gap `indeterminate`, y ausencia de duplicados tras re-run. Evidence:
- [ ] **Smoke de 3 productos.** Reporte con SQL/output para: producto con delta positivo estimado, producto con reposición o stock creciente `indeterminate`, producto con gap/fallo `indeterminate`. Evidence:
- [ ] **Tests locales pasan.** Unit/integration tests de DDL/view/writer/idempotencia, más tests existentes de crawler; `git diff --check` PASS en repos tocados. Evidence:
- [ ] **Security/data PASS.** Sin secretos en logs, sin PII, sin checkout/cart, sin writes a competidores, sin exponer snapshot bruto en RSO. Evidence:
- [ ] **DevOps PASS.** Manifiestos/migraciones validados con dry-run/lint; no `deploy/prod` directo; si hay apply live, debe ser vía GitOps o comando aprobado y con verificación post-apply. Evidence:

## Specialist Checks
- [ ] **rho-researcher** - topologia, DB actual, migraciones existentes, rutas de datos, riesgos/bloqueos. Evidence:
- [ ] **rho-architect** - contrato SQL, particionado, vista, idempotencia, frontera F3 vs F4/F6. Evidence:
- [ ] **rho-backend** - writer/ingest append-only, tests, fixtures de dos corridas. Evidence:
- [ ] **rho-devops** - CNPG/Postgres/migraciones/GitOps/dry-run/apply seguro. Evidence:
- [ ] **rho-security** - secretos, snapshots, anti-bot, privacidad, no cart/no checkout. Evidence:
- [ ] **rho-verifier** - re-ejecuta comandos, SQL, tests, diff y scope. Evidence:
- [ ] **Codex/RSO auditor** - re-ejecuta evidencia y marca PASS/BLOCKED. Evidence:

## Status (log datado, append-only)
- 2026-06-24T21:59:34+02:00 - OPEN: F3 abierta tras F5 PASS (`f0fbdf9`). Rama `codex/competitor-crawler-F3-history` creada y publicada. Pendiente research Claude CLI antes de cualquier DDL/write.
