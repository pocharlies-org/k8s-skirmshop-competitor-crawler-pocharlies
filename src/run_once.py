"""Bounded one-shot tier runner for Kubernetes CronJob execution.

Unlike :mod:`src.main` — a long-lived APScheduler daemon that starts cron jobs
and then blocks on ``SIGTERM``/``SIGINT`` — this entrypoint runs one or more
tiers *sequentially to completion* and exits with a process status code a
CronJob can use as job success/failure:

* ``0`` — every selected tier ran to completion.
* ``1`` — an unhandled crawl error aborted the run, or (with
  ``--fail-on-push-errors``) at least one document failed to push.
* ``2`` — usage/config error: unknown tier, no tiers selected, missing/invalid
  config (also the argparse exit code for bad CLI usage).

It reuses the existing :func:`src.scheduler.crawl_tier` coroutine, so the crawl
and push-ingest behavior is identical to the scheduled path — only the trigger
differs (one-shot vs cron). The cron ``schedule`` field in ``config.yaml`` is
intentionally ignored here; selection is explicit via ``--tier`` / ``--all``.

Examples::

    python -m src.run_once --tier tier1
    python -m src.run_once --tier tier1 --tier tier2
    python -m src.run_once --all
    python -m src.run_once --all --config /app/config.yaml
"""
import argparse
import asyncio
import logging
import os
from pathlib import Path

from src.scheduler import crawl_tier, load_config

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
#: Default config path; overridable by ``CONFIG_PATH`` env or ``--config``.
DEFAULT_CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "/app/config.yaml"))

#: Exit codes (kept stable for CronJob backoff/alerting semantics).
EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2

logger = logging.getLogger("crawler.run_once")


def _setup_logging() -> None:
    """Match ``src.main`` log format so cron and daemon logs read alike."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_once",
        description="Run one or more competitor-crawler tiers once and exit.",
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--tier",
        action="append",
        dest="tiers",
        metavar="NAME",
        help="Tier name to run (repeatable); mutually exclusive with --all.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="Run every tier defined in the config, in declaration order.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.yaml (default: %(default)s).",
    )
    parser.add_argument(
        "--fail-on-push-errors",
        action="store_true",
        help="Exit non-zero if any document failed to push to brain.",
    )
    return parser.parse_args(argv)


def _load_tiers(config_path: Path) -> dict | None:
    """Load and validate the ``tiers`` mapping. Returns ``None`` on any error."""
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        logger.error("config file not found: %s", config_path)
        return None
    except Exception as e:  # noqa: BLE001 — surface any parse error explicitly
        logger.error("failed to load config %s: %r", config_path, e)
        return None

    tiers = (config or {}).get("tiers") or {}
    if not isinstance(tiers, dict) or not tiers:
        logger.error("no tiers defined in config %s", config_path)
        return None
    return tiers


def _select(tiers: dict, args: argparse.Namespace) -> list[tuple[str, dict]] | None:
    """Resolve the requested tiers to ``(name, tier)`` pairs, or ``None``.

    ``None`` signals a usage error (unknown tier / empty selection) already
    logged for the operator.
    """
    if args.all:
        return list(tiers.items())

    selected: list[tuple[str, dict]] = []
    missing: list[str] = []
    for name in args.tiers or []:
        if name in tiers:
            selected.append((name, tiers[name]))
        else:
            missing.append(name)

    if missing:
        logger.error(
            "unknown tier(s): %s; available: %s",
            ", ".join(missing),
            ", ".join(sorted(tiers)),
        )
        return None
    if not selected:
        logger.error("no tiers selected")
        return None
    return selected


async def run_selected(selected: list[tuple[str, dict]]) -> tuple[int, int]:
    """Run each selected tier sequentially; aggregate ``(pushed, failed)``."""
    total_pushed = 0
    total_failed = 0
    for tier_name, tier in selected:
        stores = (tier or {}).get("stores") or []
        if not stores:
            logger.warning("[%s] no stores configured — skipping", tier_name)
            continue
        pushed, failed = await crawl_tier(tier_name, stores)
        total_pushed += pushed
        total_failed += failed
    return total_pushed, total_failed


def run(argv: list[str] | None = None) -> int:
    """Entry logic returning a process exit code (no ``sys.exit`` side effect)."""
    args = parse_args(argv)
    _setup_logging()

    tiers = _load_tiers(args.config)
    if tiers is None:
        return EXIT_USAGE_ERROR

    selected = _select(tiers, args)
    if selected is None:
        return EXIT_USAGE_ERROR

    names = ", ".join(name for name, _ in selected)
    logger.info("run_once start: tiers=[%s] config=%s", names, args.config)

    try:
        total_pushed, total_failed = asyncio.run(run_selected(selected))
    except Exception:  # noqa: BLE001 — convert to a non-zero job status
        logger.exception("run_once aborted by unhandled crawl error")
        return EXIT_RUNTIME_ERROR

    logger.info(
        "run_once complete: tiers=%d pushed=%d failed=%d",
        len(selected),
        total_pushed,
        total_failed,
    )
    if args.fail_on_push_errors and total_failed:
        logger.error(
            "run_once exiting non-zero: %d document(s) failed to push "
            "(--fail-on-push-errors)",
            total_failed,
        )
        return EXIT_RUNTIME_ERROR
    return EXIT_OK


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
