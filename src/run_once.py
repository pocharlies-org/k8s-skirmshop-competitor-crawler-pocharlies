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

Observability is opt-in and off by default: ``--metrics-port`` (or env
``METRICS_PORT``) starts a Prometheus ``/metrics`` endpoint for the run, and
``--metrics-linger-seconds`` (env ``METRICS_LINGER_SECONDS``, default 0) keeps it
serving briefly after completion so a CronJob run is still scrapeable at the end.
The endpoint is pure observability — it never changes the job's exit code.

Examples::

    python -m src.run_once --tier tier1
    python -m src.run_once --tier tier1 --tier tier2
    python -m src.run_once --all
    python -m src.run_once --all --config /app/config.yaml
    python -m src.run_once --all --metrics-port 9090 --metrics-linger-seconds 15
"""
import argparse
import asyncio
import logging
import os
import time
from pathlib import Path

from src.metrics_exporter import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    CrawlerMetrics,
    MetricsServer,
)
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
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=None,
        metavar="PORT",
        help="Expose a Prometheus /metrics endpoint on this TCP port "
        "(0 = ephemeral). Disabled when unset; env METRICS_PORT is the "
        "fallback. Observability only — never affects the job exit code.",
    )
    parser.add_argument(
        "--metrics-linger-seconds",
        type=int,
        default=None,
        metavar="SECONDS",
        help="After the run completes, keep /metrics serving for this many "
        "seconds so a final scrape can read terminal values before exit "
        "(default 0; env METRICS_LINGER_SECONDS).",
    )
    return parser.parse_args(argv)


def _resolve_metrics_port(args: argparse.Namespace) -> int | None:
    """Resolve the metrics port from CLI/env, or ``None`` when disabled.

    A bad value disables metrics (logged) rather than failing the job — the
    endpoint is observability, never a reason to abort a crawl window.
    """
    raw = args.metrics_port
    if raw is None:
        env = os.getenv("METRICS_PORT")
        if not env or not env.strip():
            return None
        try:
            raw = int(env)
        except ValueError:
            logger.error("invalid METRICS_PORT=%r; metrics disabled", env)
            return None
    if not 0 <= raw <= 65535:
        logger.error("metrics port %d out of range 0-65535; metrics disabled", raw)
        return None
    return raw


def _resolve_linger_seconds(args: argparse.Namespace) -> int:
    """Resolve the post-run linger seconds from CLI/env (default 0)."""
    raw = args.metrics_linger_seconds
    if raw is None:
        env = os.getenv("METRICS_LINGER_SECONDS")
        if not env or not env.strip():
            return 0
        try:
            raw = int(env)
        except ValueError:
            logger.error("invalid METRICS_LINGER_SECONDS=%r; using 0", env)
            return 0
    if raw < 0:
        logger.warning("negative metrics linger %d; using 0", raw)
        return 0
    return raw


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


async def run_selected(
    selected: list[tuple[str, dict]],
    metrics: CrawlerMetrics | None = None,
) -> tuple[int, int]:
    """Run each selected tier sequentially; aggregate ``(pushed, failed)``.

    When ``metrics`` is supplied, each tier's lifecycle is recorded:
    ``run_active`` toggles 1→0 around the crawl and ``run_total`` /
    ``push_*_total`` are incremented on completion. A tier that raises records a
    terminal ``status="error"`` sample and re-raises, preserving the runner's
    existing exit-code behavior (the error still aborts the run). Metrics never
    change control flow.
    """
    total_pushed = 0
    total_failed = 0
    for tier_name, tier in selected:
        stores = (tier or {}).get("stores") or []
        if not stores:
            logger.warning("[%s] no stores configured — skipping", tier_name)
            if metrics is not None:
                metrics.finish_run(tier_name, status=STATUS_SKIPPED)
            continue
        if metrics is not None:
            metrics.start_run(tier_name)
        try:
            pushed, failed = await crawl_tier(tier_name, stores)
        except Exception:
            if metrics is not None:
                metrics.finish_run(tier_name, status=STATUS_ERROR)
            raise
        if metrics is not None:
            metrics.finish_run(
                tier_name, status=STATUS_OK, pushed=pushed, failed=failed
            )
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

    metrics, server = _maybe_start_metrics(args, selected)
    linger = _resolve_linger_seconds(args) if server is not None else 0
    try:
        return _run_and_status(args, selected, metrics)
    finally:
        if server is not None:
            if linger > 0:
                logger.info(
                    "metrics linger %ds before shutdown for a final scrape",
                    linger,
                )
                time.sleep(linger)
            server.stop()
            logger.info("metrics endpoint stopped")


def _maybe_start_metrics(
    args: argparse.Namespace,
    selected: list[tuple[str, dict]],
) -> tuple[CrawlerMetrics | None, MetricsServer | None]:
    """Start the optional /metrics endpoint; never fail the job over it."""
    port = _resolve_metrics_port(args)
    if port is None:
        return None, None
    metrics = CrawlerMetrics()
    for name, _ in selected:
        metrics.ensure_tier(name)
    try:
        server = MetricsServer(metrics, port=port)
        server.start()
    except OSError as e:  # bind/permission failure — degrade, don't abort
        logger.error("failed to start metrics endpoint on port %s: %r", port, e)
        return metrics, None
    logger.info("metrics endpoint serving on :%d/metrics", server.port)
    return metrics, server


def _run_and_status(
    args: argparse.Namespace,
    selected: list[tuple[str, dict]],
    metrics: CrawlerMetrics | None,
) -> int:
    """Run the selected tiers and map the outcome to a process exit code."""
    try:
        total_pushed, total_failed = asyncio.run(run_selected(selected, metrics))
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
