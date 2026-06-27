"""APScheduler-driven tier crawls."""
import asyncio
import logging
from pathlib import Path

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.crawler import crawl_store
from src.push_client import push_documents

logger = logging.getLogger(__name__)


def load_config(path: Path = Path("/app/config.yaml")) -> dict:
    return yaml.safe_load(path.read_text()) or {}


async def crawl_tier(tier_name: str, stores: list[dict]) -> tuple[int, int]:
    """Run every store in a tier sequentially, push results in batches.

    Returns ``(total_pushed, total_failed)`` aggregated across stores. A failure
    crawling/pushing one store is logged and skipped, never aborting the tier,
    so a single bad store cannot starve the rest of the window. The return value
    lets a one-shot runner (``src.run_once``) derive a process exit status;
    APScheduler (``build_scheduler``) ignores it.
    """
    logger.info(f"[{tier_name}] start ({len(stores)} stores)")
    total_pushed = 0
    total_failed = 0
    for store in stores:
        try:
            docs = await crawl_store(store)
            sent, failed = await push_documents(docs)
            total_pushed += sent
            total_failed += failed
        except Exception as e:
            logger.exception(f"[{tier_name}] {store.get('domain')} failed: {e}")
    logger.info(
        f"[{tier_name}] done — pushed={total_pushed} failed={total_failed}"
    )
    return total_pushed, total_failed


def build_scheduler(config: dict) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    tiers = config.get("tiers", {})
    for tier_name, tier in tiers.items():
        sched = tier.get("schedule")
        stores = tier.get("stores", [])
        if not sched or not stores:
            continue
        try:
            trigger = CronTrigger.from_crontab(sched, timezone="UTC")
            scheduler.add_job(
                crawl_tier,
                trigger=trigger,
                args=[tier_name, stores],
                id=f"crawl_{tier_name}",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=3600,
            )
            logger.info(f"scheduled {tier_name} ({len(stores)} stores) @ {sched}")
        except Exception as e:
            logger.error(f"invalid cron for {tier_name}: {e}")
    return scheduler
