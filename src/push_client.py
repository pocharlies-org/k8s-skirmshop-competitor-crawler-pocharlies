"""Push batches of crawled products to skirmshop-brain push-ingest."""
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


async def push_documents(docs: Iterable[dict]) -> tuple[int, int]:
    """POST docs to brain in batches. Returns (sent, failed)."""
    docs = list(docs)
    if not docs:
        return 0, 0
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
