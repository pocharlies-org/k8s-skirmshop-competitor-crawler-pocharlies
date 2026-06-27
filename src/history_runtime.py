"""Runtime glue for writing crawler observations to Postgres history.

The F3 writer is deliberately DB-API oriented and independent from the crawler.
This module is the F7 bridge: it maps crawled push-ingest documents to F3
``Observation`` rows and opens a psycopg connection only when explicitly enabled
with ``HISTORY_ENABLED=true``.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from src.history_writer import (
    DEFAULT_CURRENCY,
    WriteResult,
    from_dry_run_payload,
    write_observations,
)
from src.stock import normalize_availability

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class HistoryConfigError(RuntimeError):
    """Raised when history is enabled but required DB env is missing/invalid."""


@dataclass(frozen=True)
class HistoryConfig:
    enabled: bool
    host: str | None = None
    port: int = 5432
    database: str | None = None
    user: str | None = None
    password: str | None = None
    connect_timeout: int = 10


@dataclass(frozen=True)
class HistoryWriteResult:
    enabled: bool
    inserted: int = 0
    skipped: int = 0

    @classmethod
    def from_write_result(cls, result: WriteResult) -> "HistoryWriteResult":
        return cls(enabled=True, inserted=result.inserted, skipped=result.skipped)


def _is_truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _TRUTHY


def history_enabled(env: Mapping[str, str] | None = None) -> bool:
    env = env or os.environ
    return _is_truthy(env.get("HISTORY_ENABLED"))


def load_history_config(env: Mapping[str, str] | None = None) -> HistoryConfig:
    """Load DB config from env.

    Disabled mode is a no-op. Enabled mode is fail-closed: every required
    setting must be present before any crawl traffic is allowed to proceed.
    """
    env = env or os.environ
    if not history_enabled(env):
        return HistoryConfig(enabled=False)

    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [name for name in required if not (env.get(name) or "").strip()]
    if missing:
        raise HistoryConfigError(
            "HISTORY_ENABLED=true but missing DB env: " + ", ".join(missing)
        )

    try:
        port = int(env.get("PGPORT", "5432"))
    except ValueError as exc:
        raise HistoryConfigError("PGPORT must be an integer") from exc
    if not 0 < port <= 65535:
        raise HistoryConfigError("PGPORT must be between 1 and 65535")

    try:
        connect_timeout = int(env.get("PGCONNECT_TIMEOUT", "10"))
    except ValueError as exc:
        raise HistoryConfigError("PGCONNECT_TIMEOUT must be an integer") from exc
    if connect_timeout <= 0:
        raise HistoryConfigError("PGCONNECT_TIMEOUT must be positive")

    return HistoryConfig(
        enabled=True,
        host=env["PGHOST"].strip(),
        port=port,
        database=env["PGDATABASE"].strip(),
        user=env["PGUSER"].strip(),
        password=env["PGPASSWORD"],
        connect_timeout=connect_timeout,
    )


def validate_history_config(env: Mapping[str, str] | None = None) -> HistoryConfig:
    """Validate config without opening a network connection."""
    return load_history_config(env)


def observations_from_docs(
    docs: Iterable[Mapping[str, object]],
    *,
    domain: str,
    run_id: str,
    observed_at: datetime,
) -> list:
    """Map crawler push-ingest docs to F3 ``Observation`` objects."""
    products: list[dict] = []
    for doc in docs:
        metadata = doc.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}

        source_id = doc.get("source_id") or metadata.get("source_id")
        if not source_id:
            raise ValueError("history document missing source_id")

        raw_availability = metadata.get("availability")
        stock_status = metadata.get("stock_status")
        stock_method = metadata.get("stock_method")
        if not stock_status or not stock_method:
            stock_status, stock_method = normalize_availability(
                raw_availability if isinstance(raw_availability, str) else None
            )

        products.append({
            "source_id": source_id,
            "domain": metadata.get("domain") or domain,
            "price": metadata.get("price"),
            "currency": metadata.get("currency") or DEFAULT_CURRENCY,
            "vat_incl": metadata.get("vat_incl"),
            "stock_qty": metadata.get("stock_qty"),
            "stock_status": stock_status,
            "stock_method": stock_method,
            "is_promotion": bool(metadata.get("is_promotion", False)),
            "raw_snapshot_s3": metadata.get("raw_snapshot_s3"),
            "crawl_success": bool(metadata.get("crawl_success", True)),
            "error_code": metadata.get("error_code"),
        })

    return from_dry_run_payload(
        {"domain": domain, "products": products},
        run_id,
        observed_at,
    )


def open_history_connection(config: HistoryConfig):
    """Open a psycopg connection. Imported lazily so disabled tests need no DB."""
    import psycopg

    return psycopg.connect(
        host=config.host,
        port=config.port,
        dbname=config.database,
        user=config.user,
        password=config.password,
        connect_timeout=config.connect_timeout,
    )


def write_docs_history(
    docs: Sequence[Mapping[str, object]],
    *,
    domain: str,
    run_id: str,
    observed_at: datetime,
    config: HistoryConfig | None = None,
    connect=open_history_connection,
) -> HistoryWriteResult:
    """Write crawled docs to Postgres history when enabled."""
    config = config or load_history_config()
    if not config.enabled:
        return HistoryWriteResult(enabled=False)
    if not docs:
        return HistoryWriteResult(enabled=True)

    observations = observations_from_docs(
        docs,
        domain=domain,
        run_id=run_id,
        observed_at=observed_at,
    )
    conn = connect(config)
    try:
        result = write_observations(conn, observations)
    finally:
        close = getattr(conn, "close", None)
        if callable(close):
            close()

    logger.info(
        "[%s] history write complete: inserted=%d skipped=%d",
        domain,
        result.inserted,
        result.skipped,
    )
    return HistoryWriteResult.from_write_result(result)
