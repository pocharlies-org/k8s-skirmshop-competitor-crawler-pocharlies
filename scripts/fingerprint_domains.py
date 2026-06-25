#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "domain", "url", "platform", "tier", "has_structured_data",
    "has_visible_stock", "robots_crawl_delay", "antibot", "http_status",
    "evidence", "observed_at",
}
UA = "skirmshop-competitor-crawler-fingerprint/0.1 (+research; read-only)"
TIMEOUT = 6
CTX = ssl.create_default_context()
# Antibot signals that force a `red` tier. A data endpoint reporting any of these is
# never ignored (fail-closed), even when the root page looks clean.
ANTIBOT_BLOCKING = frozenset({"captcha", "cloudflare", "http_429", "http_403"})


def _origin(url: str, domain: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return f"https://www.{domain}"


def _get(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read(512_000)
            return {"url": url, "status": int(resp.status), "body": raw.decode("utf-8", "ignore"), "error": None}
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read(256_000)
            body = raw.decode("utf-8", "ignore")
        except Exception:
            body = ""
        return {"url": url, "status": int(exc.code), "body": body, "error": f"HTTPError:{exc.code}"}
    except Exception as exc:
        return {"url": url, "status": None, "body": "", "error": type(exc).__name__ + ":" + str(exc)[:180]}


def _crawl_delay(robots_body: str) -> float | None:
    """Return the ``Crawl-delay`` (seconds) that applies to ``User-agent: *``.

    robots.txt is organized into groups. A group opens with one or more
    consecutive ``User-agent`` lines and is followed by its directives
    (``Disallow``, ``Allow``, ``Crawl-delay`` ...). The first directive line
    closes the run of agent declarations, so the next ``User-agent`` starts a
    fresh group. A ``Crawl-delay`` therefore belongs to the group whose agent
    set is currently in scope.

    Only a delay declared inside a group whose agents include the wildcard
    ``*`` is honored. Delays scoped to named crawlers (Ahrefs, MJ12, Pinterest
    and similar) are ignored so a competitor's aggressive throttling of SEO
    bots never leaks into our generic-agent crawl budget. Returns the first
    valid wildcard delay, or ``None`` when no wildcard group declares one.
    """
    current_agents: set[str] = set()
    collecting_agents = False  # True while consuming a run of User-agent lines
    for raw in robots_body.splitlines():
        line = raw.split("#", 1)[0].strip()  # drop inline comments + whitespace
        if not line:
            continue
        field, sep, value = line.partition(":")
        if not sep:
            continue
        field = field.strip().lower()
        value = value.strip().lower()
        if field == "user-agent":
            if not collecting_agents:
                # A directive closed the previous group: this opens a new one.
                current_agents = set()
                collecting_agents = True
            current_agents.add(value)
            continue
        # Any non-agent directive ends the current run of User-agent lines.
        collecting_agents = False
        if field == "crawl-delay" and "*" in current_agents:
            try:
                delay = float(value)
            except ValueError:
                continue
            if math.isfinite(delay) and delay >= 0:
                return delay
    return None


def _json_ok(body: str) -> Any | None:
    try:
        return json.loads(body)
    except Exception:
        return None


def _detect_antibot(status: int | None, body: str) -> str:
    b = (body or "").lower()
    if status == 429:
        return "http_429"
    if "captcha" in b or "g-recaptcha" in b or "hcaptcha" in b:
        return "captcha"
    if "cloudflare" in b or "cf-chl" in b or "just a moment" in b or "checking your browser" in b:
        return "cloudflare"
    if status == 403:
        return "http_403"
    if status is None:
        return "unknown"
    return "none"


def _shape_ok_shopify(body: str) -> bool:
    parsed = _json_ok(body)
    return isinstance(parsed, dict) and "products" in parsed


def _shape_ok_woocommerce(body: str) -> bool:
    parsed = _json_ok(body)
    return isinstance(parsed, list)


def _endpoint_clean(status: int | None, body: str, shape_ok: Any) -> bool:
    """A data endpoint is clean only if HTTP 200, correct JSON shape, and no antibot
    markers in the body (fail-closed against 200 challenge bodies / captcha JSON)."""
    return status == 200 and shape_ok(body) and _detect_antibot(status, body) == "none"


def _classify_platform(
    root: dict[str, Any], shopify: dict[str, Any], woo: dict[str, Any]
) -> tuple[str, str, str | None]:
    """Return (platform, platform_source, platform_endpoint).

    platform_source is "endpoint" only when a data endpoint returns HTTP 200 with the
    correct JSON shape AND no antibot markers. Otherwise the platform is inferred from
    root HTML ("html") or defaults ("none"). A blocked endpoint never yields "endpoint".
    """
    if _endpoint_clean(shopify.get("status"), shopify.get("body", ""), _shape_ok_shopify):
        return "shopify", "endpoint", "shopify"
    if _endpoint_clean(woo.get("status"), woo.get("body", ""), _shape_ok_woocommerce):
        return "woocommerce", "endpoint", "woocommerce"
    b = (root.get("body") or "").lower()
    if "cdn.shopify.com" in b or "shopify.theme" in b or "myshopify" in b:
        return "shopify", "html", None
    if "woocommerce" in b or "wp-content/plugins/woocommerce" in b:
        return "woocommerce", "html", None
    if root.get("status") == 200:
        return "generic_html", "none", None
    return "unknown", "none", None


def _effective_antibot(
    platform: str, platform_source: str, antibot_by_source: dict[str, str]
) -> str:
    """Endpoint-scoped antibot policy.

    - Shopify/Woo: a blocked data endpoint always wins (fail-closed). A clean data
      endpoint ("endpoint" source) scopes antibot away from the root page. Otherwise
      (HTML-inferred, inconclusive endpoint) the root governs.
    - generic_html / unknown / HTML-inferred: the root governs.
    """
    root_antibot = antibot_by_source["root"]
    if platform == "shopify":
        endpoint_antibot: str | None = antibot_by_source["shopify"]
    elif platform == "woocommerce":
        endpoint_antibot = antibot_by_source["woocommerce"]
    else:
        endpoint_antibot = None
    if platform in {"shopify", "woocommerce"}:
        if endpoint_antibot in ANTIBOT_BLOCKING:
            return endpoint_antibot  # fail-closed: blocked data endpoint => red
        if platform_source == "endpoint":
            return endpoint_antibot  # clean data endpoint relief (== "none")
        return root_antibot  # HTML-inferred platform, inconclusive endpoint
    return root_antibot


def _has_structured(body: str) -> bool:
    b = (body or "").lower()
    return any(token in b for token in ("application/ld+json", "og:price", "product:price", "itemprop=", "schema.org/product"))


def _has_stock(body: str) -> bool:
    b = (body or "").lower()
    tokens = ["availability", "in stock", "out of stock", "en stock", "agotado", "disponible", "sin stock", "add to cart", "añadir al carrito"]
    return any(t in b for t in tokens)


def fingerprint_one(entry: dict[str, Any]) -> dict[str, Any]:
    domain = entry["domain"]
    origin = _origin(entry.get("url", ""), domain)
    robots = _get(origin.rstrip("/") + "/robots.txt")
    root = _get(origin.rstrip("/") + "/")
    shopify = _get(origin.rstrip("/") + "/products.json?limit=1")
    woo = _get(origin.rstrip("/") + "/wp-json/wc/store/v1/products?per_page=1")
    platform, platform_source, platform_endpoint = _classify_platform(root, shopify, woo)
    body = root.get("body") or ""
    statuses = {"root": root.get("status"), "robots": robots.get("status"), "shopify": shopify.get("status"), "woocommerce": woo.get("status")}
    root_antibot = _detect_antibot(root.get("status"), root.get("body", ""))
    shopify_antibot = _detect_antibot(shopify.get("status"), shopify.get("body", ""))
    woo_antibot = _detect_antibot(woo.get("status"), woo.get("body", ""))
    antibot_by_source = {"root": root_antibot, "shopify": shopify_antibot, "woocommerce": woo_antibot}
    effective_antibot = _effective_antibot(platform, platform_source, antibot_by_source)
    structured = _has_structured(body) or platform in {"shopify", "woocommerce"}
    visible_stock = _has_stock(body) or platform in {"shopify", "woocommerce"}
    if effective_antibot in ANTIBOT_BLOCKING:
        tier = "red"
    elif platform in {"shopify", "woocommerce"} or structured:
        tier = "green"
    else:
        tier = "yellow"
    return {
        "domain": domain,
        "url": entry.get("url") or origin + "/",
        "platform": platform,
        "tier": tier,
        "has_structured_data": bool(structured),
        "has_visible_stock": bool(visible_stock),
        "robots_crawl_delay": _crawl_delay(robots.get("body") or ""),
        "antibot": effective_antibot,
        "http_status": root.get("status"),
        "evidence": {
            "probe_method": "stdlib_urllib_get_only",
            "statuses": statuses,
            "errors": {"root": root.get("error"), "robots": robots.get("error"), "shopify": shopify.get("error"), "woocommerce": woo.get("error")},
            "platform_source": platform_source,
            "platform_endpoint": platform_endpoint,
            "root_antibot": root_antibot,
            "effective_antibot": effective_antibot,
            "antibot_by_source": antibot_by_source,
        },
        "observed_at": dt.datetime.now(dt.UTC).isoformat(),
    }


def load_targets(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    targets = list(data.get("spain_top10", [])) + list(data.get("europe_top20", []))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in targets:
        domain = item["domain"].strip().lower()
        if domain not in seen:
            seen.add(domain)
            out.append(item)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    targets = load_targets(Path(args.input))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(fingerprint_one, targets))
    rows.sort(key=lambda r: r["domain"])
    for row in rows:
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise SystemExit(f"missing fields for {row.get('domain')}: {sorted(missing)}")
    Path(args.output).write_text(json.dumps({"generated_at": dt.datetime.now(dt.UTC).isoformat(), "count": len(rows), "fingerprints": rows}, indent=2, ensure_ascii=False) + "\n")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["tier"]] = counts.get(row["tier"], 0) + 1
    silver = next((row for row in rows if row["domain"] == "silverback-airsoft.com"), None)
    print("FINGERPRINT_OK", len(rows), counts, "silverback=", silver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
