"""Unit tests for src.scheduler.crawl_tier — no real network.

crawl_store/push_documents are monkeypatched so the tier loop runs purely in
memory. Locks the F7 contract that crawl_tier returns aggregated
``(total_pushed, total_failed)`` and never aborts the tier on a single store
failure.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import scheduler


def test_crawl_tier_returns_aggregated_totals(monkeypatch):
    crawled = []

    async def fake_crawl_store(store):
        crawled.append(store["domain"])
        # one doc per store, value irrelevant to the aggregation
        return [{"id": store["domain"]}]

    async def fake_push_documents(docs):
        # pretend every doc was pushed successfully
        return len(list(docs)), 0

    monkeypatch.setattr(scheduler, "crawl_store", fake_crawl_store)
    monkeypatch.setattr(scheduler, "push_documents", fake_push_documents)

    stores = [{"domain": "a.com"}, {"domain": "b.com"}, {"domain": "c.com"}]
    pushed, failed = asyncio.run(scheduler.crawl_tier("tier1", stores))

    assert (pushed, failed) == (3, 0)
    assert crawled == ["a.com", "b.com", "c.com"]  # sequential, in order


def test_crawl_tier_aggregates_push_failures(monkeypatch):
    async def fake_crawl_store(store):
        return [{"id": store["domain"]}]

    async def fake_push_documents(docs):
        # half the batch fails to push
        return 0, len(list(docs))

    monkeypatch.setattr(scheduler, "crawl_store", fake_crawl_store)
    monkeypatch.setattr(scheduler, "push_documents", fake_push_documents)

    pushed, failed = asyncio.run(
        scheduler.crawl_tier("tier1", [{"domain": "a.com"}, {"domain": "b.com"}])
    )

    assert (pushed, failed) == (0, 2)


def test_crawl_tier_skips_failing_store_without_aborting(monkeypatch):
    seen = []

    async def fake_crawl_store(store):
        seen.append(store["domain"])
        if store["domain"] == "boom.com":
            raise RuntimeError("crawl exploded")
        return [{"id": store["domain"]}]

    async def fake_push_documents(docs):
        return len(list(docs)), 0

    monkeypatch.setattr(scheduler, "crawl_store", fake_crawl_store)
    monkeypatch.setattr(scheduler, "push_documents", fake_push_documents)

    stores = [{"domain": "ok1.com"}, {"domain": "boom.com"}, {"domain": "ok2.com"}]
    pushed, failed = asyncio.run(scheduler.crawl_tier("tier1", stores))

    # the failing store is skipped; the other two still pushed
    assert (pushed, failed) == (2, 0)
    assert seen == ["ok1.com", "boom.com", "ok2.com"]
