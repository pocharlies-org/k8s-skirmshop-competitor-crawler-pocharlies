"""Domain egress guard for the competitor crawler.

Single source of truth for *"is this URL safe to fetch for store ``domain``?"*.

The crawler must never make an HTTP request (direct ``httpx`` *or* Firecrawl)
to a host that is not the configured store domain or one of its subdomains.
A naive substring check (``domain in netloc``) is exploitable in three ways
that this module closes:

1. **Sibling-suffix spoof** — ``evilgunfire.com`` *contains* ``gunfire.com`` as
   a substring, so ``"gunfire.com" in "evilgunfire.com"`` is ``True``. We require
   an exact host match or a dot-delimited subdomain (``*.gunfire.com``).
2. **Userinfo spoof** — ``https://gunfire.com@evil.com/`` has ``netloc ==
   "gunfire.com@evil.com"`` (substring match passes) but the *real* host the
   request reaches is ``evil.com``. We compare against ``urlsplit().hostname``,
   which discards userinfo and port.
3. **Non-HTTP schemes** — ``javascript:``, ``data:``, ``mailto:``,
   ``ftp://`` and protocol-relative ``//evil.com`` are all rejected; only
   ``http`` and ``https`` are allowed to egress.

Pure stdlib, no network, deterministic — safe to import anywhere.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class EgressBlockedError(Exception):
    """Raised when a URL is not permitted to egress for a given store domain."""


def _normalize_domain(domain: str) -> str:
    """Lower-case and strip stray leading/trailing dots and whitespace.

    Config domains are bare apex hosts (``gunfire.com``); this tolerates an
    accidental ``.gunfire.com`` / ``gunfire.com.`` / mixed case without
    changing matching semantics.
    """
    return (domain or "").strip().lower().strip(".")


def _host_of(url: str) -> str | None:
    """Return the real, normalized host of an http(s) URL, or ``None``.

    ``None`` means "not eligible to egress": missing/blank URL, a non-http(s)
    scheme, an unparseable URL, or no host component. ``urlsplit().hostname``
    intentionally strips userinfo (``user:pass@``) and the port, so spoofs of
    the form ``https://gunfire.com@evil.com/`` resolve to ``evil.com``.
    """
    if not url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        # Malformed URL (e.g. invalid IPv6 / bad port) — never egress.
        return None
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        return None
    try:
        host = parts.hostname
    except ValueError:
        return None
    if not host:
        return None
    # Drop a single FQDN trailing dot so ``gunfire.com.`` == ``gunfire.com``.
    return host.lower().rstrip(".")


def is_allowed_url(url: str, domain: str) -> bool:
    """Return ``True`` iff ``url`` may be fetched for store ``domain``.

    Rules:
    - scheme is ``http`` or ``https``;
    - the real host (userinfo/port stripped) is exactly ``domain`` or a
      dot-delimited subdomain of it (``www.gunfire.com`` ✓, ``evilgunfire.com``
      ✗, ``gunfire.com.evil.com`` ✗).
    """
    norm_domain = _normalize_domain(domain)
    if not norm_domain:
        return False
    host = _host_of(url)
    if host is None:
        return False
    return host == norm_domain or host.endswith("." + norm_domain)


def assert_allowed_url(url: str, domain: str) -> None:
    """Raise :class:`EgressBlockedError` if ``url`` is not allowed for ``domain``.

    Convenience for call sites that prefer an explicit typed error to a boolean
    branch. The message never leaks anything beyond the URL/domain already in
    scope at the call site.
    """
    if not is_allowed_url(url, domain):
        raise EgressBlockedError(
            f"egress blocked: {url!r} is not on-domain for {domain!r}"
        )
