# RHO Checklist - F5 Product Match

> Fase **F5** del `RSO-MASTER-PLAN.md`.
> Gate previo: F1 PASS (`262674f`) y F2 PASS (`134036e`). F5 esta permitido en paralelo con F2 y debe cerrar antes de F3/F6.
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/output). No abrir F3/F6/F7 sin PASS de Codex.

## Objective
- [ ] Poblar/validar matching `PRODUCT_MATCH` entre nuestros productos Shopify y `CompetitorProduct` con `match_confidence` y `match_method`, usando cascada multi-senal (EAN/GTIN -> SKU -> marca+modelo normalizado -> embeddings BGE/reranker), enviando dudosos a `MatchReview` y demostrando precision en muestra revisada. Evidence:

## Directives
- [ ] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Claude implementa/prueba; Codex re-ejecuta evidencia antes de abrir F3/F6/F7.
- [ ] No tocar `deploy/prod`, k8s manifests, CronJobs ni produccion nocturna en F5.
- [ ] F5 es **matching**. Prohibido historico append-only (F3), cart-probe/cantidad exacta/carrito (F4), comparacion viva/F6, scheduling/F7.
- [ ] No usar matches dudosos para alimentar alertas/deltas/API. Tramo medio siempre a `MatchReview`.
- [ ] Todo write debe ser idempotente y auditable: dry-run primero, target explicito, before/after counts, rollback o re-run seguro.
- [ ] No escribir en produccion real sin evidencia de target y aprobacion RSO en el reporte de auditoria. Si el unico target disponible es prod, marcar `[blocked]`.
- [ ] No exponer secretos/tokens ni datos personales. La muestra debe contener solo identificadores de producto publicos/necesarios.
- [ ] Git: ramas `codex/*` por repo tocado; `fetch`+rebase antes de commit; push inmediato; nunca force-push.

## Acceptance Criteria
- [x] **Topology research completo.** Repos/servicios afectados identificados (`skirmshop-brain-v2`, posible `skirmshopshopifyapp`, este repo RSO), schema `PRODUCT_MATCH`, APIs consumidoras (`prices.py`, `intel.py`), fuente Shopify barcode/SKU y fuente `CompetitorProduct` verificados. Evidence: `rso/F5-product-match/researcher.report.md`; Brain branch `codex/product-recommendations-20260616`, Shopifyapp branch `codex/competitor-crawler-F0-bootstrap`; `PRODUCT_MATCH` en `ontology.py`, consumidores no lo expanden todavia.
- [ ] **Contrato `PRODUCT_MATCH` definido.** Direccion del edge, claves idempotentes, propiedades (`match_confidence`, `match_method`, timestamps/source), umbrales auto-link/review/reject y enum de metodos documentados. Evidence:
- [ ] **Matcher implementado con dry-run.** Comando dry-run produce candidatos con senales usadas, score, decision (`auto_link|review|reject`) sin escribir edges. Evidence:
- [ ] **Cascada multi-senal.** EAN/GTIN exacto usa `Variant.barcode`; SKU exacto; marca+modelo normalizado NFKD/ASCII/hyphen->space; fallback embedding/reranker implementado o bloqueado explicitamente si infraestructura no existe. Evidence:
- [ ] **`MatchReview` para dudosos.** Tramo medio se persiste/serializa a cola de revision humana o artifact equivalente; no se crea `PRODUCT_MATCH` para dudosos. Evidence:
- [ ] **Precision en muestra revisada.** Muestra manual revisada con positivos/negativos, matriz de confusion, precision >= umbral definido; falsos positivos explicados. Evidence:
- [ ] **Edges `PRODUCT_MATCH` auditables.** En target permitido, count before/after de edges y muestra de edges con `match_confidence/match_method`; re-run idempotente no duplica. Evidence:
- [ ] **Consumidores desbloqueables.** `prices.py`/`intel.py` pueden leer `PRODUCT_MATCH` sin usar matches dudosos; tests o smoke lo demuestran. Evidence:
- [ ] **Security/data PASS.** Sin secretos en logs, sin writes no aprobados, sin datos personales, target de escritura claro, rollback/re-run seguro. Evidence:
- [ ] **Tests locales pasan.** Unit/integration tests del matcher, schema/ontology y consumidores relevantes; `git diff --check` pasa. Evidence:

## Specialist Checks
- [x] **rho-researcher** - topologia, datos existentes, targets y riesgos de escritura. Evidence: `rso/F5-product-match/researcher.report.md`; safe write target `[blocked]` porque solo FalkorDB prod es visible; `MatchReview` no existe; `CompetitorProduct` no tiene barcode/ean.
- [ ] **rho-architect** - contrato de edge, umbrales, idempotencia, frontera F5 vs F6. Evidence:
- [ ] **rho-backend** - matcher, dry-run/apply controlado, tests, artefactos. Evidence:
- [ ] **rho-security** - secretos, writes, datos, target, re-run seguro. Evidence:
- [ ] **rho-verifier** - re-ejecuta comandos, matriz, counts, no scope creep. Evidence:
- [ ] **Codex/RSO auditor** - re-ejecuta evidencia y marca PASS/BLOCKED. Evidence:

## Status (log datado, append-only)
- 2026-06-24T16:31:35+02:00 - OPEN: F5 abierta tras F2 PASS (`134036e`). Pendiente research Claude CLI antes de cualquier write.
- 2026-06-24T16:36:00+02:00 - RESEARCH PASS/BLOCKED: topologia documentada; implementacion debe empezar por dry-run sin writes. Apply/live edges bloqueado hasta target seguro o aprobacion RSO explicita.
