"""B1 tests for bounded live HTTP transport using httpx MockTransport."""
from __future__ import annotations

import httpx
import pytest

from src.prober.http_transport import HttpProbeTransport
from src.prober.transport import TransportError


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_transport_allows_approved_subdomain_and_decodes_json():
    def handler(request):
        assert request.headers["user-agent"].startswith("SkirmshopCompetitorProber/")
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"ok": True},
        )

    transport = HttpProbeTransport(
        allowed_domain="airsoftquimera.com",
        client=_client(handler),
    )

    response = transport.request(
        "GET",
        "https://www.airsoftquimera.com/cacc_4_50_1_15229_10_0/",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.is_challenge is False


def test_transport_blocks_off_domain_before_http_request():
    calls = []

    def handler(request):  # pragma: no cover - must not run
        calls.append(request.url)
        return httpx.Response(200)

    transport = HttpProbeTransport(
        allowed_domain="airsoftquimera.com",
        client=_client(handler),
    )

    with pytest.raises(TransportError, match="outside"):
        transport.request("GET", "https://evil.example/cacc_4_50_1_1_1_0/")
    assert calls == []


def test_transport_marks_challenge_from_location_header():
    def handler(request):
        return httpx.Response(
            302,
            headers={"location": "/captcha.php?from=%2F"},
        )

    transport = HttpProbeTransport(
        allowed_domain="airsoftquimera.com",
        client=_client(handler),
    )

    response = transport.request("GET", "https://airsoftquimera.com/probe")

    assert response.status_code == 302
    assert response.is_challenge is True


def test_transport_marks_html_503_as_challenge():
    def handler(request):
        return httpx.Response(
            503,
            headers={"content-type": "text/html"},
            text="Service unavailable",
        )

    transport = HttpProbeTransport(
        allowed_domain="airsoftquimera.com",
        client=_client(handler),
    )

    response = transport.request("GET", "https://airsoftquimera.com/probe")

    assert response.status_code == 503
    assert response.is_challenge is True


def test_transport_wraps_httpx_errors():
    def handler(request):
        raise httpx.ConnectTimeout("timeout")

    transport = HttpProbeTransport(
        allowed_domain="airsoftquimera.com",
        client=_client(handler),
    )

    with pytest.raises(TransportError, match="timeout"):
        transport.request("GET", "https://airsoftquimera.com/probe")
