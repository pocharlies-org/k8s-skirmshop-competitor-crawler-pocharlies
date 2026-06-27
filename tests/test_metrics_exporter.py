"""Unit tests for src.metrics_exporter — no external network.

The HTTP server is bound to ``127.0.0.1:0`` (loopback, ephemeral port) so the
exposition path is exercised over a real socket without touching any external
host. Everything else is pure in-memory registry assertions.
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import metrics_exporter as mx


# --- registry / rendering -------------------------------------------------

def test_render_exposes_all_four_required_families():
    m = mx.CrawlerMetrics()
    m.ensure_tier("tier1")
    m.start_run("tier1")
    m.finish_run("tier1", status=mx.STATUS_OK, pushed=5, failed=2)

    text = m.render()

    # required series with exact label ordering (sorted: status before tier)
    assert 'competitor_crawler_run_total{status="ok",tier="tier1"} 1' in text
    assert 'competitor_crawler_push_sent_total{tier="tier1"} 5' in text
    assert 'competitor_crawler_push_failed_total{tier="tier1"} 2' in text
    assert 'competitor_crawler_run_active{tier="tier1"} 0' in text

    # HELP/TYPE present for every family
    assert "# TYPE competitor_crawler_run_total counter" in text
    assert "# TYPE competitor_crawler_push_sent_total counter" in text
    assert "# TYPE competitor_crawler_push_failed_total counter" in text
    assert "# TYPE competitor_crawler_run_active gauge" in text
    # exposition ends with a trailing newline
    assert text.endswith("\n")


def test_run_active_gauge_toggles_around_a_run():
    m = mx.CrawlerMetrics()
    m.start_run("tier1")
    assert m.value(mx.RUN_ACTIVE, tier="tier1") == 1
    m.finish_run("tier1", status=mx.STATUS_OK)
    assert m.value(mx.RUN_ACTIVE, tier="tier1") == 0


def test_ensure_tier_makes_zero_series_visible_before_completion():
    m = mx.CrawlerMetrics()
    m.ensure_tier("tier1")
    text = m.render()
    # push counters and the active gauge are present at 0 before the run finishes
    assert 'competitor_crawler_push_sent_total{tier="tier1"} 0' in text
    assert 'competitor_crawler_push_failed_total{tier="tier1"} 0' in text
    assert 'competitor_crawler_run_active{tier="tier1"} 0' in text
    # but no run_total sample yet (no terminal status observed)
    assert "competitor_crawler_run_total{" not in text


def test_counters_accumulate_across_runs():
    m = mx.CrawlerMetrics()
    m.finish_run("tier1", status=mx.STATUS_OK, pushed=3, failed=1)
    m.finish_run("tier1", status=mx.STATUS_OK, pushed=2, failed=0)
    assert m.value(mx.PUSH_SENT_TOTAL, tier="tier1") == 5
    assert m.value(mx.PUSH_FAILED_TOTAL, tier="tier1") == 1
    assert m.value(mx.RUN_TOTAL, tier="tier1", status=mx.STATUS_OK) == 2


def test_status_labels_distinguish_outcomes():
    m = mx.CrawlerMetrics()
    m.finish_run("tier1", status=mx.STATUS_OK)
    m.finish_run("tier2", status=mx.STATUS_ERROR)
    m.finish_run("tier3", status=mx.STATUS_SKIPPED)
    assert m.value(mx.RUN_TOTAL, tier="tier1", status="ok") == 1
    assert m.value(mx.RUN_TOTAL, tier="tier2", status="error") == 1
    assert m.value(mx.RUN_TOTAL, tier="tier3", status="skipped") == 1


def test_negative_increment_is_rejected():
    m = mx.CrawlerMetrics()
    try:
        m._inc(mx.PUSH_SENT_TOTAL, -1, {"tier": "tier1"})
    except ValueError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError on negative counter increment")


# --- label escaping -------------------------------------------------------

def test_newline_in_label_value_is_escaped():
    m = mx.CrawlerMetrics()
    m.finish_run("a\nb", status=mx.STATUS_OK)
    text = m.render()
    # a literal newline would corrupt the exposition line layout
    assert 'tier="a\\nb"' in text


def test_quote_and_backslash_in_label_value_are_escaped():
    m = mx.CrawlerMetrics()
    m.finish_run('q"\\x', status=mx.STATUS_OK)
    text = m.render()
    # backslash escaped first, then the quote
    assert 'tier="q\\"\\\\x"' in text


# --- HTTP exposition (loopback only) -------------------------------------

def test_http_endpoint_serves_metrics_over_loopback():
    m = mx.CrawlerMetrics()
    m.ensure_tier("tier1")
    m.finish_run("tier1", status=mx.STATUS_OK, pushed=1, failed=0)
    server = mx.MetricsServer(m, host="127.0.0.1", port=0)
    server.start()
    try:
        port = server.port
        assert port > 0
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics", timeout=5
        ) as resp:
            assert resp.status == 200
            ctype = resp.headers.get("Content-Type")
            body = resp.read().decode("utf-8")
        assert "text/plain" in ctype
        assert "version=0.0.4" in ctype
        assert "competitor_crawler_run_total" in body
        assert 'competitor_crawler_push_sent_total{tier="tier1"} 1' in body
    finally:
        server.stop()


def test_http_endpoint_returns_404_for_other_paths():
    m = mx.CrawlerMetrics()
    server = mx.MetricsServer(m, host="127.0.0.1", port=0)
    server.start()
    try:
        port = server.port
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/nope", timeout=5
            )
        except urllib.error.HTTPError as e:
            assert e.code == 404
        else:  # pragma: no cover - defensive
            raise AssertionError("expected HTTP 404 for unknown path")
    finally:
        server.stop()


def test_http_endpoint_reflects_live_updates_after_start():
    m = mx.CrawlerMetrics()
    m.ensure_tier("tier1")
    server = mx.MetricsServer(m, host="127.0.0.1", port=0)
    server.start()
    try:
        port = server.port
        # mutate after the server is already serving (concurrent scrape path)
        m.start_run("tier1")
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics", timeout=5
        ) as resp:
            body = resp.read().decode("utf-8")
        assert 'competitor_crawler_run_active{tier="tier1"} 1' in body
    finally:
        server.stop()


def test_ephemeral_port_is_reported():
    m = mx.CrawlerMetrics()
    server = mx.MetricsServer(m, host="127.0.0.1", port=0)
    try:
        # port resolved from the bound socket even before start()
        assert isinstance(server.port, int)
        assert server.port > 0
    finally:
        server.stop()
