"""Network-free robots.txt and Crawl-delay tests for the crawler."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import crawler


class _RobotsResponse:
    def __init__(self, status_code=200, text="", url="https://example.com/robots.txt"):
        self.status_code = status_code
        self.text = text
        self.url = url


class _RobotsClient:
    def __init__(self, response=None, exc=None):
        self.response = response or _RobotsResponse(status_code=404)
        self.exc = exc
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.exc is not None:
            raise self.exc
        return self.response


class _AsyncClientFactory:
    def __init__(self, client):
        self.client = client

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _noop_sleep(*_args, **_kwargs):
    return None


def test_crawl_store_skips_start_url_disallowed_by_robots(monkeypatch):
    client = _RobotsClient(
        _RobotsResponse(text="User-agent: *\nDisallow: /blocked\n")
    )
    monkeypatch.setattr(crawler.httpx, "AsyncClient", _AsyncClientFactory(client))
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    async def exploding_fetch(*_args, **_kwargs):
        raise AssertionError("fetch_page must not be called for disallowed URL")

    monkeypatch.setattr(crawler, "fetch_page", exploding_fetch)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "example.com",
                "url": "https://example.com/blocked/product",
                "depth": 0,
                "delay_seconds": 0,
            }
        )
    )

    assert docs == []
    assert client.calls == [
        ("https://example.com/robots.txt", {"follow_redirects": True})
    ]


def test_crawl_store_skips_disallowed_links(monkeypatch):
    client = _RobotsClient(
        _RobotsResponse(text="User-agent: *\nDisallow: /product/blocked\n")
    )
    requested = []

    async def fake_fetch_page(_client, url, domain=None):
        requested.append((url, domain))
        if url == "https://example.com/":
            return """
                <html><body>
                  <a href="/product/allowed">allowed</a>
                  <a href="/product/blocked">blocked</a>
                </body></html>
            """
        return "<html><body>price</body></html>"

    monkeypatch.setattr(crawler.httpx, "AsyncClient", _AsyncClientFactory(client))
    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "example.com",
                "url": "https://example.com/",
                "depth": 1,
                "delay_seconds": 0,
            }
        )
    )

    assert docs == []
    assert requested == [
        ("https://example.com/", "example.com"),
        ("https://example.com/product/allowed", "example.com"),
    ]


def test_crawl_store_uses_max_of_configured_delay_and_robots_delay(monkeypatch):
    client = _RobotsClient(
        _RobotsResponse(text="User-agent: *\nCrawl-delay: 2\n")
    )
    slept = []

    async def fake_fetch_page(_client, url, domain=None):
        return "<html><body>price</body></html>"

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(crawler.httpx, "AsyncClient", _AsyncClientFactory(client))
    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", fake_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "example.com",
                "url": "https://example.com/product/one",
                "depth": 0,
                "delay_seconds": 0.5,
            }
        )
    )

    assert docs == []
    assert slept == [2.0]


def test_crawl_store_robots_fetch_failure_fails_open(monkeypatch):
    client = _RobotsClient(exc=RuntimeError("network down"))
    requested = []

    async def fake_fetch_page(_client, url, domain=None):
        requested.append((url, domain))
        return "<html><body>price</body></html>"

    monkeypatch.setattr(crawler.httpx, "AsyncClient", _AsyncClientFactory(client))
    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "example.com",
                "url": "https://example.com/product/one",
                "depth": 0,
                "delay_seconds": 0,
            }
        )
    )

    assert docs == []
    assert requested == [("https://example.com/product/one", "example.com")]
