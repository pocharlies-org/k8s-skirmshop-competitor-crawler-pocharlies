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
    monkeypatch.setattr(scheduler, "write_docs_history", lambda *a, **k: type(
        "R", (), {"enabled": False, "inserted": 0, "skipped": 0}
    )())

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
    monkeypatch.setattr(scheduler, "write_docs_history", lambda *a, **k: type(
        "R", (), {"enabled": False, "inserted": 0, "skipped": 0}
    )())

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
    assert (pushed, failed) == (2, 1)
    assert seen == ["ok1.com", "boom.com", "ok2.com"]


def test_crawl_tier_writes_history_before_push(monkeypatch):
    calls = []
    pushed_docs = []

    async def fake_crawl_store(store):
        return [{"source_id": f"competitor:{store['domain']}:p1"}]

    def fake_history(docs, *, domain, run_id, observed_at):
        calls.append((list(docs), domain, run_id, observed_at))
        return type("R", (), {"enabled": True, "inserted": len(docs), "skipped": 0})()

    async def fake_push_documents(docs):
        pushed_docs.extend(docs)
        return len(list(docs)), 0

    monkeypatch.setattr(scheduler, "history_enabled", lambda: True)
    monkeypatch.setattr(scheduler, "validate_history_config", lambda: None)
    monkeypatch.setattr(scheduler, "crawl_store", fake_crawl_store)
    monkeypatch.setattr(scheduler, "write_docs_history", fake_history)
    monkeypatch.setattr(scheduler, "push_documents", fake_push_documents)

    pushed, failed = asyncio.run(scheduler.crawl_tier("tier1", [{"domain": "a.com"}]))

    assert (pushed, failed) == (1, 0)
    assert calls[0][1] == "a.com"
    assert calls[0][2].startswith("tier1:")
    assert pushed_docs == [{"source_id": "competitor:a.com:p1"}]


def test_crawl_tier_history_failure_counts_failed_and_skips_push(monkeypatch):
    pushed_docs = []

    async def fake_crawl_store(store):
        return [{"source_id": f"competitor:{store['domain']}:p1"}]

    def boom(*args, **kwargs):
        raise RuntimeError("db unavailable")

    async def fake_push_documents(docs):
        pushed_docs.extend(docs)
        return len(list(docs)), 0

    monkeypatch.setattr(scheduler, "history_enabled", lambda: True)
    monkeypatch.setattr(scheduler, "validate_history_config", lambda: None)
    monkeypatch.setattr(scheduler, "crawl_store", fake_crawl_store)
    monkeypatch.setattr(scheduler, "write_docs_history", boom)
    monkeypatch.setattr(scheduler, "push_documents", fake_push_documents)

    pushed, failed = asyncio.run(scheduler.crawl_tier("tier1", [{"domain": "a.com"}]))

    assert (pushed, failed) == (0, 1)
    assert pushed_docs == []
