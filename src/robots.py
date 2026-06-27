"""robots.txt policy helpers for the competitor crawler."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

CRAWLER_USER_AGENT = "skirmshop-competitor-crawler"
CRAWLER_USER_AGENT_HEADER = f"{CRAWLER_USER_AGENT}/1.0 (+research)"


@dataclass(frozen=True)
class RobotsPolicy:
    """Parsed robots.txt policy for one crawl origin.

    ``parser=None`` means robots.txt was unavailable or non-authoritative, so
    URL fetches are allowed but the configured app delay still applies.
    """

    robots_url: str
    parser: RobotFileParser | None
    crawl_delay_seconds: float | None = None

    def can_fetch(self, url: str) -> bool:
        if self.parser is None:
            return True
        return self.parser.can_fetch(CRAWLER_USER_AGENT, url)


def robots_url_for(start_url: str) -> str:
    parsed = urlparse(start_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def _parse_robots(robots_url: str, body: str) -> RobotsPolicy:
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(body.splitlines())

    delay = parser.crawl_delay(CRAWLER_USER_AGENT)
    if delay is None:
        delay = parser.crawl_delay("*")
    delay_seconds = float(delay) if delay and float(delay) > 0 else None
    return RobotsPolicy(
        robots_url=robots_url,
        parser=parser,
        crawl_delay_seconds=delay_seconds,
    )


def _disallow_all(robots_url: str) -> RobotsPolicy:
    return _parse_robots(robots_url, "User-agent: *\nDisallow: /\n")


async def load_robots_policy(
    client: httpx.AsyncClient,
    start_url: str,
    domain: str,
) -> RobotsPolicy:
    """Fetch and parse robots.txt for the start URL origin.

    Missing or transiently unreachable robots.txt is fail-open, matching common
    crawler behavior while keeping the configured application delay. Explicit
    401/403 on robots.txt is treated conservatively as disallow-all.
    """

    robots_url = robots_url_for(start_url)
    if not robots_url:
        logger.warning("[%s] robots unavailable: invalid start URL %s", domain, start_url)
        return RobotsPolicy(robots_url="", parser=None)

    try:
        resp = await client.get(robots_url, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - robots failure must not crash crawl
        logger.warning("[%s] robots fetch failed for %s: %r", domain, robots_url, exc)
        return RobotsPolicy(robots_url=robots_url, parser=None)

    if resp.status_code == 200:
        policy = _parse_robots(robots_url, resp.text)
        if policy.crawl_delay_seconds is not None:
            logger.info(
                "[%s] robots crawl-delay=%s from %s",
                domain,
                policy.crawl_delay_seconds,
                robots_url,
            )
        return policy

    if resp.status_code in {401, 403}:
        logger.warning(
            "[%s] robots returned %d for %s; treating as disallow-all",
            domain,
            resp.status_code,
            robots_url,
        )
        return _disallow_all(robots_url)

    logger.info("[%s] robots unavailable: %s returned %d", domain, robots_url, resp.status_code)
    return RobotsPolicy(robots_url=robots_url, parser=None)
