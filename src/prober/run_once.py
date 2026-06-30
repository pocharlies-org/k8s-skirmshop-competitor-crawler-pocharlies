"""One-shot stock-prober runner for explicit approved targets.

The runner is deliberately target-file driven. It never discovers products on
its own and refuses domains outside the approved B1 scope.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

from src.history_runtime import (
    HistoryConfig,
    HistoryConfigError,
    load_history_config,
    open_history_connection,
)
from src.history_writer import write_observations
from src.prober.airsoftquimera import (
    APPROVED_DOMAIN,
    DEFAULT_MAX_QTY,
)
from src.prober.contract import (
    ProbeResult,
    ProbeStatus,
    ProbeTarget,
    probe_result_to_observation,
)
from src.prober.http_transport import HttpProbeTransport
from src.prober.killswitch import DomainGuard
from src.prober.metrics import Metrics
from src.prober.service import probe_stock

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEFAULT_TARGETS_PATH = Path(os.getenv("PROBER_TARGETS_PATH", "/app/prober-targets.json"))
DEFAULT_MAX_TARGETS = 10

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2

logger = logging.getLogger("prober.run_once")


def _setup_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prober.run_once",
        description="Run approved stock-prober targets once and exit.",
    )
    parser.add_argument(
        "--targets",
        type=Path,
        default=DEFAULT_TARGETS_PATH,
        help="JSON file containing a list or {'targets': [...]} payload.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="History run id. Defaults to prober:<UTC timestamp>.",
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=DEFAULT_MAX_TARGETS,
        help="Refuse target files larger than this count (default 10).",
    )
    parser.add_argument(
        "--max-qty",
        type=int,
        default=DEFAULT_MAX_QTY,
        help="Maximum quantity to probe per product (hard cap 10).",
    )
    parser.add_argument(
        "--write-history",
        action="store_true",
        help="Write ProbeResult observations to Postgres append-only history.",
    )
    return parser.parse_args(argv)


def run(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[[ProbeTarget], object] | None = None,
    history_connect=open_history_connection,
) -> int:
    args = parse_args(argv)
    _setup_logging()

    try:
        targets = load_targets(args.targets, max_targets=args.max_targets)
        max_qty = _validate_max_qty(args.max_qty)
        run_id = args.run_id or _default_run_id()
        history_config = _prepare_history(args.write_history)
    except (OSError, ValueError, HistoryConfigError) as exc:
        logger.error("prober setup failed: %s", exc)
        return EXIT_USAGE_ERROR

    logger.info(
        "prober run start: targets=%d write_history=%s run_id=%s",
        len(targets),
        args.write_history,
        run_id,
    )
    try:
        results = run_targets(
            targets,
            max_qty=max_qty,
            transport_factory=transport_factory or _default_transport_factory,
        )
        if args.write_history:
            _write_history(results, run_id, history_config, history_connect)
    except Exception:  # noqa: BLE001 - keep CronJob status deterministic
        logger.exception("prober run aborted")
        return EXIT_RUNTIME_ERROR

    failures = [
        result for result in results
        if result.probe_status not in (ProbeStatus.PROBED, ProbeStatus.UNAVAILABLE)
    ]
    for result in results:
        logger.info(
            "probe result: domain=%s product_key=%s status=%s stock_status=%s "
            "stock_qty=%s cleanup=%s error=%s block=%s",
            result.domain,
            result.product_key,
            result.probe_status.value,
            result.stock_status,
            result.stock_qty,
            result.cleanup_status.value,
            result.error_code,
            result.block_reason,
        )

    if failures:
        logger.error("prober exiting non-zero: %d target(s) failed", len(failures))
        return EXIT_RUNTIME_ERROR
    logger.info("prober run complete: targets=%d", len(results))
    return EXIT_OK


def load_targets(path: Path, *, max_targets: int = DEFAULT_MAX_TARGETS) -> list[ProbeTarget]:
    if max_targets < 1:
        raise ValueError("max_targets must be >= 1")
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("targets") if isinstance(raw, Mapping) else raw
    if not isinstance(items, list):
        raise ValueError("targets JSON must be a list or {'targets': [...]}")
    if len(items) > max_targets:
        raise ValueError(f"too many targets: {len(items)} > {max_targets}")
    targets = [_target_from_mapping(item) for item in items]
    if not targets:
        raise ValueError("no targets supplied")
    return targets


def run_targets(
    targets: Iterable[ProbeTarget],
    *,
    max_qty: int,
    transport_factory: Callable[[ProbeTarget], object],
) -> list[ProbeResult]:
    metrics = Metrics()
    guard = DomainGuard(metrics)
    observed_at = datetime.now(timezone.utc)
    results: list[ProbeResult] = []

    for target in targets:
        transport = transport_factory(target)
        try:
            result = probe_stock(
                target,
                transport,
                guard,
                metrics,
                observed_at,
                airsoftquimera_max_qty=max_qty,
            )
        finally:
            close = getattr(transport, "close", None)
            if callable(close):
                close()
        results.append(result)
    return results


def _target_from_mapping(item: object) -> ProbeTarget:
    if not isinstance(item, Mapping):
        raise ValueError("each target must be an object")
    domain = str(item.get("domain") or "").strip().lower()
    if domain != APPROVED_DOMAIN:
        raise ValueError(f"domain not approved for B1: {domain!r}")
    platform = str(item.get("platform") or APPROVED_DOMAIN).strip().lower()
    if platform not in {"airsoftquimera", APPROVED_DOMAIN}:
        raise ValueError(f"platform not approved for B1: {platform!r}")
    return ProbeTarget(
        domain=domain,
        product_key=str(item.get("product_key") or "").strip(),
        url=str(item.get("url") or "").strip(),
        platform=platform,
        variant_id=(
            None if item.get("variant_id") is None
            else str(item.get("variant_id")).strip()
        ),
    )


def _validate_max_qty(max_qty: int) -> int:
    if not 1 <= max_qty <= DEFAULT_MAX_QTY:
        raise ValueError(f"max_qty must be between 1 and {DEFAULT_MAX_QTY}")
    return max_qty


def _prepare_history(write_history: bool) -> HistoryConfig | None:
    if not write_history:
        return None
    return load_history_config()


def _write_history(
    results: list[ProbeResult],
    run_id: str,
    config: HistoryConfig | None,
    connect,
) -> None:
    if config is None:
        raise HistoryConfigError("history config is required")
    observations = [probe_result_to_observation(result, run_id) for result in results]
    conn = connect(config)
    try:
        outcome = write_observations(conn, observations)
    finally:
        close = getattr(conn, "close", None)
        if callable(close):
            close()
    logger.info(
        "history write complete: inserted=%d skipped=%d",
        outcome.inserted,
        outcome.skipped,
    )


def _default_transport_factory(target: ProbeTarget) -> HttpProbeTransport:
    return HttpProbeTransport(allowed_domain=target.domain)


def _default_run_id() -> str:
    return "prober:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()


__all__ = [
    "EXIT_OK",
    "EXIT_RUNTIME_ERROR",
    "EXIT_USAGE_ERROR",
    "load_targets",
    "run_targets",
    "run",
    "main",
]
