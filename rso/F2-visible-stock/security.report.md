# RHO Security Report — F2 Visible Stock

**Role:** rho-security (verificador independiente)
**Repo:** `k8s-skirmshop-competitor-crawler-pocharlies`
**Rama:** `codex/competitor-crawler-F2-visible-stock`
**Date:** 2026-06-24
**Auditor:** Claude (RSO delegado por Codex/PMO)

---

## Scope

Archivos inspeccionados en el diff F2 (main → HEAD):

| Archivo | Estado |
|---|---|
| `src/adapters/base.py` | Nuevo en F2 |
| `src/adapters/generic_html.py` | Nuevo en F2 |
| `src/extractor.py` | Nuevo en F2 |
| `src/dry_run.py` | Nuevo en F2 |
| `src/stock.py` | Nuevo en F2 |
| `tests/test_adapters.py` | Nuevo en F2 |
| `tests/test_stock.py` | Nuevo en F2 |
| `rso/F2-visible-stock/pilot-visible-stock.json` | Artefacto piloto |
| `rso/F2-visible-stock/visible-stock-sample.json` | Muestra etiquetada |
| `src/fetcher.py` | Preexistente — inspeccionado por residual risk |
| `src/push_client.py` | Preexistente — inspeccionado por residual risk |

---

## RHO Security Checklist

### Directives
- [x] No editar código de producto salvo vulnerabilidad crítica; reportar BLOCKED primero.
- [x] Solo comandos read-only + validaciones.
- [x] Evidencia directa para cada `[x]`.

---

### Acceptance Criteria

- [x] **SC-1: F2 usa solo GET público a competidor — no cart/checkout/login/account.**

  Evidence:
  ```
  # generic_html.py — único método HTTP usado:
  resp = await client.get(url)   # línea 51

  # extractor.py SKIP_PATH_HINTS (línea 164):
  "/cart", "/checkout", "/account", "/login", "/register"

  # grep "cart|checkout|login|account" en archivos F2:
  → Solo aparece en SKIP_PATH_HINTS (extractor.py:164) — se usan para EXCLUIR esas rutas.
  ```
  PASS.

- [x] **SC-2: No POST/PUT/PATCH/DELETE contra competidores en cambios F2.**

  Evidence:
  ```
  grep -n "POST\|PUT\|PATCH\|DELETE" src/adapters/generic_html.py src/adapters/base.py
    src/extractor.py src/dry_run.py src/stock.py
  → Sin resultados.

  httpx.AsyncClient solo usa .get() en generic_html.py y fetcher.py.
  ```
  PASS.

- [x] **SC-3: dry_run.py no importa ni llama push_client ni Brain push.**

  Evidence:
  ```
  grep -n "import|from" src/dry_run.py:
    from __future__ import annotations
    import argparse, asyncio, json, logging, sys
    from pathlib import Path
    from src.adapters.generic_html import GenericHtmlAdapter  (dentro de _pick_adapter_class)

  → push_client, BRAIN_URL, brain → no aparecen en ningún import ni llamada de dry_run.py.
  ```
  PASS.

- [x] **SC-4: Output piloto no expone campos de stock prohibidos.**

  Campos prohibidos auditados: `availability` (raw URL), `stock_qty`, `quantity`, `qty`,
  `qty_available`, `units_left`, `count` (por producto), `in_stock` (campo booleano),
  `out_of_stock` (campo booleano), ni stock numérico.

  Evidence:
  ```python
  # Escaneo automático de pilot-visible-stock.json (42 productos):
  banned = {'availability','stock_qty','quantity','qty','qty_available',
            'units_left','in_stock','out_of_stock'}
  → BANNED FIELDS FOUND: ninguno.

  Stock status values en productos: {'in_stock'}   ← valor cualitativo F2, no booleano
  Stock method values en productos: {'visible'}
  ```

  **Nota de interpretación:** El campo `stock_status` con valores `"in_stock"` / `"out_of_stock"` /
  `"unknown"` es la **feature F2 intencionada** (label cualitativo normalizado desde schema.org).
  No es el campo booleano `in_stock` prohibido. El campo booleano `in_stock` está listado en
  `_F1_STOCK_FIELDS` y es stripeado por `_normalize` (verificado en `base.py` y test
  `test_normalize_strips_f1_stock_fields`). No hay ningún campo de cantidad numérica por producto.

  PASS.

- [x] **SC-5: F2 no implementa F3/F4/F5/F6/F7; sin k8s/deploy/prod/CronJob.**

  Evidence:
  ```
  grep -rn "F3|F4|F5|F6|F7|CronJob|cart_probe|push_client|BRAIN_URL" \
    src/stock.py src/dry_run.py src/adapters/
  → Sin resultados.

  CHECKLIST.md directive: "Prohibido historico append-only (F3), cart-probe/cantidad exacta/carrito (F4),
  matching PRODUCT_MATCH (F5), comparacion viva (F6), scheduling nocturno (F7)."
  → F2 diff no toca Dockerfile, docker-compose, ningún manifiesto k8s.
  ```
  PASS.

- [x] **SC-6: Riesgo residual de src/fetcher.py y src/push_client.py — fuera del path F2.**

  Evidence:
  ```
  src/fetcher.py:23 → client.get(url)  # solo GET, sin escrituras
  src/push_client.py:30 → client.post(...)  # POST a brain en batches

  dry_run.py: NO importa fetcher.py ni push_client.py.
  src/adapters/generic_html.py: NO importa fetcher.py ni push_client.py (usa httpx propio).
  src/stock.py: NO importa push_client.py.
  ```
  Estos archivos son **preexistentes** y usados por `src/main.py` / `src/crawler.py`
  (fuera del scope F2 dry-run). Están aislados del path F2. Riesgo residual catalogado
  en sección de riesgos.

  PASS — fuera de path F2.

- [x] **SC-7: Test suite pasa.**

  Evidence:
  ```
  cd /home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies
  python3 -m pytest tests/ -q
  → 53 passed in 0.18s
  ```
  PASS (CHECKLIST.md reportaba 52; actual run = 53, ningún fallo).

---

## Findings

### FINDING-SEC-01 — PASS: Única superficie de red en F2 es GET público a catálogo
`GenericHtmlAdapter.fetch_page()` usa `httpx.AsyncClient.get()` con User-Agent declarativo
`SkirmshopCrawler/1.0`. No hay llamadas a endpoints privados. SKIP_PATH_HINTS excluye
explícitamente `/cart`, `/checkout`, `/account`, `/login`, `/register`.

### FINDING-SEC-02 — PASS: dry_run completamente aislado de Brain push
El módulo `push_client.py` (que hace POST al Brain) no está en ningún import de `dry_run.py`
ni de ningún otro archivo nuevo en F2. El path F2 es: `dry_run.py → GenericHtmlAdapter →
extractor.py + stock.py → JSON file`. Sin side-effects externos.

### FINDING-SEC-03 — OBSERVACIÓN: stock_status="in_stock" en output es label F2, no booleano prohibido
La directiva prohibía `in_stock`/`out_of_stock` como **campos booleanos**. El F2 usa
`stock_status` con valores string `"in_stock"/"out_of_stock"/"unknown"` — es el contrato
F2 definido en CHECKLIST y documentado en `src/stock.py`. No es una violación.
Los campos booleanos `in_stock`/`out_of_stock` están correctamente stripeados por `_normalize`.

### FINDING-SEC-04 — OBSERVACIÓN residual: push_client.py preexistente con POST a Brain
`src/push_client.py` realiza POST a `BRAIN_URL` (variable de entorno). No está en el path F2.
Queda fuera del scope de esta auditoría pero se registra como **superficie de riesgo residual**
que debe auditarse en la fase de producción (F7/CronJob) antes de cualquier deploy nocturno.

---

## Fixes / Mitigations Required

**Ninguno.** Todos los checks pasan sin vulnerabilidades críticas en el scope F2.

---

## Residual Security Risks

| ID | Riesgo | Severidad | Estado |
|---|---|---|---|
| RR-01 | `push_client.py` hace POST a Brain con `BRAIN_URL` de env — si mal configurado en prod podría filtrar datos de competidores. | Media | Fuera de path F2. Auditar en F7/deploy. |
| RR-02 | `User-Agent` declarativo (`SkirmshopCrawler/1.0`) identifica el crawler — competidor podría bloquearlo. | Baja | Operacional, no de seguridad. |
| RR-03 | No hay rate-limiting en `GenericHtmlAdapter` — posible ban por IP o DDoS accidental. | Baja | F4/F7 scope; no aplica a F2 dry-run single-domain. |
| RR-04 | `pilot-visible-stock.json` almacena URLs de productos de competidor en el repo — datos públicos, bajo riesgo legal. | Muy baja | Datos públicos indexados. |

---

## Verification Summary

| Check | Comando / Evidencia | Resultado |
|---|---|---|
| Solo GET público | `grep -n "POST\|PUT\|PATCH\|DELETE" src/adapters/*.py src/dry_run.py src/stock.py` | PASS — sin resultados |
| No cart/checkout/login en F2 | `grep -n "cart\|checkout\|login" src/adapters/*.py src/dry_run.py` → solo en SKIP_PATH_HINTS | PASS |
| dry_run sin push_client | `grep -n "import" src/dry_run.py` | PASS — sin push_client |
| Pilot sin banned fields | Python scan automatizado sobre 42 productos | PASS — ningún campo prohibido |
| No stock numérico en pilot | Python scan + revisión manual pilot-visible-stock.json | PASS |
| No F3/F4/F5/F6/F7 en F2 | `grep -rn "F3\|F4\|CronJob\|push_client\|BRAIN_URL" src/stock.py src/dry_run.py src/adapters/` | PASS |
| Tests | `python3 -m pytest tests/ -q` | PASS — 53/53 |

---

**Veredicto:** **SECURITY PASS** — F2 Visible Stock dentro de scope, sin escrituras a competidores, sin exposición de datos prohibidos, sin scope creep F3+, dry_run completamente aislado de Brain push.
