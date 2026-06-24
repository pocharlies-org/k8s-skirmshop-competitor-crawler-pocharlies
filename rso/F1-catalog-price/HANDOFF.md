# HANDOFF - F1 Catalog + Price

Rol: Claude CLI = EJECUTOR. Codex = RSO/PMO/auditor.

Repo: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`
Rama obligatoria: `codex/competitor-crawler-F1-catalog-price`

Antes de tocar nada:
1. `git fetch origin`
2. `git pull --rebase --autostash`
3. Confirma que estás en `codex/competitor-crawler-F1-catalog-price`
4. Lee:
   - `RSO-MASTER-PLAN.md`
   - `rso/F0-bootstrap/CHECKLIST.md`
   - `rso/F1-catalog-price/CHECKLIST.md`
   - `data/competitors/fingerprint.json`

Objetivo F1:
Implementa catálogo + precio para 1 dominio piloto `green` usando un framework `BaseSiteAdapter` JSON-first. El gate F1 es un `dry-run` auditable de un dominio que devuelva >=10 productos con `price != null`, ratio de fallos <20%, 5 ejemplos, tests y cero cart/checkout/login/write.

Scope permitido:
- `src/**`
- `tests/**`
- `requirements.txt` si hace falta una dependencia razonable
- `rso/F1-catalog-price/*.report.md`
- `rso/F1-catalog-price/pilot-smoke.json` o artefacto equivalente
- `rso/F1-catalog-price/CHECKLIST.md` SOLO para marcar `[x]` con Evidence real

Scope prohibido:
- No tocar `k8s/**`, deploy/prod, CronJobs, imágenes o producción nocturna.
- No implementar F2/F3/F4/F5/F6/F7.
- No cart-probe, no checkout, no login/account, no POST/PUT/PATCH/DELETE a competidores, no CAPTCHA solving.
- No ampliar `config.yaml` como fuente de verdad runtime.

Roles obligatorios:
1. `rho-researcher`: preflight read-only de dominios `green` de `fingerprint.json` y selección de piloto.
2. `rho-architect`: contrato `BaseSiteAdapter` y frontera F1 vs F2/F4.
3. `rho-backend`: implementación + tests + dry-run smoke.
4. `rho-security`: auditoría anti-bot: solo GET público, cero cart/write.
5. `rho-verifier`: re-ejecuta comandos y valida artefacto/diff.

Acceptance que debes cerrar en `CHECKLIST.md`:
- `BaseSiteAdapter` incorporado.
- Piloto `green` seleccionado desde F0.
- Dry-run auditable documentado.
- Dry-run devuelve >=10 productos con `title`, `url`, `price != null`, `domain`, `source_id` estable y fallos <20%.
- 5 ejemplos reales en `backend.report.md`.
- Cero stock/cart/write.
- Tests relevantes pasan.
- `py_compile`, `pytest`, `git diff --check` limpios.

Comandos mínimos esperados:
```bash
python3 -m py_compile src/*.py tests/*.py
python3 -m pytest tests/ -q
git diff --check
```

Al terminar:
1. Escribe los reports por rol en `rso/F1-catalog-price/`.
2. Actualiza `CHECKLIST.md` con `[x]` y Evidence.
3. `git status --short --branch`
4. `git fetch origin && git pull --rebase --autostash`
5. Commit atómico.
6. Push inmediato.
7. Devuelve resumen + checklist + comandos + archivos tocados + riesgos.

No abras F2/F5. Codex audita F1 y solo entonces abre la siguiente fase.
