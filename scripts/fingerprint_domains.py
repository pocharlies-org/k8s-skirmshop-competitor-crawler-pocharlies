#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
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
    for line in robots_body.splitlines():
        if line.lower().strip().startswith("crawl-delay"):
            _, _, value = line.partition(":")
            try:
                return float(value.strip())
            except ValueError:
                return None
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


def _detect_platform(root: dict[str, Any], shopify: dict[str, Any], woo: dict[str, Any]) -> str:
    sj = _json_ok(shopify.get("body", ""))
    if shopify.get("status") == 200 and isinstance(sj, dict) and "products" in sj:
        return "shopify"
    wj = _json_ok(woo.get("body", ""))
    if woo.get("status") == 200 and isinstance(wj, list):
        return "woocommerce"
    b = (root.get("body") or "").lower()
    if "cdn.shopify.com" in b or "shopify.theme" in b or "myshopify" in b:
        return "shopify"
    if "woocommerce" in b or "wp-content/plugins/woocommerce" in b:
        return "woocommerce"
    if root.get("status") == 200:
        return "generic_html"
    return "unknown"


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
    platform = _detect_platform(root, shopify, woo)
    body = root.get("body") or ""
    statuses = {"root": root.get("status"), "robots": robots.get("status"), "shopify": shopify.get("status"), "woocommerce": woo.get("status")}
    antibots = [_detect_antibot(item.get("status"), item.get("body", "")) for item in (root, shopify, woo)]
    antibot = next((x for x in antibots if x in {"captcha", "cloudflare", "http_429", "http_403"}), "none" if root.get("status") else "unknown")
    structured = _has_structured(body) or platform in {"shopify", "woocommerce"}
    visible_stock = _has_stock(body) or platform in {"shopify", "woocommerce"}
    if antibot in {"captcha", "cloudflare", "http_429", "http_403"}:
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
        "antibot": antibot,
        "http_status": root.get("status"),
        "evidence": {"probe_method": "stdlib_urllib_get_only", "statuses": statuses, "errors": {"root": root.get("error"), "robots": robots.get("error"), "shopify": shopify.get("error"), "woocommerce": woo.get("error")}},
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
