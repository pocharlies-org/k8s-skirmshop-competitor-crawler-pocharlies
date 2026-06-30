"""Bounded live HTTP transport for approved cart-probe adapters.

This transport is intentionally small: it enforces an application-level domain
guard, does not follow redirects, uses short timeouts, and returns a normalized
``ProbeResponse`` without logging body content.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from .transport import ProbeResponse, TransportError

DEFAULT_USER_AGENT = (
    "SkirmshopCompetitorProber/0.1 "
    "(stock audit; contact https://skirmshop.es)"
)
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=10.0)

_CHALLENGE_MARKERS = (
    "captcha",
    "cf-chl",
    "cf-challenge",
    "challenge-platform",
    "just a moment",
    "attention required",
)


class HttpProbeTransport:
    """Synchronous ``ProbeTransport`` backed by ``httpx.Client``."""

    def __init__(
        self,
        *,
        allowed_domain: str,
        timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        client: httpx.Client | None = None,
    ) -> None:
        domain = (allowed_domain or "").strip().lower().rstrip(".")
        if not domain:
            raise ValueError("allowed_domain is required")
        self._allowed_domain = domain
        self._headers = {"User-Agent": user_agent}
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers=self._headers,
        )

    def request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> ProbeResponse:
        self._validate_url(url)
        try:
            response = self._client.request(
                method.upper(),
                url,
                json=json,
                headers=self._headers,
            )
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc

        body_text = getattr(response, "text", "") or ""
        return ProbeResponse(
            status_code=response.status_code,
            json_body=_json_body(response),
            is_challenge=_looks_like_challenge(
                status_code=response.status_code,
                url=url,
                headers=dict(response.headers),
                body_text=body_text,
            ),
            text=body_text,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpProbeTransport":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise TransportError(f"unsupported URL scheme: {parsed.scheme!r}")
        host = (parsed.hostname or "").lower().rstrip(".")
        if not _host_allowed(host, self._allowed_domain):
            raise TransportError("probe URL host is outside the approved domain")


def _host_allowed(host: str, allowed_domain: str) -> bool:
    return host == allowed_domain or host.endswith("." + allowed_domain)


def _json_body(response: httpx.Response) -> dict[str, Any] | None:
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _looks_like_challenge(
    *,
    status_code: int,
    url: str,
    headers: dict[str, str],
    body_text: str,
) -> bool:
    parsed = urlparse(url)
    haystack = " ".join(
        [
            parsed.path.lower(),
            headers.get("location", "").lower(),
            body_text[:4096].lower(),
        ]
    )
    if any(marker in haystack for marker in _CHALLENGE_MARKERS):
        return True
    return status_code in {403, 429, 503} and "text/html" in headers.get(
        "content-type", ""
    ).lower()


__all__ = ["HttpProbeTransport", "DEFAULT_USER_AGENT", "DEFAULT_TIMEOUT"]
