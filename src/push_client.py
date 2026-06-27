"""Push batches of crawled products to skirmshop-brain push-ingest.

Authentication
--------------
Brain ``push-ingest`` is guarded by ``Depends(require_oauth_or_api_key)``. This
client authenticates with the ``X-API-Key`` header sourced from the
``BRAIN_API_KEY`` environment variable (delivered via the
``competitor-crawler-secrets`` Secret in production).

Two operating modes:

* **Permissive (default / dev):** if ``BRAIN_API_KEY`` is absent the client
  still POSTs but logs a warning. This keeps local/dev brains that disable auth
  working without extra config.
* **Fail-closed (production):** set ``REQUIRE_BRAIN_API_KEY=true`` to refuse any
  POST when the key is missing/empty. Instead of shipping unauthenticated data
  to a production brain, ``push_documents`` raises :class:`BrainAuthError`
  before opening any connection.

Auth-related env vars are read at call time (not import time) so the fail-closed
decision reflects the live runtime configuration and stays unit-testable.
"""
import asyncio
import logging
import os
import random
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)

BRAIN_URL = os.getenv("BRAIN_URL", "http://skirmshop-brain-v2:5001").rstrip("/")
BRAIN_INSTANCE = os.getenv("BRAIN_INSTANCE", "skirmshop")
PUSH_BATCH_SIZE = int(os.getenv("PUSH_BATCH_SIZE", "20"))

#: Env var holding the Brain API key (X-API-Key value). Never logged.
BRAIN_API_KEY_ENV = "BRAIN_API_KEY"
#: Env var enabling fail-closed auth: when truthy, a missing key blocks POSTs.
REQUIRE_BRAIN_API_KEY_ENV = "REQUIRE_BRAIN_API_KEY"
#: HTTP header Brain expects for API-key auth.
API_KEY_HEADER = "X-API-Key"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class BrainAuthError(RuntimeError):
    """Raised in fail-closed mode when ``BRAIN_API_KEY`` is missing/empty.

    Carries no secret material — only that the key is absent.
    """


def _api_key() -> str | None:
    """Return the configured Brain API key, or ``None`` if unset/empty."""
    key = os.getenv(BRAIN_API_KEY_ENV)
    if key is not None:
        key = key.strip()
    return key or None


def _require_api_key() -> bool:
    """Whether fail-closed auth is enabled (``REQUIRE_BRAIN_API_KEY`` truthy)."""
    return os.getenv(REQUIRE_BRAIN_API_KEY_ENV, "").strip().lower() in _TRUTHY


def _auth_headers(api_key: str | None) -> dict[str, str]:
    """Build request headers. Empty when no key (httpx omits an empty dict)."""
    if api_key:
        return {API_KEY_HEADER: api_key}
    return {}


async def push_documents(docs: Iterable[dict]) -> tuple[int, int]:
    """POST docs to brain in batches. Returns (sent, failed).

    Raises:
        BrainAuthError: when ``REQUIRE_BRAIN_API_KEY`` is truthy but
            ``BRAIN_API_KEY`` is missing/empty (fail-closed). No POST is issued.
    """
    docs = list(docs)
    if not docs:
        return 0, 0

    api_key = _api_key()
    if _require_api_key() and not api_key:
        # Fail closed: do not leak crawled data to a production brain without
        # authentication. Raised before any client/connection is created.
        logger.error(
            "%s is enabled but %s is missing/empty — refusing to POST to brain "
            "push-ingest (fail-closed)",
            REQUIRE_BRAIN_API_KEY_ENV,
            BRAIN_API_KEY_ENV,
        )
        raise BrainAuthError(
            f"{REQUIRE_BRAIN_API_KEY_ENV} is set but {BRAIN_API_KEY_ENV} is "
            "missing/empty; refusing unauthenticated push to brain push-ingest"
        )
    if not api_key:
        logger.warning(
            "%s not set — pushing to brain push-ingest without %s "
            "(set %s=true to fail closed in production)",
            BRAIN_API_KEY_ENV,
            API_KEY_HEADER,
            REQUIRE_BRAIN_API_KEY_ENV,
        )

    headers = _auth_headers(api_key)
    sent = failed = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(docs), PUSH_BATCH_SIZE):
            batch = docs[i:i + PUSH_BATCH_SIZE]
            attempt = 0
            while True:
                attempt += 1
                try:
                    r = await client.post(
                        f"{BRAIN_URL}/instances/{BRAIN_INSTANCE}/push-ingest",
                        json={"adapter": "competitor", "documents": batch},
                        headers=headers,
                    )
                    if r.status_code in (429, 502, 503, 504):
                        raise httpx.HTTPStatusError(
                            "transient", request=r.request, response=r,
                        )
                    r.raise_for_status()
                    sent += len(batch)
                    break
                except (httpx.TimeoutException, httpx.ConnectError,
                        httpx.ReadError, httpx.HTTPStatusError) as e:
                    if attempt >= 4:
                        logger.error(
                            f"push-ingest exhausted retries on batch {i}: {e!r}"
                        )
                        failed += len(batch)
                        break
                    sleep = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        f"push-ingest transient (attempt {attempt}/4): "
                        f"{e!r} — retry in {sleep:.1f}s"
                    )
                    await asyncio.sleep(sleep)
    logger.info(f"push-ingest done: sent={sent} failed={failed}")
    return sent, failed
