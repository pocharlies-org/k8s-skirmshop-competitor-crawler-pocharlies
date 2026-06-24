# RHO Architect Report — F2 Visible Stock

**Date:** 2026-06-24
**Role:** rho-architect (implementer delegado, invocado por Codex RSO/PMO)
**Scope:** Contrato de datos F2, plan técnico, fronteras módulo, separación F2 vs F4.
**NO genera código de producto, NO hace commit, NO despliega.**

---

## RHO Architect Checklist

### Directives
- [x] Solo artefactos de reporte; NO código de producto, NO git, NO redelegación.
- [x] Solo `GET` público contra competidores; prohibido cart/checkout/login/account/POST/PUT/PATCH/DELETE.
- [x] No exponer `stock_qty`/`quantity`/`qty` ni cantidad numérica.
- [x] Preservar F1 (catálogo+precio); no romper campos `title`/`url`/`price`/`domain`/`source_id`.
- [x] Separar claramente F2 (stock visible) de F4 (cart-probe/cantidad exacta).
- [x] Sin F3/F4/F5/F6/F7; sin Brain push; sin k8s/CronJob/producción.

### Acceptance Criteria — Architect scope
- [x] **Contrato F2 definido.** Campos `stock_status` y `stock_method` especificados con dominio de valores, tipos, semántica y campos prohibidos. Evidence: §3 de este informe.
- [x] **Mapping availability→stock_status completo.** Todos los valores schema.org relevantes mapeados con política de fallback `unknown`. Evidence: §4.
- [x] **Frontera F2 vs F4 documentada.** F2 = observación pasiva visible; F4 = cart-probe activo cantidad exacta. Evidence: §6.
- [x] **Módulos afectados identificados.** Lista de archivos candidatos con cambios mínimos y justificación. Evidence: §5.
- [x] **Compatibilidad F1 verificada.** `_F1_STOCK_FIELDS` en `base.py` debe evolucionar sin romper campos F1. Evidence: §5.2.
- [x] **Riesgos residuales documentados.** Evidence: §7.

---

## 1. Contexto: estado post-F1

Inspeccionados:

| Archivo | Relevancia |
|---|---|
| `src/extractor.py` | Extrae `availability` desde JSON-LD (`offers.availability`); NO la extrae en método microdata; OG no la extrae. |
| `src/adapters/base.py` | `_F1_STOCK_FIELDS` incluye `availability`, `stock`, `stock_status`, `quantity`, `qty`, `in_stock`, `out_of_stock`. `_normalize()` los ELIMINA del output. |
| `src/adapters/generic_html.py` | Delega extracción a `src/extractor.py`; sin lógica de stock. |
| `src/dry_run.py` | (no leído en este pass, pero irrelevante para contrato). |
| `tests/test_adapters.py` | (no leído; afectado por cambio de contrato en §5). |

**Hallazgo clave:** `_from_jsonld_product()` ya propaga `availability` al dict raw, pero `_normalize()` lo elimina antes de la salida. El dato existe internamente y puede ser consumido antes de la eliminación. Esto es el punto de inserción de F2 con impacto mínimo.

---

## 2. Objetivo arquitectónico de F2

Convertir el campo raw `availability` (schema.org URL o string libre) en dos campos normalizados, públicos y sin cantidad:

```
stock_status: "in_stock" | "out_of_stock" | "unknown"
stock_method: "visible" | "unknown"
```

La normalización ocurre dentro del pipeline de `_normalize()` en `BaseSiteAdapter`, antes de que `_F1_STOCK_FIELDS` elimine el raw.

---

## 3. Contrato F2 — definición formal

### 3.1 Campos añadidos al output de producto

```python
# Adición a cada dict de producto (sobre los campos F1 ya existentes)
"stock_status": Literal["in_stock", "out_of_stock", "unknown"]
"stock_method": Literal["visible", "unknown"]
```

**Semántica:**

| Campo | Valor | Significado |
|---|---|---|
| `stock_status` | `in_stock` | El competidor muestra el producto como disponible/comprable. |
| `stock_status` | `out_of_stock` | El competidor muestra explícitamente agotado/no disponible. |
| `stock_status` | `unknown` | No hay evidencia visible/estructurada. **Nunca inferir agotado por ausencia.** |
| `stock_method` | `visible` | El estado se obtuvo de dato estructurado visible público (JSON-LD, microdata). |
| `stock_method` | `unknown` | No se encontró evidencia estructurada; `stock_status` debe ser `unknown`. |

### 3.2 Campos PROHIBIDOS en output F2

Los siguientes campos NUNCA deben aparecer en el dict de producto entregado:

```
stock_qty, quantity, qty, availability (raw), in_stock (bool), out_of_stock (bool),
stock (genérico), qty_available, units_left, count, units
```

`availability` raw puede circular internamente como variable local durante `_normalize()` pero **no debe persistir en el dict de salida**.

### 3.3 Invariante F1 preservada

Los campos F1 (`title`, `url`, `price`, `domain`, `source_id`) no se modifican. El criterio de descarte de `run()` (`not title` o `price is None`) se mantiene sin cambios.

### 3.4 Tipo Python (referencia para rho-backend)

```python
from typing import Literal

StockStatus = Literal["in_stock", "out_of_stock", "unknown"]
StockMethod = Literal["visible", "unknown"]
```

No se añade dataclass ni TypedDict en F2; el dict sigue siendo `dict[str, Any]` para compatibilidad con el pipeline existente.

---

## 4. Mapping `availability` → `stock_status`

### 4.1 Valores schema.org canónicos

**Codex RSO reconciliation (2026-06-24):** el handoff F2 aprobado trata `PreOrder`,
`PreSale` y `BackOrder` como ambiguos para stock visible del piloto. Por tanto, el
contrato final los normaliza a `unknown/unknown`, no a `in_stock/visible`.

| `availability` raw (URL o string) | `stock_status` | `stock_method` | Notas |
|---|---|---|---|
| `https://schema.org/InStock` | `in_stock` | `visible` | Caso más común. |
| `InStock` | `in_stock` | `visible` | Sin URL base. |
| `https://schema.org/LimitedAvailability` | `in_stock` | `visible` | Pocas unidades, pero comprable. |
| `LimitedAvailability` | `in_stock` | `visible` | |
| `https://schema.org/PreOrder` | `unknown` | `unknown` | Pedido anticipado: ambiguo en F2, no inferir stock visible. |
| `PreOrder` | `unknown` | `unknown` | |
| `https://schema.org/PreSale` | `unknown` | `unknown` | Preventa: ambiguo en F2. |
| `PreSale` | `unknown` | `unknown` | |
| `https://schema.org/BackOrder` | `unknown` | `unknown` | Pedido bajo reposicion: ambiguo en F2. |
| `BackOrder` | `unknown` | `unknown` | |
| `https://schema.org/OutOfStock` | `out_of_stock` | `visible` | |
| `OutOfStock` | `out_of_stock` | `visible` | |
| `https://schema.org/SoldOut` | `out_of_stock` | `visible` | |
| `SoldOut` | `out_of_stock` | `visible` | |
| `https://schema.org/Discontinued` | `out_of_stock` | `visible` | Descontinuado = no disponible. |
| `Discontinued` | `out_of_stock` | `visible` | |
| `https://schema.org/OnlineOnly` | `in_stock` | `visible` | Solo online, pero disponible. |
| `OnlineOnly` | `in_stock` | `visible` | |
| `""` (vacío) | `unknown` | `unknown` | Sin dato. |
| `None` | `unknown` | `unknown` | Sin dato. |
| Cualquier otro valor | `unknown` | `unknown` | Fallback seguro; no inferir. |

### 4.2 Implementación del mapping (pseudocódigo para rho-backend)

```python
_INSTOCK_TOKENS = frozenset({
    "instock", "limitedavailability", "instoreonly", "onlineonly",
})
_OUTOFSTOCK_TOKENS = frozenset({
    "outofstock", "soldout", "discontinued",
})

def normalize_availability(raw: str | None) -> tuple[StockStatus, StockMethod]:
    """Map raw schema.org availability to (stock_status, stock_method).

    Accepts full URL form (https://schema.org/InStock) or short form (InStock).
    Case-insensitive. Returns ('unknown', 'unknown') for any unrecognized value.
    """
    if not raw:
        return "unknown", "unknown"
    # Strip URL prefix; normalize case
    token = raw.rsplit("/", 1)[-1].lower().strip()
    if token in _INSTOCK_TOKENS:
        return "in_stock", "visible"
    if token in _OUTOFSTOCK_TOKENS:
        return "out_of_stock", "visible"
    return "unknown", "unknown"
```

### 4.3 Ubicación final

La implementación final vive en **`src/stock.py`** para mantener la normalización
como función pura y reutilizable, separada de la extracción HTML. `src/adapters/base.py`
consume esa función antes de eliminar campos raw.

---

## 5. Archivos candidatos y cambios mínimos

### 5.1 `src/extractor.py`

**Cambio 1:** Mantener en `src/extractor.py` solo la extracción de `availability` raw.
La normalización final se implementa en `src/stock.py`.

**Cambio 2:** Añadir extracción de `availability` en el **método microdata** (Método 3). Actualmente no la extrae. Añadir:

```python
avail = item.find(itemprop="availability")
# ...
"availability": (avail.get("content") or avail.get("href") or avail.get_text(strip=True)) if avail else "",
```

El método OG (Método 2) rara vez publica availability; se puede omitir en F2 (deja `availability=""` → `unknown`). Documentar esto explícitamente en el código con un comentario.

### 5.2 `src/adapters/base.py`

**Cambio 1:** Modificar `_normalize()` para:
1. Leer `availability` del dict raw **antes** de filtrar.
2. Llamar a `normalize_availability()`.
3. Añadir `stock_status` y `stock_method` al dict de salida.
4. Mantener `_F1_STOCK_FIELDS` intacto (sigue eliminando `availability` raw y campos numéricos).

```python
from src.stock import normalize_availability  # nuevo import

def _normalize(self, raw: dict, page_url: str) -> dict:
    product_url = raw.get("url") or page_url
    source_id = f"competitor:{self.domain}:{product_url}"
    # F2: normalizar antes de filtrar
    stock_status, stock_method = normalize_availability(raw.get("availability"))
    filtered = {k: v for k, v in raw.items() if k not in self._F1_STOCK_FIELDS}
    return {
        **filtered,
        "domain": self.domain,
        "url": product_url,
        "source_id": source_id,
        "stock_status": stock_status,
        "stock_method": stock_method,
    }
```

**Cambio 2:** Actualizar `_F1_STOCK_FIELDS` — añadir tokens que podrían colarse como clave raw:

```python
_F1_STOCK_FIELDS: frozenset = frozenset({
    "availability", "stock", "stock_status", "quantity", "qty",
    "in_stock", "out_of_stock",
    # F2-guard: prevenir raw quantity-like keys
    "stock_qty", "qty_available", "units_left",
})
```

Nota: `stock_status` está en `_F1_STOCK_FIELDS`, pero se añade de vuelta con el valor normalizado después del filtrado. Esto es correcto porque el orden es: filtrar raw → añadir normalizado.

### 5.3 `tests/test_stock.py`

Añadir tests unitarios para `normalize_availability()`:
- Todos los tokens `_INSTOCK_TOKENS` → `("in_stock", "visible")`
- Todos los tokens `_OUTOFSTOCK_TOKENS` → `("out_of_stock", "visible")`
- URL completa (`https://schema.org/InStock`) → `("in_stock", "visible")`
- String vacío y None → `("unknown", "unknown")`
- Token desconocido → `("unknown", "unknown")`
- Case insensitive (`INSTOCK`, `InStock`) → correcto

### 5.4 `tests/test_adapters.py`

Añadir tests de `BaseSiteAdapter._normalize()`:
- Con `availability=InStock` en raw → output tiene `stock_status="in_stock"`, `stock_method="visible"`.
- Con `availability=""` → `stock_status="unknown"`, `stock_method="unknown"`.
- Output NO contiene `availability`, `qty`, `stock_qty`.
- Campos F1 (`title`, `url`, `price`, `domain`, `source_id`) siguen presentes.

---

## 6. Frontera F2 vs F4 (decisión arquitectónica)

```
F2 — Visible Stock (este alcance)
├── Solo lectura pasiva de datos estructurados públicos (JSON-LD, microdata)
├── Un único GET por página de producto (mismo que F1)
├── Output: stock_status/stock_method binario normalizado
├── Sin sesión, sin cookies de carrito, sin JS de checkout
└── Microservicio: este crawler (k8s-skirmshop-competitor-crawler-pocharlies)

F4 — Cart-Probe (fuera de alcance, PROHIBIDO en F2)
├── JS headless (Playwright) simulando añadir al carrito
├── Búsqueda binaria de cantidad máxima aceptada
├── Requiere limpiar carrito después de cada probe
├── Output: stock_qty (cantidad exacta) — PROHIBIDO en F2
└── Microservicio: skirmshop-stock-prober (repo separado, aislado)
```

**Decisión de diseño:** F2 NO debe dejar ningún campo de cantidad ni "hint" que un consumidor posterior pueda malinterpretar como resultado de cart-probe. Los campos `stock_status`/`stock_method` son los únicos contratos públicos de F2.

**Decisión de diseño:** Si `leopard.es` no publica `availability` en JSON-LD para todos sus productos, el output correcto es `stock_status=unknown`, NO intentar inferirlo de texto HTML ("En stock", "Agotado") en F2. El scraping de texto libre de estado de stock queda como mejora futura explícita (F2-ext, si Codex lo aprueba), no en este alcance.

---

## 7. Riesgos residuales

| # | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| R-1 | `leopard.es` puede no publicar `availability` en JSON-LD en todas las fichas → ratio alto de `unknown`. | Bajo | Aceptable; `unknown` es la respuesta correcta. Documentar en `visible-stock-sample.json`. |
| R-2 | Microdata en `leopard.es` puede tener `availability` en `<link itemprop="availability" href="...">` (no `<span>`). | Medio | El parser microdata propuesto lee `href` con fallback a `content` y `get_text`. Verificar en dry-run. |
| R-3 | `normalize_availability` con token desconocido retorna `unknown` silenciosamente. Tokens no documentados de plataformas no-schema.org (ej. "disponible", "sin stock" en texto libre). | Bajo | Fuera del alcance de F2. No inferir; `unknown` seguro. |
| R-4 | `_F1_STOCK_FIELDS` filtra `stock_status` antes de que se añada el normalizado. Si el orden del merge cambia, puede perderse. | Medio | El `**filtered` va primero en el dict return; luego los campos explícitos (`stock_status`, `stock_method`) sobrescriben cualquier colisión. Agregar test de contrato explícito. |
| R-5 | Si un adaptador futuro (no `GenericHtmlAdapter`) pasa un raw con `stock_status` ya normalizado, `_F1_STOCK_FIELDS` lo eliminará y se recalculará desde `availability`. | Bajo | Comportamiento correcto: la fuente de verdad es `availability` raw. Documentar en docstring de `_normalize()`. |

---

## 8. Resumen ejecutivo para rho-backend

1. **Implementar `normalize_availability(raw: str | None) -> tuple[StockStatus, StockMethod]`** en `src/extractor.py`. Función pura, sin I/O.
2. **Añadir extracción de `availability` en Método 3 (microdata)** en `src/extractor.py`.
3. **Modificar `BaseSiteAdapter._normalize()`** en `src/adapters/base.py` para llamar a `normalize_availability()` antes del filtrado y añadir `stock_status`/`stock_method` al output.
4. **Tests** en `test_extractor.py` y `test_adapters.py` cubriendo mapping, fallback `unknown`, ausencia de campos prohibidos y no-regresión F1.
5. **Dry-run** genera `rso/F2-visible-stock/pilot-visible-stock.json` con los nuevos campos; muestra etiquetada de 10 fichas en `visible-stock-sample.json`.

**Cambios fuera de alcance del arquitecto:** implementación concreta de código de producto, dry-run, muestra etiquetada, seguridad, verificación — responsabilidad de rho-backend, rho-security y rho-verifier.

---

## Files Inspected

- `RSO-MASTER-PLAN.md` — leído completo
- `rso/F2-visible-stock/CHECKLIST.md` — leído completo
- `rso/F2-visible-stock/HANDOFF.md` — leído completo
- `rso/F1-catalog-price/codex-audit.report.md` — leído completo
- `src/extractor.py` — leído completo
- `src/adapters/base.py` — leído completo
- `src/adapters/generic_html.py` — leído completo

## Files Touched

- `rso/F2-visible-stock/architect.report.md` — **ESTE ARCHIVO** (nuevo, solo reporte)

No se ha tocado código de producto, manifests, ni se ha hecho commit/push.

---

**Status:** PASS — Contrato definido, mapping completo, fronteras documentadas, riesgos explícitos. Listo para rho-backend.
