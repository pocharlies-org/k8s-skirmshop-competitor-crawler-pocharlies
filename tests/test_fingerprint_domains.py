"""F4c tests: endpoint-scoped antibot policy for scripts/fingerprint_domains.py.

All network is mocked via monkeypatch of ``fingerprint_domains._get`` so these
tests are fully offline and never perform a real probe. They assert the
endpoint-scoped antibot policy: a clean Shopify/Woo data endpoint scopes antibot
away from a captcha'd root (relief), while a blocked data endpoint is never
ignored (fail-closed => red).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fingerprint_domains as fp  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SHOPIFY_CLEAN_BODY = json.dumps({"products": [{"id": 1, "title": "Rifle Replica"}]})
WOO_CLEAN_BODY = json.dumps([{"id": 1, "name": "Pistol Replica", "is_in_stock": True}])
SHOPIFY_HTML_CLEAN = "<html><head><link href='https://cdn.shopify.com/x.css'></head><body>ok</body></html>"
WOO_HTML_CLEAN = "<html><body class='woocommerce'>wp-content/plugins/woocommerce</body></html>"
CHALLENGE_BODY = "<html><title>Just a moment...</title><body>checking your browser cloudflare cf-chl</body></html>"
ROBOTS_OK = {"status": 200, "body": "User-agent: *\nDisallow:\n"}


def _resp(status, body="", error=None):
    return {"status": status, "body": body, "error": error}


def make_get(responses):
    """Build a fake ``_get`` routing by URL suffix to a responses mapping.

    responses keys: ``robots``, ``root``, ``shopify``, ``woo``. Missing keys
    default to a hard error response (status None).
    """

    def _fake_get(url):
        if url.endswith("/robots.txt"):
            key = "robots"
        elif "/products.json" in url:
            key = "shopify"
        elif "/wp-json/wc/store" in url:
            key = "woo"
        else:
            key = "root"
        spec = responses.get(key, {"status": None, "body": "", "error": "not-configured"})
        return {
            "url": url,
            "status": spec.get("status"),
            "body": spec.get("body", ""),
            "error": spec.get("error"),
        }

    return _fake_get


def run_one(monkeypatch, responses, domain="example.com"):
    monkeypatch.setattr(fp, "_get", make_get(responses))
    return fp.fingerprint_one({"domain": domain, "url": f"https://{domain}/"})


# ---------------------------------------------------------------------------
# Endpoint relief: clean data endpoint overrides root captcha => green
# ---------------------------------------------------------------------------

def test_shopify_endpoint_clean_with_root_captcha_is_green(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>please solve the captcha to continue</html>"),
            "shopify": _resp(200, SHOPIFY_CLEAN_BODY),
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "shopify"
    assert res["evidence"]["platform_source"] == "endpoint"
    assert res["evidence"]["platform_endpoint"] == "shopify"
    assert res["evidence"]["root_antibot"] == "captcha"
    assert res["evidence"]["effective_antibot"] == "none"
    assert res["evidence"]["antibot_by_source"]["root"] == "captcha"
    assert res["evidence"]["antibot_by_source"]["shopify"] == "none"
    assert res["antibot"] == "none"
    assert res["tier"] == "green"


def test_woo_endpoint_clean_with_root_captcha_is_green(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>g-recaptcha verify you are human</html>"),
            "shopify": _resp(404, "not found"),
            "woo": _resp(200, WOO_CLEAN_BODY),
        },
    )
    assert res["platform"] == "woocommerce"
    assert res["evidence"]["platform_source"] == "endpoint"
    assert res["evidence"]["platform_endpoint"] == "woocommerce"
    assert res["evidence"]["root_antibot"] == "captcha"
    assert res["evidence"]["effective_antibot"] == "none"
    assert res["antibot"] == "none"
    assert res["tier"] == "green"


# ---------------------------------------------------------------------------
# Fail-closed: blocked data endpoint => red (never ignored)
# ---------------------------------------------------------------------------

def test_shopify_endpoint_403_is_red(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, SHOPIFY_HTML_CLEAN),  # clean root, shopify inferred from HTML
            "shopify": _resp(403, "forbidden"),
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "shopify"
    assert res["evidence"]["platform_source"] == "html"
    assert res["evidence"]["root_antibot"] == "none"
    assert res["evidence"]["antibot_by_source"]["shopify"] == "http_403"
    assert res["evidence"]["effective_antibot"] == "http_403"
    assert res["antibot"] == "http_403"
    assert res["tier"] == "red"


def test_woo_endpoint_403_is_red(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, WOO_HTML_CLEAN),  # clean root, woo inferred from HTML
            "shopify": _resp(404, "not found"),
            "woo": _resp(403, "forbidden"),
        },
    )
    assert res["platform"] == "woocommerce"
    assert res["evidence"]["platform_source"] == "html"
    assert res["evidence"]["effective_antibot"] == "http_403"
    assert res["antibot"] == "http_403"
    assert res["tier"] == "red"


@pytest.mark.parametrize(
    "platform_html, ep_key, ep_marker",
    [
        (SHOPIFY_HTML_CLEAN, "shopify", "shopify"),
        (WOO_HTML_CLEAN, "woo", "woocommerce"),
    ],
)
def test_endpoint_429_is_red(monkeypatch, platform_html, ep_key, ep_marker):
    responses = {
        "robots": ROBOTS_OK,
        "root": _resp(200, platform_html),
        "shopify": _resp(404, "not found"),
        "woo": _resp(404, "not found"),
    }
    responses[ep_key] = _resp(429, "too many requests")
    res = run_one(monkeypatch, responses)
    assert res["platform"] == ep_marker
    assert res["evidence"]["effective_antibot"] == "http_429"
    assert res["antibot"] == "http_429"
    assert res["tier"] == "red"


def test_endpoint_200_challenge_body_gives_no_relief_and_is_red(monkeypatch):
    # Shopify endpoint returns HTTP 200 but with a Cloudflare challenge body
    # (wrong shape, antibot markers). It must not be treated as a clean endpoint.
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, SHOPIFY_HTML_CLEAN),
            "shopify": _resp(200, CHALLENGE_BODY),
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "shopify"
    assert res["evidence"]["platform_source"] == "html"  # not "endpoint": no relief
    assert res["evidence"]["antibot_by_source"]["shopify"] == "cloudflare"
    assert res["evidence"]["effective_antibot"] == "cloudflare"
    assert res["antibot"] == "cloudflare"
    assert res["tier"] == "red"


def test_endpoint_200_wrong_shape_gives_no_relief_root_captcha_is_red(monkeypatch):
    # Shopify endpoint returns valid JSON of the WRONG shape (no markers). It must
    # not grant relief; with a captcha'd root, root governs => red.
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>captcha required cdn.shopify.com</html>"),
            "shopify": _resp(200, json.dumps({"errors": "nope"})),  # wrong shape
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "shopify"
    assert res["evidence"]["platform_source"] == "html"  # endpoint not clean
    assert res["evidence"]["antibot_by_source"]["shopify"] == "none"
    assert res["evidence"]["root_antibot"] == "captcha"
    assert res["evidence"]["effective_antibot"] == "captcha"
    assert res["antibot"] == "captcha"
    assert res["tier"] == "red"


# ---------------------------------------------------------------------------
# Generic / structured root behaviour
# ---------------------------------------------------------------------------

def test_generic_root_captcha_is_red(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>please complete the captcha</html>"),
            "shopify": _resp(404, "not found"),
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "generic_html"
    assert res["evidence"]["platform_source"] == "none"
    assert res["evidence"]["platform_endpoint"] is None
    assert res["evidence"]["root_antibot"] == "captcha"
    assert res["evidence"]["effective_antibot"] == "captcha"
    assert res["antibot"] == "captcha"
    assert res["tier"] == "red"


def test_structured_clean_generic_is_green(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(
                200,
                '<html><script type="application/ld+json">{"@type":"Product"}</script></html>',
            ),
            "shopify": _resp(404, "not found"),
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "generic_html"
    assert res["has_structured_data"] is True
    assert res["evidence"]["effective_antibot"] == "none"
    assert res["antibot"] == "none"
    assert res["tier"] == "green"


def test_generic_with_blocked_irrelevant_endpoint_is_not_red(monkeypatch):
    # Regression for the F4c bug: a clean generic_html root must NOT be marked red
    # just because an unrelated /products.json probe returns 403.
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(
                200,
                '<html><script type="application/ld+json">{"@type":"Product"}</script></html>',
            ),
            "shopify": _resp(403, "forbidden"),
            "woo": _resp(404, "not found"),
        },
    )
    assert res["platform"] == "generic_html"
    assert res["evidence"]["antibot_by_source"]["shopify"] == "http_403"
    assert res["evidence"]["effective_antibot"] == "none"  # endpoint scoped away
    assert res["antibot"] == "none"
    assert res["tier"] == "green"


# ---------------------------------------------------------------------------
# Schema / contract guarantees
# ---------------------------------------------------------------------------

def test_evidence_schema_is_additive(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>captcha</html>"),
            "shopify": _resp(200, SHOPIFY_CLEAN_BODY),
            "woo": _resp(404, "not found"),
        },
    )
    # Original required top-level fields preserved.
    assert fp.REQUIRED_FIELDS <= set(res)
    ev = res["evidence"]
    # Original evidence keys preserved.
    for key in ("probe_method", "statuses", "errors"):
        assert key in ev
    assert set(ev["statuses"]) == {"root", "robots", "shopify", "woocommerce"}
    assert set(ev["errors"]) == {"root", "robots", "shopify", "woocommerce"}
    # New additive keys present.
    for key in (
        "platform_source",
        "platform_endpoint",
        "root_antibot",
        "effective_antibot",
        "antibot_by_source",
    ):
        assert key in ev
    assert set(ev["antibot_by_source"]) == {"root", "shopify", "woocommerce"}


@pytest.mark.parametrize(
    "responses",
    [
        {  # endpoint relief
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>captcha</html>"),
            "shopify": _resp(200, SHOPIFY_CLEAN_BODY),
            "woo": _resp(404, "x"),
        },
        {  # endpoint blocked
            "robots": ROBOTS_OK,
            "root": _resp(200, WOO_HTML_CLEAN),
            "shopify": _resp(404, "x"),
            "woo": _resp(403, "x"),
        },
        {  # generic captcha
            "robots": ROBOTS_OK,
            "root": _resp(200, "<html>captcha</html>"),
            "shopify": _resp(404, "x"),
            "woo": _resp(404, "x"),
        },
        {  # total failure (DNS error)
            "robots": _resp(None, "", "URLError:boom"),
            "root": _resp(None, "", "URLError:boom"),
            "shopify": _resp(None, "", "URLError:boom"),
            "woo": _resp(None, "", "URLError:boom"),
        },
    ],
)
def test_top_level_antibot_equals_effective(monkeypatch, responses):
    res = run_one(monkeypatch, responses)
    assert res["antibot"] == res["evidence"]["effective_antibot"]


def test_unreachable_domain_is_unknown_yellow_backward_compatible(monkeypatch):
    res = run_one(
        monkeypatch,
        {
            "robots": _resp(None, "", "URLError:boom"),
            "root": _resp(None, "", "URLError:boom"),
            "shopify": _resp(None, "", "URLError:boom"),
            "woo": _resp(None, "", "URLError:boom"),
        },
    )
    assert res["platform"] == "unknown"
    assert res["http_status"] is None
    assert res["antibot"] == "unknown"
    assert res["tier"] == "yellow"


def test_output_schema_backward_compatible_with_committed_fingerprint(monkeypatch):
    committed = json.loads((REPO_ROOT / "data/competitors/fingerprint.json").read_text())
    sample = committed["fingerprints"][0]
    res = run_one(
        monkeypatch,
        {
            "robots": ROBOTS_OK,
            "root": _resp(200, SHOPIFY_HTML_CLEAN),
            "shopify": _resp(200, SHOPIFY_CLEAN_BODY),
            "woo": _resp(404, "x"),
        },
    )
    # Every key the committed artifact exposed at the top level must still exist.
    assert set(sample) <= set(res)
    # Original evidence keys remain available for downstream consumers.
    for key in ("probe_method", "statuses", "errors"):
        assert key in res["evidence"]


# ---------------------------------------------------------------------------
# GET-only static guard
# ---------------------------------------------------------------------------

def test_get_only_static_guard():
    src = (REPO_ROOT / "scripts/fingerprint_domains.py").read_text()
    # Exactly one request builder, GET only.
    assert 'method="GET"' in src
    assert "POST" not in src
    assert src.count("urllib.request.Request(") == 1
    assert src.count("urllib.request.urlopen(") == 1
    # No high-level HTTP clients that could carry a body.
    for forbidden in ("import requests", "import httpx", "import aiohttp", "requests.", "httpx.", "aiohttp."):
        assert forbidden not in src
    # No request body is ever attached.
    assert "data=" not in src
    # No cart/checkout/login/account write endpoints are ever requested.
    for forbidden_path in ("/cart/add", "/cart/clear", "cart.js", "/checkout", "/login", "/wp-login", "/account"):
        assert forbidden_path not in src


def test_get_helper_uses_get_method(monkeypatch):
    captured = {}

    class _FakeReq:
        def __init__(self, url, headers=None, method=None):
            captured["url"] = url
            captured["method"] = method
            captured["headers"] = headers
            captured["has_data"] = False

    class _FakeResp:
        status = 200

        def read(self, n):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(fp.urllib.request, "Request", _FakeReq)
    monkeypatch.setattr(fp.urllib.request, "urlopen", lambda req, timeout=None, context=None: _FakeResp())

    out = fp._get("https://example.com/robots.txt")
    assert captured["method"] == "GET"
    assert captured["has_data"] is False
    assert out["status"] == 200


# ---------------------------------------------------------------------------
# Crawl-delay parsing: must resolve to the wildcard ``User-agent: *`` group and
# never adopt a delay scoped to a named bot (Ahrefs/MJ12/Pinterest/...).
# All cases are pure-string and fully offline (no network, no monkeypatch).
# ---------------------------------------------------------------------------

def test_crawl_delay_star_group_is_used():
    body = "User-agent: *\nDisallow:\nCrawl-delay: 5\n"
    assert fp._crawl_delay(body) == 5.0


def test_crawl_delay_named_bot_only_is_ignored():
    # A delay scoped solely to a named crawler must not leak into the result.
    body = "User-agent: AhrefsBot\nCrawl-delay: 10\n"
    assert fp._crawl_delay(body) is None


def test_crawl_delay_multiple_named_bots_then_star():
    # Named bots (each its own group) declare delays; only the wildcard wins.
    body = (
        "User-agent: AhrefsBot\n"
        "Crawl-delay: 10\n"
        "\n"
        "User-agent: MJ12bot\n"
        "Crawl-delay: 20\n"
        "\n"
        "User-agent: PinterestBot\n"
        "Crawl-delay: 30\n"
        "\n"
        "User-agent: *\n"
        "Disallow: /private\n"
        "Crawl-delay: 3\n"
    )
    assert fp._crawl_delay(body) == 3.0


def test_crawl_delay_no_star_delay_returns_none():
    # Wildcard group exists but declares no Crawl-delay -> None (do not borrow
    # the named bot's delay that appears earlier in the file).
    body = (
        "User-agent: AhrefsBot\n"
        "Crawl-delay: 10\n"
        "\n"
        "User-agent: *\n"
        "Disallow: /private\n"
    )
    assert fp._crawl_delay(body) is None


def test_crawl_delay_malformed_value_is_ignored():
    body = "User-agent: *\nCrawl-delay: soon\n"
    assert fp._crawl_delay(body) is None


def test_crawl_delay_shared_group_with_star_applies():
    # A single group naming several agents, the wildcard among them: the delay
    # that follows the run of User-agent lines applies to all of them.
    body = (
        "User-agent: Googlebot\n"
        "User-agent: *\n"
        "Crawl-delay: 7\n"
    )
    assert fp._crawl_delay(body) == 7.0


def test_crawl_delay_star_survives_surrounding_named_delays():
    # Named-bot delays before and after the wildcard group are both ignored.
    body = (
        "User-agent: SemrushBot\n"
        "Crawl-delay: 99\n"
        "\n"
        "User-agent: *\n"
        "Crawl-delay: 2\n"
        "\n"
        "User-agent: MJ12bot\n"
        "Crawl-delay: 50\n"
    )
    assert fp._crawl_delay(body) == 2.0


def test_crawl_delay_malformed_star_does_not_borrow_named_delay():
    # A malformed wildcard delay must not fall through to a later named delay.
    body = (
        "User-agent: *\n"
        "Crawl-delay: later\n"
        "\n"
        "User-agent: AhrefsBot\n"
        "Crawl-delay: 10\n"
    )
    assert fp._crawl_delay(body) is None


def test_crawl_delay_absent_returns_none():
    # The ROBOTS_OK fixture used across the suite has no Crawl-delay.
    assert fp._crawl_delay(ROBOTS_OK["body"]) is None
    assert fp._crawl_delay("") is None


# ---------------------------------------------------------------------------
# Numeric validity guard (rho-backend follow-up requested by Codex/verifier:
# close the residual risk for invalid wildcard delays). A wildcard delay that
# is negative or non-finite (inf/-inf/nan) fails the `isfinite(...) and >= 0`
# guard, is rejected, and MUST NOT fall through to a delay scoped to a named
# bot. All cases are pure-string and fully offline (no network, no monkeypatch).
# ---------------------------------------------------------------------------


def test_crawl_delay_negative_star_returns_none():
    # A negative wildcard delay is invalid (>= 0 guard) and yields None.
    body = "User-agent: *\nCrawl-delay: -5\n"
    assert fp._crawl_delay(body) is None


def test_crawl_delay_negative_star_does_not_borrow_named_delay():
    # The rejected negative wildcard delay must not fall through to a later
    # named-bot delay declared further down the file.
    body = (
        "User-agent: *\n"
        "Crawl-delay: -5\n"
        "\n"
        "User-agent: AhrefsBot\n"
        "Crawl-delay: 10\n"
    )
    assert fp._crawl_delay(body) is None


@pytest.mark.parametrize("token", ["inf", "-inf", "nan", "infinity", "-infinity"])
def test_crawl_delay_non_finite_star_returns_none(token):
    # inf/-inf/nan parse as a float but fail the math.isfinite guard -> None.
    body = f"User-agent: *\nCrawl-delay: {token}\n"
    assert fp._crawl_delay(body) is None


@pytest.mark.parametrize("token", ["inf", "-inf", "nan", "infinity"])
def test_crawl_delay_non_finite_star_does_not_borrow_named_delay(token):
    # A non-finite wildcard delay must not fall through to a later named-bot
    # delay; the named group resets the agent set so `*` is no longer in scope.
    body = (
        "User-agent: *\n"
        f"Crawl-delay: {token}\n"
        "\n"
        "User-agent: MJ12bot\n"
        "Crawl-delay: 20\n"
    )
    assert fp._crawl_delay(body) is None


def test_crawl_delay_valid_star_after_invalid_in_same_group_is_accepted():
    # Documents the EXISTING behavior (no code change): once the wildcard group
    # is in scope, an invalid delay line (negative/non-finite) is skipped but a
    # later VALID Crawl-delay in the same group (no intervening User-agent) is
    # still honored, because current_agents keeps `*` in scope.
    body = (
        "User-agent: *\n"
        "Crawl-delay: -5\n"
        "Crawl-delay: nan\n"
        "Crawl-delay: 7\n"
    )
    assert fp._crawl_delay(body) == 7.0
