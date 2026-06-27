"""Optional, dependency-free Prometheus metrics for the one-shot crawler runner.

This module pairs a tiny in-memory metric registry (:class:`CrawlerMetrics`)
with a stdlib ``http.server`` exposition endpoint (:class:`MetricsServer`).
:mod:`src.run_once` starts the endpoint *only* when a metrics port is configured,
records the lifecycle of each tier run, and (optionally) lingers after the run so
a Prometheus scrape — or a CronJob sidecar reading ``/metrics`` once at the end —
can read the terminal values before the process exits.

Metric families (names/labels are part of the F7 observability contract):

* ``competitor_crawler_run_total{tier,status}``    — counter, runs by terminal status
* ``competitor_crawler_push_sent_total{tier}``     — counter, docs pushed to Brain
* ``competitor_crawler_push_failed_total{tier}``   — counter, docs that failed to push
* ``competitor_crawler_run_active{tier}``          — gauge, 1 while a tier run is in flight

Why no ``prometheus_client``: the runner is a short-lived CronJob process exposing
four families. The stdlib HTTP server plus a hand-rolled text exposition keep the
container image dependency-free (mirrors the existing F4 ``src/prober/metrics.py``
choice), and there is no multiprocess/registry sharing to justify the extra dep.
"""
from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Iterable, List, Tuple

logger = logging.getLogger("crawler.metrics")

# --- metric family names (stable contract) -------------------------------
RUN_TOTAL = "competitor_crawler_run_total"
PUSH_SENT_TOTAL = "competitor_crawler_push_sent_total"
PUSH_FAILED_TOTAL = "competitor_crawler_push_failed_total"
RUN_ACTIVE = "competitor_crawler_run_active"

#: Terminal run statuses used as the ``status`` label on ``RUN_TOTAL``.
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

# Family metadata, rendered in this fixed order so the exposition is stable.
_FAMILIES: Tuple[Tuple[str, str, str], ...] = (
    (RUN_TOTAL, "counter",
     "Competitor-crawler tier runs by terminal status."),
    (PUSH_SENT_TOTAL, "counter",
     "Documents successfully pushed to Brain per tier."),
    (PUSH_FAILED_TOTAL, "counter",
     "Documents that failed to push to Brain per tier."),
    (RUN_ACTIVE, "gauge",
     "1 while a tier run is in progress, else 0."),
)

#: Content type for Prometheus text exposition format version 0.0.4.
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# A label set is stored as a sorted tuple of (key, value) pairs so it is hashable
# and order-independent; this matches the rendering order Prometheus expects.
_LabelKey = Tuple[Tuple[str, str], ...]
_SeriesKey = Tuple[str, _LabelKey]


def _escape(value: str) -> str:
    """Escape a label value per the Prometheus text exposition format."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _format_value(value: float) -> str:
    """Render a sample value: integers without a trailing ``.0``."""
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return repr(float(value))


class CrawlerMetrics:
    """Thread-safe in-memory registry for the four crawler run metrics.

    The registry is updated from the asyncio runner thread and read from the
    HTTP server thread, so every mutation/render is guarded by a lock. Only the
    four documented families are exposed; the typed helpers below are the
    supported write API used by :mod:`src.run_once`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._series: Dict[_SeriesKey, float] = {}

    # --- low-level primitives --------------------------------------------
    @staticmethod
    def _key(name: str, labels: Dict[str, str]) -> _SeriesKey:
        return (name, tuple(sorted(labels.items())))

    def _inc(self, name: str, amount: float, labels: Dict[str, str]) -> None:
        if amount < 0:
            raise ValueError("counter increment must be >= 0")
        key = self._key(name, labels)
        with self._lock:
            self._series[key] = self._series.get(key, 0) + amount

    def _set(self, name: str, value: float, labels: Dict[str, str]) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._series[key] = value

    def _ensure(self, name: str, labels: Dict[str, str]) -> None:
        """Create a 0-valued series if it does not exist yet (idempotent)."""
        key = self._key(name, labels)
        with self._lock:
            self._series.setdefault(key, 0)

    def value(self, name: str, **labels: str) -> float:
        """Read a single sample value (0 if the series is absent)."""
        with self._lock:
            return self._series.get(self._key(name, labels), 0)

    # --- typed lifecycle API used by the runner --------------------------
    def ensure_tier(self, tier: str) -> None:
        """Pre-create the always-present 0 series for ``tier``.

        Makes ``run_active`` and the push counters visible on ``/metrics`` even
        before the tier completes, so a scrape mid-run is meaningful.
        """
        self._ensure(RUN_ACTIVE, {"tier": tier})
        self._ensure(PUSH_SENT_TOTAL, {"tier": tier})
        self._ensure(PUSH_FAILED_TOTAL, {"tier": tier})

    def start_run(self, tier: str) -> None:
        """Mark ``tier`` as actively running (gauge -> 1)."""
        self._set(RUN_ACTIVE, 1, {"tier": tier})

    def finish_run(
        self, tier: str, *, status: str, pushed: int = 0, failed: int = 0
    ) -> None:
        """Record a terminal run: gauge -> 0, counters incremented.

        ``status`` is one of :data:`STATUS_OK`, :data:`STATUS_ERROR`,
        :data:`STATUS_SKIPPED`. ``pushed``/``failed`` add to the push counters.
        """
        self._set(RUN_ACTIVE, 0, {"tier": tier})
        self._inc(RUN_TOTAL, 1, {"tier": tier, "status": status})
        if pushed:
            self._inc(PUSH_SENT_TOTAL, pushed, {"tier": tier})
        else:
            self._ensure(PUSH_SENT_TOTAL, {"tier": tier})
        if failed:
            self._inc(PUSH_FAILED_TOTAL, failed, {"tier": tier})
        else:
            self._ensure(PUSH_FAILED_TOTAL, {"tier": tier})

    # --- exposition -------------------------------------------------------
    def _samples(self) -> List[Tuple[str, _LabelKey, float]]:
        with self._lock:
            return [(name, labels, value)
                    for (name, labels), value in self._series.items()]

    def render(self) -> str:
        """Return the Prometheus text exposition for all four families."""
        samples = self._samples()
        by_family: Dict[str, List[Tuple[_LabelKey, float]]] = {}
        for name, labels, value in samples:
            by_family.setdefault(name, []).append((labels, value))

        lines: List[str] = []
        for name, mtype, help_text in _FAMILIES:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {mtype}")
            for labels, value in sorted(by_family.get(name, []),
                                        key=lambda s: s[0]):
                lines.append(f"{name}{_render_labels(labels)} "
                             f"{_format_value(value)}")
        return "\n".join(lines) + "\n"


def _render_labels(labels: Iterable[Tuple[str, str]]) -> str:
    items = list(labels)
    if not items:
        return ""
    body = ",".join(f'{k}="{_escape(v)}"' for k, v in items)
    return "{" + body + "}"


class _MetricsHandler(BaseHTTPRequestHandler):
    """Serves ``GET /metrics`` from the server's attached registry."""

    # Keep the access log quiet; route to our logger at debug instead of stderr.
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        logger.debug("metrics %s %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        path = self.path.split("?", 1)[0]
        if path != "/metrics":
            body = b"not found\n"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._safe_write(body)
            return
        body = self.server.metrics.render().encode("utf-8")  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)

    def _safe_write(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Scraper hung up mid-response; nothing to do but not crash the thread.
            logger.debug("metrics client disconnected before response finished")


class MetricsServer:
    """A backgrounded ``/metrics`` HTTP endpoint over the stdlib server.

    Binds ``host:port`` immediately on construction (so a bind failure surfaces
    to the caller, which can then decide to keep the job running without
    metrics). ``start`` runs ``serve_forever`` on a daemon thread; ``stop``
    shuts it down and closes the socket. ``port`` reflects the actually-bound
    port, which is useful when constructed with ``port=0`` (ephemeral).
    """

    def __init__(self, metrics: CrawlerMetrics, *, host: str = "0.0.0.0",
                 port: int = 0) -> None:
        self._httpd = ThreadingHTTPServer((host, port), _MetricsHandler)
        # Attach the registry so the handler can reach it without globals.
        self._httpd.metrics = metrics  # type: ignore[attr-defined]
        self._httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="metrics-http",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        # ``shutdown`` blocks on the serve_forever loop's stop event, so only
        # call it when the loop is actually running; otherwise just close the
        # bound socket (e.g. constructed-but-never-started).
        if self._thread is not None:
            self._httpd.shutdown()
            self._thread.join(timeout=5)
            self._thread = None
        self._httpd.server_close()


__all__ = [
    "CrawlerMetrics",
    "MetricsServer",
    "RUN_TOTAL",
    "PUSH_SENT_TOTAL",
    "PUSH_FAILED_TOTAL",
    "RUN_ACTIVE",
    "STATUS_OK",
    "STATUS_ERROR",
    "STATUS_SKIPPED",
    "CONTENT_TYPE",
]
