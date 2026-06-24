# Handoff To Claude: F0 Bootstrap

Rol: Claude = EJECUTOR. Codex = RSO/PMO/auditor. No avances de fase sin PASS
explícito de Codex.

Repo:
`/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`

Rama:
`codex/competitor-crawler-F0-bootstrap`

Plan maestro aprobado:
`/home/dibanez/.claude/plans/haz-uan-auditoria-completa-majestic-cherny.md`

## Git

- Trabaja en `codex/competitor-crawler-F0-bootstrap`.
- Ejecuta `git fetch` y rebase antes de cada commit.
- Haz commits atómicos.
- Push inmediato tras validar.
- Nunca hagas force-push.
- No toques `deploy/prod`.
- No empieces F1.

## F0 Scope

F0 es read-only hacia competidores salvo bootstrap del repo/registry:

1. Trae la fuente existente del crawler desde
   `sauvage:/home/ubuntu/skirmshop/skirmshop-competitor-crawler` al clon local.
2. Deriva top10 España + top20 Europa con MCP SimilarWeb y prepara la lista para curación/validación del usuario.
3. Pobla o prepara `CompetitorSource` como fuente única del registry.
4. Genera `fingerprint.json` para todos los dominios con:
   `platform`, `tier`, `has_structured_data`, `has_visible_stock`,
   `robots_crawl_delay`, `antibot`.
5. Usa Firecrawl/headless solo en lectura cuando haga falta. No eludas challenges.
6. Define/crea índices del grafo al arrancar brain para evitar scans:
   `Product.id`, `Product.sku`, y campos relevantes de `CompetitorProduct.*`.
7. No hagas cart-probe, checkout, login, account creation, ni ninguna request de escritura a competidores.

## Acceptance

Marca `[x]` con `Evidence:` reproducible en
`rso/F0-bootstrap/CHECKLIST.md` solo cuando tengas evidencia directa:

- Fuente del crawler importada en el clon local.
- Lista top10 ES + top20 EU derivada con SimilarWeb y lista para curación/validación.
- `CompetitorSource` poblado o preparado como registry.
- `fingerprint.json` cubre 100% de dominios objetivo.
- Cada fingerprint tiene `platform`, `tier`, `has_structured_data`, `has_visible_stock`, `robots_crawl_delay`, `antibot`.
- `silverback-airsoft.com` queda clasificado como `red`.
- Recuento por tier reportado.
- Índices del grafo definidos/creados.
- Cero requests de cart/escritura a competidores en F0.
- Reports escritos en `rso/F0-bootstrap/`.

## Required Roles

Usa subagentes Claude separados cuando aplique:

- `rho-researcher`: inventario de fuente en sauvage, repo local, registry y estado actual.
- `rho-architect`: esquema de fingerprint, flujo de registry, plan/definición de índices.
- `rho-security`: robots/antibot, prueba de cero cart/write requests, riesgos y rails.

Puedes añadir `rho-devops` si tocas manifiestos, jobs, secretos, CI/CD, red o k8s.
Puedes añadir `rho-verifier` antes del commit final si hay dudas.

## Required Reports

Escribe:

- `rso/F0-bootstrap/researcher.report.md`
- `rso/F0-bootstrap/architect.report.md`
- `rso/F0-bootstrap/security.report.md`
- cualquier otro `<role>.report.md` usado

Cada report debe incluir:

- scope,
- archivos inspeccionados/tocados,
- comandos ejecutados,
- evidencia,
- checklist `[ ]`/`[x]`/`[blocked: motivo]`,
- riesgos residuales.

## Closeout

Al terminar F0:

1. Actualiza `rso/F0-bootstrap/CHECKLIST.md` con evidencia real.
2. Ejecuta las pruebas/comandos mínimos necesarios.
3. Rebase contra remoto.
4. Commit atómico.
5. Push inmediato.
6. Avisa que F0 queda listo para auditoría Codex.

No empieces F1. Codex auditará F0 re-ejecutando los comandos de evidencia, no
leyendo solo el texto de los reports.
