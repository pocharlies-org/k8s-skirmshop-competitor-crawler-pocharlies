# RHO Checklist - F4 Cart-Probe

> Fase **F4** del `RSO-MASTER-PLAN.md`.
> Gate previo requerido: F0/F1/F2/F3/F5 PASS. Orden aprobado: `F0 -> F1 -> (F2 || F5) -> F3 -> F4 -> F6 -> F7`.
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/SQL output). No abrir F6/F7 sin PASS F4.

## Objective
- [ ] Implementar y validar `skirmshop-stock-prober`: cart-probe agresivo pero acotado, con busqueda binaria de cantidad maxima, limpieza de carrito verificada, kill-switch 403/429/challenge, calibracion vs stock visible en muestra de 10, e integracion F3 append-only (`stock_qty`, `stock_method=cart_probe`) sin tocar F6/F7. Evidence:

## Directives
- [ ] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Claude implementa/prueba; Codex re-ejecuta evidencia antes de cerrar F4. Evidence:
- [x] F4 se abre solo tras F3 PASS. Evidence: crawler commit `e23659b`; infra commit `a6e64e9`; F3 checklist Objective `[x]`.
- [ ] Prohibido checkout, login, cuentas, aceptacion de ToS, CAPTCHA solvers, bypass anti-bot o acciones que degraden sitios. Evidence:
- [ ] Primeras pruebas deben ser unitarias/mocked. Cualquier cart-probe live requiere dominio green aprobado, limite bajo, UA honesto, cleanup probado y log de no-checkout. Evidence:
- [ ] Cloudflare/CAPTCHA/challenge/red tier => `blocked_by_antibot`, no forzar; silverback/red no se probea. Evidence:
- [ ] Sesion efimera por producto/variante; `/cart/clear.js` o equivalente al terminar, incluso en error; no dejar carritos sucios. Evidence:
- [ ] Kill-switch por dominio: primer 403/429/challenge sostenido aborta probe del dominio, cae a visible/unknown, cooldown 24-48h, metrica `competitor_crawl_block_total{domain,reason}`. Evidence:
- [ ] Egress aislado definido antes de produccion; no activar CronJob/nocturno ni replicas productivas en F4. Evidence:
- [ ] No F6: no tocar comparacion viva `prices.py`/`intel.py`, no depender de `PRODUCT_MATCH` nuevo. Evidence:
- [ ] No F7: no scheduling productivo, no CronJob activo. Evidence:
- [ ] No secretos/cookies/HTML crudo en logs/RSO; snapshots solo URI/key si aplica. Evidence:
- [ ] Git: rama `codex/competitor-crawler-F4-cart-probe`; fetch+rebase antes de commit; push inmediato; nunca force-push ni tocar `deploy/prod` directamente. Evidence:

## Acceptance Criteria
- [x] **Research de plataforma completo.** Confirmar repo destino (`skirmshop-stock-prober` nuevo vs modulo en repo actual), patrones existentes de Playwright/HTTP, dominios green candidatos, robots/antibot/tier, y si existe egress aislado. Evidence: `researcher.report.md`; branch/gates confirmed; recommendation is in-repo `src/prober/` + disabled deployment; all current green targets are `generic_html`; no green Shopify/Woo; no NetworkPolicy exists.
- [x] **Contrato de datos F4 definido.** `probe_stock(...)` o equivalente devuelve `domain`, `product_key`, `variant_id/url`, `stock_qty`, `stock_status`, `stock_method=cart_probe`, `probe_status`, `block_reason`, `cleanup_status`, `observed_at`, y errores explicitos. Evidence: `architect.report.md`; `ProbeResult` contract and mapper to F3 `Observation` defined; no F3 schema change required.
- [ ] **Shopify probe mock PASS.** Busqueda binaria o parse de 422 para maxima cantidad disponible; tests cubren in-stock, unavailable, qty limite, 403/429, challenge y cleanup. Evidence:
- [ ] **WooCommerce probe mock PASS.** Usa `quantity_limits.maximum` si disponible o respuesta add-to-cart; tests cubren mismas ramas de seguridad. Evidence:
- [ ] **Generic probe policy PASS.** GenericHtml solo probea si hay patron add-to-cart seguro y testeado; si no, `unknown/blocked` sin forzar. Evidence:
- [ ] **Cleanup verificado.** Cada probe termina con clear cart o cleanup equivalente; tests prueban cleanup tambien cuando add-to-cart falla. Evidence:
- [ ] **Kill-switch verificado.** Smoke mocked 403/429/challenge activa cooldown y bloquea probes posteriores del dominio; metrica/log estructurado presente. Evidence:
- [ ] **Integracion F3 PASS.** Resultado cart-probe se puede escribir via F3 writer como observacion append-only con `stock_qty` numerico y `stock_method=cart_probe`; idempotencia se mantiene. Evidence:
- [ ] **Calibracion muestra 10 PASS.** Tabla probe vs visible/ground-truth para dominio green aprobado; discrepancias clasificadas; cero checkout/login; cleanup log por producto. Evidence:
- [ ] **Security PASS.** No secretos, no cookies persistentes, no PII, no CAPTCHA solving, no checkout, rate limits/cooldown, dominio red bloqueado. Evidence:
- [ ] **DevOps PASS.** Microservicio/manifiestos si existen quedan disabled por defecto (`replicas:0`/activation disabled), egress aislado documentado, server dry-run PASS, no live production schedule. Evidence:
- [ ] **Verifier PASS.** Re-ejecuta tests, smoke kill-switch, diff scope, security scan y evidencia de cleanup/calibracion. Evidence:

## Specialist Checks
- [x] **rho-researcher** - repo destino, plataformas, dominios candidatos, robots/antibot, egress actual. Evidence: `researcher.report.md`; Claude CLI read-only PASS; live calibration target blocked for lack of green Shopify/Woo.
- [x] **rho-architect** - contrato probe, boundaries F4/F3/F6/F7, modelo de cooldown/metrics. Evidence: `architect.report.md`; Claude CLI read-only PASS; live calibration remains blocked.
- [ ] **rho-backend** - probe core, transports mockables, integracion F3 writer, tests. Evidence:
- [ ] **rho-devops** - microservicio/k8s/egress/dry-run/no Cron activo. Evidence:
- [ ] **rho-security** - anti-bot/legal/no checkout/no login/no CAPTCHA/no dirty carts. Evidence:
- [ ] **rho-verifier** - re-ejecuta tests/smokes/diff/evidencia. Evidence:
- [ ] **Codex/RSO auditor** - decide PASS/BLOCKED y no abre F6 hasta PASS. Evidence:

## Status (log datado, append-only)
- 2026-06-25T00:34:26+02:00 - OPEN: F4 abierta tras F3 PASS. Rama `codex/competitor-crawler-F4-cart-probe` creada y publicada. Pendiente research Claude CLI antes de implementar probe o tocar dominios reales.
- 2026-06-25T00:52:00+02:00 - RESEARCH PASS / LIVE CALIBRATION BLOCKED: `rho-researcher` read-only confirma que no hay Shopify/Woo green; todos los green son `generic_html`, no hay NetworkPolicy/egress isolation, y F3 writer ya soporta `cart_probe`. RSO decide avanzar con mocks + modulo in-repo y mantener calibracion live bloqueada hasta aprobar target seguro.
- 2026-06-25T00:58:00+02:00 - ARCHITECT PASS: `rho-architect` define `ProbeResult`, mapper a F3 `Observation`, `src/prober/` in-repo, Generic default-deny, `DomainGuard` cooldown/metrics y matriz T1-T20. Live calibration sigue bloqueada por falta de target green Shopify/Woo y NetworkPolicy.
