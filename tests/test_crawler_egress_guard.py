"""Network-free tests for the crawler egress domain guard."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import crawler, fetcher
from src.egress_guard import is_allowed_url
from src.fetcher import FetchBlockedError


def test_is_allowed_url_accepts_exact_domain_and_subdomain():
    assert is_allowed_url("https://gunfire.com/product/a", "gunfire.com")
    assert is_allowed_url("https://www.gunfire.com/product/a", "gunfire.com")
    assert is_allowed_url("http://shop.gunfire.com:8080/p/a", "gunfire.com")
    assert is_allowed_url("https://GUNFIRE.com./p/a", " gunfire.com. ")


def test_is_allowed_url_rejects_suffix_prefix_userinfo_and_non_http():
    blocked = [
        "https://evilgunfire.com/product/a",
        "https://gunfire.com.evil.com/product/a",
        "https://not-gunfire.com/product/a",
        "https://gunfire.com@evil.com/product/a",
        "javascript:alert(1)",
        "mailto:sales@gunfire.com",
        "ftp://gunfire.com/product/a",
        "//evil.com/product/a",
        "/relative/product/a",
        "",
    ]
    for url in blocked:
        assert not is_allowed_url(url, "gunfire.com"), url


class _ExplodingClient:
    async def get(self, url, **kwargs):
        raise AssertionError(f"client.get must not be called for {url}")


class _ExplodingAsyncClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("Firecrawl fallback must not be constructed")


def test_fetch_page_blocks_forbidden_url_before_direct_or_firecrawl(monkeypatch):
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", _ExplodingAsyncClient)

    html = asyncio.run(
        fetcher.fetch_page(
            _ExplodingClient(),
            "https://gunfire.com@evil.com/product/a",
            "gunfire.com",
        )
    )

    assert html is None


class _RedirectResponse:
    status_code = 200
    url = "https://evil.com/product/a"
    text = "<html>" + ("price " * 1000) + "</html>"

    def json(self):
        raise AssertionError("not a Firecrawl response")


class _RedirectClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _RedirectResponse()


def test_fetch_page_discards_off_domain_redirect_without_firecrawl(monkeypatch):
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", _ExplodingAsyncClient)
    client = _RedirectClient()

    html = asyncio.run(
        fetcher.fetch_page(client, "https://gunfire.com/product/a", "gunfire.com")
    )

    assert html is None
    assert client.calls == [
        ("https://gunfire.com/product/a", {"follow_redirects": True})
    ]


class _BlockedResponse:
    status_code = 503
    url = "https://www.taiwangun.com/captcha.php?from=%2Fen"
    text = "<html>captcha required</html>"


class _BlockedClient:
    async def get(self, url, **kwargs):
        return _BlockedResponse()


def test_fetch_page_blocks_challenge_before_firecrawl(monkeypatch):
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", _ExplodingAsyncClient)

    try:
        asyncio.run(
            fetcher.fetch_page(
                _BlockedClient(),
                "https://www.taiwangun.com/en",
                "taiwangun.com",
            )
        )
    except FetchBlockedError as exc:
        assert exc.reason == "challenge_path"
        assert "captcha.php" in exc.url
    else:  # pragma: no cover - defensive
        raise AssertionError("expected FetchBlockedError")


class _CloudflareMentionResponse:
    status_code = 200
    url = "https://gunfire.com/"
    text = "<html>" + ("cloudflare price " * 400) + "</html>"


class _CloudflareMentionClient:
    async def get(self, url, **kwargs):
        return _CloudflareMentionResponse()


def test_fetch_page_allows_plain_cloudflare_mention_without_challenge(monkeypatch):
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", _ExplodingAsyncClient)

    html = asyncio.run(
        fetcher.fetch_page(_CloudflareMentionClient(), "https://gunfire.com/", "gunfire.com")
    )

    assert html == _CloudflareMentionResponse.text


class _NoNetworkAsyncClient:
    """Context manager accepted by crawl_store; get must never be called."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return _ExplodingClient()

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _noop_sleep(*_args, **_kwargs):
    return None


class _AllowAllRobots:
    crawl_delay_seconds = None

    def can_fetch(self, _url):
        return True


async def _allow_all_robots(*_args, **_kwargs):
    return _AllowAllRobots()


def test_crawl_store_off_domain_start_url_does_not_fetch(monkeypatch):
    monkeypatch.setattr(crawler.httpx, "AsyncClient", _NoNetworkAsyncClient)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "gunfire.com",
                "url": "https://gunfire.com@evil.com/product/a",
                "depth": 1,
            }
        )
    )

    assert docs == []


def test_crawl_store_bfs_rejects_evil_suffix_and_userinfo(monkeypatch):
    requested = []

    async def fake_fetch_page(_client, url, domain=None):
        requested.append((url, domain))
        if url == "https://gunfire.com/":
            return """
                <html><body>
                  <a href="https://www.gunfire.com/product/allowed">ok</a>
                  <a href="https://evilgunfire.com/product/blocked">bad</a>
                  <a href="https://gunfire.com@evil.com/product/blocked">bad</a>
                  <a href="https://gunfire.com.evil.com/product/blocked">bad</a>
                </body></html>
            """
        return ""

    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {"domain": "gunfire.com", "url": "https://gunfire.com/", "depth": 1}
        )
    )

    assert docs == []
    assert requested == [
        ("https://gunfire.com/", "gunfire.com"),
        ("https://www.gunfire.com/product/allowed", "gunfire.com"),
    ]


def test_crawl_store_prioritizes_detail_links_over_shallow_categories(monkeypatch):
    requested = []
    detail_url = (
        "https://fullmetal.es/armas-de-airsoft/armas-electricas/"
        "fusiles-de-asalto-aeg/ec-mcx-aeg"
    )

    async def fake_fetch_page(_client, url, domain=None):
        requested.append((url, domain))
        if url == "https://fullmetal.es/":
            return """
                <html><body>
                  <a href="/armas-de-airsoft">root category</a>
                  <a href="/armas-electricas">second category</a>
                </body></html>
            """
        if url == "https://fullmetal.es/armas-de-airsoft":
            return f"""
                <html><body>
                  <a href="{detail_url}">EC MCX AEG</a>
                </body></html>
            """
        if url == detail_url:
            return """<html><body>
              <script type="application/ld+json">{
                "@type": "Product",
                "name": "EC MCX AEG",
                "offers": {"price": "359.00"}
              }</script>
            </body></html>"""
        return "<html><body>category</body></html>"

    monkeypatch.setattr(crawler, "load_robots_policy", _allow_all_robots)
    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "fullmetal.es",
                "url": "https://fullmetal.es/",
                "depth": 2,
                "max_pages": 3,
                "delay_seconds": 0,
            }
        )
    )

    assert [call[0] for call in requested] == [
        "https://fullmetal.es/",
        "https://fullmetal.es/armas-de-airsoft",
        detail_url,
    ]
    assert len(docs) == 1
    assert docs[0]["metadata"]["title"] == "EC MCX AEG"
    assert docs[0]["metadata"]["price"] == 359.0


def test_crawl_store_bfs_skips_cart_compare_return_and_search_paths(monkeypatch):
    requested = []

    async def fake_fetch_page(_client, url, domain=None):
        requested.append((url, domain))
        if url == "https://gunfire.com/":
            return """
                <html><body>
                  <a href="/product/allowed">ok</a>
                  <a href="/basketedit.php">basket</a>
                  <a href="/en/product-compare.html">compare</a>
                  <a href="/en/return.html">return</a>
                  <a href="/en/searching.html">search</a>
                  <a href="/captcha.php">captcha</a>
                </body></html>
            """
        return ""

    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {"domain": "gunfire.com", "url": "https://gunfire.com/", "depth": 1}
        )
    )

    assert docs == []
    assert requested == [
        ("https://gunfire.com/", "gunfire.com"),
        ("https://gunfire.com/product/allowed", "gunfire.com"),
    ]


def test_crawl_store_raises_on_blocked_fetch(monkeypatch):
    async def fake_fetch_page(_client, url, domain=None):
        raise FetchBlockedError(url, "http_429")

    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    try:
        asyncio.run(
            crawler.crawl_store(
                {
                    "domain": "gunfire.com",
                    "url": "https://gunfire.com/",
                    "depth": 0,
                }
            )
        )
    except FetchBlockedError as exc:
        assert exc.reason == "http_429"
    else:  # pragma: no cover - defensive
        raise AssertionError("expected FetchBlockedError")


def test_crawl_store_respects_max_pages_hard_limit(monkeypatch):
    requested = []

    async def fake_fetch_page(_client, url, domain=None):
        requested.append((url, domain))
        if url == "https://gunfire.com/":
            return """
                <html><body>
                  <a href="/product/one">one</a>
                  <a href="/product/two">two</a>
                  <a href="/product/three">three</a>
                </body></html>
            """
        return "<html><body>price</body></html>"

    monkeypatch.setattr(crawler, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(crawler.asyncio, "sleep", _noop_sleep)

    docs = asyncio.run(
        crawler.crawl_store(
            {
                "domain": "gunfire.com",
                "url": "https://gunfire.com/",
                "depth": 2,
                "max_pages": 2,
                "delay_seconds": 0,
            }
        )
    )

    assert docs == []
    assert requested == [
        ("https://gunfire.com/", "gunfire.com"),
        ("https://gunfire.com/product/one", "gunfire.com"),
    ]


def test_crawl_store_rejects_invalid_limits_before_fetch(monkeypatch):
    monkeypatch.setattr(crawler.httpx, "AsyncClient", _NoNetworkAsyncClient)

    for key, value in (("max_pages", 0), ("max_pages", "nope"), ("delay_seconds", -1)):
        store = {
            "domain": "gunfire.com",
            "url": "https://gunfire.com/",
            "depth": 1,
            key: value,
        }
        try:
            asyncio.run(crawler.crawl_store(store))
        except ValueError as exc:
            assert key in str(exc)
        else:
            raise AssertionError(f"{key}={value!r} should fail closed")
