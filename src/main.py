"""Entrypoint — wire scheduler, signal handlers, healthcheck marker."""
import asyncio
import logging
import os
import signal
from pathlib import Path

from src.scheduler import build_scheduler, load_config

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
HEALTHCHECK_FILE = Path("/tmp/healthy")


def _setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


async def main():
    _setup_logging()
    log = logging.getLogger("crawler.main")
    config = load_config()
    scheduler = build_scheduler(config)
    scheduler.start()
    log.info("scheduler started; jobs: %s",
             [j.id for j in scheduler.get_jobs()])

    # Mark healthy for the Dockerfile HEALTHCHECK
    HEALTHCHECK_FILE.write_text("ok\n")

    # Wait for SIGTERM/SIGINT
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)
    log.info("idle until next cron fires; signal=%s to stop",
             ",".join(s.name for s in (signal.SIGTERM, signal.SIGINT)))
    await stop_event.wait()
    log.info("shutdown signal received")
    scheduler.shutdown(wait=False)
    HEALTHCHECK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
