"""dry_run.py - CLI smoke-test for a single competitor domain.

Usage:
    python -m src.dry_run --domain leopard.es --limit 50 --output out.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

FINGERPRINT_PATH = Path(__file__).resolve().parent.parent / "data/competitors/fingerprint.json"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_fingerprint(domain: str) -> dict:
    data = json.loads(FINGERPRINT_PATH.read_text())
    fps = data.get("fingerprints", [])
    for entry in fps:
        if entry.get("domain") == domain:
            return entry
    raise SystemExit(f"Domain '{domain}' not found in fingerprint.json. "
                     f"Available: {[e['domain'] for e in fps]}")


def _pick_adapter_class(platform: str):
    from src.adapters.generic_html import GenericHtmlAdapter
    # Extend this map as new adapters are added.
    _MAP = {
        "generic_html": GenericHtmlAdapter,
    }
    cls = _MAP.get(platform)
    if cls is None:
        logger.warning("Unknown platform '%s', falling back to generic_html.", platform)
        return GenericHtmlAdapter
    return cls


async def _run(domain: str, limit: int, output: Path) -> None:
    fp = _load_fingerprint(domain)
    source_url: str = fp["url"]
    platform: str = fp.get("platform", "generic_html")

    AdapterClass = _pick_adapter_class(platform)
    adapter = AdapterClass(domain=domain, source_url=source_url)
    logger.info("Running %s adapter for %s -> %s (limit=%d)",
                AdapterClass.name, domain, source_url, limit)
    try:
        result = await adapter.run(limit=limit)
    finally:
        if hasattr(adapter, "close"):
            await adapter.close()

    payload = {
        "domain": result.domain,
        "source_url": result.source_url,
        "adapter": result.adapter,
        "limit": limit,
        "counts": {
            "candidates": result.candidates,
            "success": result.success,
            "discarded": result.discarded,
            "failures": result.failures,
            "discard_ratio": result.discard_ratio,
        },
        "products": result.products,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.info("Wrote %d products to %s", result.success, output)
    logger.info("Counts: %s", payload["counts"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run competitor scrape.")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(_run(args.domain, args.limit, args.output))


if __name__ == "__main__":
    main()
