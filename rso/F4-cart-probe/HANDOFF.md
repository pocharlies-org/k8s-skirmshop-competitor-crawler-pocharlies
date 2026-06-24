# HANDOFF - F4 Cart-Probe

ROL: Claude CLI = EJECUTOR. Codex = RSO/PMO/auditor.

OBJETIVO F4:
Implementar y demostrar `skirmshop-stock-prober`: cart-probe agresivo con rails. Debe obtener cantidad maxima por busqueda binaria o limite de plataforma, limpiar carrito siempre, activar kill-switch ante 403/429/challenge, calibrar contra stock visible en muestra 10, y escribir/emitir observaciones compatibles con F3 append-only (`stock_qty`, `stock_method=cart_probe`).

GATES PREVIOS:
- F0 PASS.
- F1 PASS.
- F2 PASS.
- F5 PASS.
- F3 PASS en crawler commit `e23659b`; infra dry-run commit `a6e64e9`.
- F4 no abre F6/F7.

SCOPE:
- Repo RSO/crawler: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`
- Si decides microservicio nuevo, primero reporta repo/ruta propuesta y no crees repos remotos sin aprobacion RSO.
- Infra solo si hace falta manifiesto disabled/dry-run; usar rama/worktree `codex/*`, nunca `deploy/prod` directo.

DIRECTIVAS:
- Trabaja en rama `codex/competitor-crawler-F4-cart-probe`.
- `git fetch` + rebase antes de cada commit; push inmediato; nunca force-push.
- No checkout, no login, no cuentas, no CAPTCHA solver, no bypass anti-bot.
- No probes live hasta tener tests mocked PASS y dominio green aprobado por RSO.
- Cloudflare/CAPTCHA/red tier => `blocked_by_antibot`; no forzar.
- Sesion efimera por producto/variante y cleanup obligatorio (`/cart/clear.js` o equivalente) en success/fail.
- Kill-switch por dominio para 403/429/challenge sostenido: abortar, cooldown 24-48h, visible/unknown fallback, metrica `competitor_crawl_block_total{domain,reason}`.
- No F6: no tocar `prices.py`/`intel.py` ni comparacion viva.
- No F7: no CronJob nocturno activo ni scheduling productivo.
- No secretos/cookies/HTML crudo en logs/reportes.

CRITERIOS DE ACEPTACION:
- `rso/F4-cart-probe/CHECKLIST.md` actualizado con `[x]` solo si hay Evidence directa.
- Research: repo destino, plataformas, dominios green candidatos, robots/antibot, egress.
- Architect: contrato `probe_stock` y modelo de cooldown/metrics.
- Backend:
  - Shopify mock PASS: binary search o 422, unavailable, qty limite, 403/429/challenge, cleanup.
  - WooCommerce mock PASS: `quantity_limits.maximum` o add-to-cart response, mismas ramas.
  - Generic policy: solo probe seguro testeado; si no, unknown/blocked.
  - Integracion F3 writer: observacion append-only con `stock_qty` y `stock_method=cart_probe`.
- DevOps: manifiestos disabled por defecto si existen, egress documentado, dry-run server PASS, no Cron activo.
- Security: no checkout/login/CAPTCHA/dirty carts, rate/cooldown, no secretos.
- Calibracion: tabla probe vs visible/ground-truth muestra 10 en dominio green aprobado, cleanup log por producto.
- Verifier: re-ejecuta tests/smokes/diff/security scan.

ENTREGA:
- Reports por rol en `rso/F4-cart-probe/<rol>.report.md`.
- Checklist F4 reconciliado.
- Commits atomicos y push inmediato.
- No abrir F6/F7. Codex audita F4 despues.
