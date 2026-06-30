"""Unit tests for the one-shot CronJob runner src.run_once — no real network.

``crawl_tier`` is monkeypatched with an in-memory fake that records the tiers it
was asked to run, so these tests exercise CLI parsing, tier selection, config
loading and process exit-code semantics without any HTTP/crawl side effects.
"""
import asyncio
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import metrics_exporter as mx
from src import run_once


def _write_config(tmp_path: Path, tiers: dict) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump({"tiers": tiers}))
    return cfg


def _install_fake_crawl_tier(monkeypatch, *, failed: int = 0):
    """Replace crawl_tier with a recorder. Returns the list of (name, stores)."""
    calls: list[tuple[str, list[dict]]] = []

    async def fake_crawl_tier(tier_name, stores):
        calls.append((tier_name, stores))
        return (len(stores), failed)

    monkeypatch.setattr(run_once, "crawl_tier", fake_crawl_tier)
    return calls


SAMPLE_TIERS = {
    "tier1": {"schedule": "0 2 * * *", "stores": [{"domain": "a.com"}]},
    "tier2": {"schedule": "0 3 * * *", "stores": [{"domain": "b.com"},
                                                  {"domain": "c.com"}]},
    "tier3": {"schedule": "0 4 * * *", "stores": [{"domain": "d.com"}]},
}


def test_run_single_tier(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier1", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert [name for name, _ in calls] == ["tier1"]


def test_run_multiple_tier_flags_in_order(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier2", "--tier", "tier1", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    # runs exactly the requested tiers, in the order given on the CLI
    assert [name for name, _ in calls] == ["tier2", "tier1"]


def test_run_all_runs_every_tier_in_declaration_order(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert [name for name, _ in calls] == ["tier1", "tier2", "tier3"]


def test_domain_filter_runs_only_matching_store(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier2", "--domain", "b.com",
                       "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert calls == [("tier2", [{"domain": "b.com"}])]


def test_domain_filter_accepts_url_or_www_alias(monkeypatch, tmp_path):
    tiers = {
        "tier2": {
            "stores": [
                {"domain": "powair6.com",
                 "url": "https://www.powair6.com/en/"},
                {"domain": "begadi.com", "url": "https://www.begadi.com/"},
            ],
        }
    }
    cfg = _write_config(tmp_path, tiers)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier2", "--domain",
                       "https://www.powair6.com/en/", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert calls == [("tier2", [tiers["tier2"]["stores"][0]])]


def test_domain_filter_all_runs_configured_tier_only(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--domain", "c.com", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert calls == [("tier2", [{"domain": "c.com"}])]


def test_unknown_domain_exits_usage_error(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier2", "--domain", "missing.example",
                       "--config", str(cfg)])

    assert rc == run_once.EXIT_USAGE_ERROR
    assert calls == []


def test_run_label_overrides_single_filtered_window(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier2", "--domain", "b.com",
                       "--run-label", "tier2-b", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert calls == [("tier2-b", [{"domain": "b.com"}])]


def test_run_label_requires_one_selected_window(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--run-label", "everything",
                       "--config", str(cfg)])

    assert rc == run_once.EXIT_USAGE_ERROR
    assert calls == []


def test_run_label_rejects_shell_unsafe_characters(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "tier1", "--run-label", "tier1/../../x",
                       "--config", str(cfg)])

    assert rc == run_once.EXIT_USAGE_ERROR
    assert calls == []


def test_unknown_tier_exits_nonzero_and_does_not_crawl(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "does-not-exist", "--config", str(cfg)])

    assert rc == run_once.EXIT_USAGE_ERROR
    assert rc != 0
    assert calls == []  # never attempted any crawl


def test_missing_config_exits_usage_error(monkeypatch, tmp_path):
    missing = tmp_path / "nope.yaml"
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--config", str(missing)])

    assert rc == run_once.EXIT_USAGE_ERROR
    assert calls == []


def test_empty_tiers_config_exits_usage_error(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--config", str(cfg)])

    assert rc == run_once.EXIT_USAGE_ERROR
    assert calls == []


def test_tier_without_stores_is_skipped(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {"empty": {"schedule": "0 2 * * *", "stores": []}})
    calls = _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--tier", "empty", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert calls == []  # no stores -> crawl_tier not invoked


def test_push_failures_ignored_by_default(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch, failed=5)

    rc = run_once.run(["--all", "--config", str(cfg)])

    # default: partial push failures do not fail the job
    assert rc == run_once.EXIT_OK


def test_fail_on_push_errors_exits_nonzero(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch, failed=5)

    rc = run_once.run(["--all", "--fail-on-push-errors", "--config", str(cfg)])

    assert rc == run_once.EXIT_RUNTIME_ERROR
    assert rc != 0


def test_fail_on_push_errors_clean_run_exits_zero(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch, failed=0)

    rc = run_once.run(["--all", "--fail-on-push-errors", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK


def test_unhandled_crawl_error_exits_runtime_error(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)

    async def boom(tier_name, stores):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(run_once, "crawl_tier", boom)

    rc = run_once.run(["--tier", "tier1", "--config", str(cfg)])

    assert rc == run_once.EXIT_RUNTIME_ERROR


def test_requires_a_selection_flag(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)

    # neither --tier nor --all -> argparse errors out with exit code 2
    with pytest.raises(SystemExit) as exc:
        run_once.run(["--config", str(cfg)])
    assert exc.value.code == run_once.EXIT_USAGE_ERROR


def test_tier_and_all_are_mutually_exclusive(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        run_once.run(["--all", "--tier", "tier1", "--config", str(cfg)])
    assert exc.value.code == run_once.EXIT_USAGE_ERROR


def test_main_raises_systemexit_with_run_code(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)

    monkeypatch.setattr(sys, "argv", ["run_once", "--tier", "tier1",
                                      "--config", str(cfg)])
    with pytest.raises(SystemExit) as exc:
        run_once.main()
    assert exc.value.code == run_once.EXIT_OK


# --- optional metrics endpoint --------------------------------------------

class _FakeServer:
    """Records lifecycle without opening a real socket."""

    instances: list["_FakeServer"] = []

    def __init__(self, metrics, *, host="0.0.0.0", port=0):
        self.metrics = metrics
        self.host = host
        self.port = port or 54321
        self.started = False
        self.stopped = False
        _FakeServer.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@pytest.fixture
def fake_metrics_server(monkeypatch):
    _FakeServer.instances.clear()
    monkeypatch.setattr(run_once, "MetricsServer", _FakeServer)
    # never let a stray env enable/disable metrics under us
    monkeypatch.delenv("METRICS_PORT", raising=False)
    monkeypatch.delenv("METRICS_LINGER_SECONDS", raising=False)
    return _FakeServer


def test_metrics_disabled_by_default(monkeypatch, tmp_path, fake_metrics_server):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    # no port -> server never constructed
    assert fake_metrics_server.instances == []


def test_metrics_server_started_and_stopped_when_port_given(
    monkeypatch, tmp_path, fake_metrics_server
):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)

    rc = run_once.run(["--all", "--metrics-port", "0", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert len(fake_metrics_server.instances) == 1
    server = fake_metrics_server.instances[0]
    assert server.started is True
    assert server.stopped is True
    # the run recorded one ok run per tier into the registry the server holds
    assert server.metrics.value(mx.RUN_TOTAL, tier="tier1", status="ok") == 1
    assert server.metrics.value(mx.RUN_TOTAL, tier="tier2", status="ok") == 1
    assert server.metrics.value(mx.RUN_ACTIVE, tier="tier1") == 0


def test_metrics_records_push_totals(
    monkeypatch, tmp_path, fake_metrics_server
):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    # fake returns (len(stores), failed=2) per tier
    _install_fake_crawl_tier(monkeypatch, failed=2)

    rc = run_once.run(["--tier", "tier2", "--metrics-port", "0",
                       "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    server = fake_metrics_server.instances[0]
    # tier2 has 2 stores -> pushed == 2, failed == 2
    assert server.metrics.value(mx.RUN_TOTAL, tier="tier2", status="error") == 1
    assert server.metrics.value(mx.PUSH_SENT_TOTAL, tier="tier2") == 2
    assert server.metrics.value(mx.PUSH_FAILED_TOTAL, tier="tier2") == 2


def test_metrics_enabled_via_env(monkeypatch, tmp_path, fake_metrics_server):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)
    monkeypatch.setenv("METRICS_PORT", "0")

    rc = run_once.run(["--all", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert len(fake_metrics_server.instances) == 1


def test_metrics_linger_sleeps_then_stops(
    monkeypatch, tmp_path, fake_metrics_server
):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)
    sleeps: list[int] = []
    monkeypatch.setattr(run_once.time, "sleep", lambda s: sleeps.append(s))

    rc = run_once.run(["--all", "--metrics-port", "0",
                       "--metrics-linger-seconds", "7", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert sleeps == [7]
    assert fake_metrics_server.instances[0].stopped is True


def test_metrics_no_linger_by_default_does_not_sleep(
    monkeypatch, tmp_path, fake_metrics_server
):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)
    sleeps: list[int] = []
    monkeypatch.setattr(run_once.time, "sleep", lambda s: sleeps.append(s))

    rc = run_once.run(["--all", "--metrics-port", "0", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert sleeps == []  # default linger 0 -> no sleep


def test_metrics_linger_via_env(monkeypatch, tmp_path, fake_metrics_server):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)
    monkeypatch.setenv("METRICS_LINGER_SECONDS", "3")
    sleeps: list[int] = []
    monkeypatch.setattr(run_once.time, "sleep", lambda s: sleeps.append(s))

    rc = run_once.run(["--all", "--metrics-port", "0", "--config", str(cfg)])

    assert rc == run_once.EXIT_OK
    assert sleeps == [3]


def test_metrics_bind_failure_does_not_fail_the_job(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch)
    monkeypatch.delenv("METRICS_PORT", raising=False)

    class _Boom:
        def __init__(self, *a, **k):
            raise OSError("address already in use")

    monkeypatch.setattr(run_once, "MetricsServer", _Boom)

    rc = run_once.run(["--all", "--metrics-port", "0", "--config", str(cfg)])

    # observability failure must never change the job outcome
    assert rc == run_once.EXIT_OK


def test_metrics_does_not_change_exit_code_on_push_errors(
    monkeypatch, tmp_path, fake_metrics_server
):
    cfg = _write_config(tmp_path, SAMPLE_TIERS)
    _install_fake_crawl_tier(monkeypatch, failed=5)

    rc = run_once.run(["--all", "--metrics-port", "0",
                       "--fail-on-push-errors", "--config", str(cfg)])

    # exit-code semantics unchanged by the metrics endpoint
    assert rc == run_once.EXIT_RUNTIME_ERROR


# --- run_selected metric recording (no server) ----------------------------

def test_run_selected_records_error_status_when_tier_returns_failures():
    m = mx.CrawlerMetrics()

    async def fake(tier_name, stores):
        return (len(stores), 1)

    import src.run_once as ro
    orig = ro.crawl_tier
    ro.crawl_tier = fake
    try:
        selected = [("tier1", {"stores": [{"domain": "a"}, {"domain": "b"}]})]
        pushed, failed = asyncio.run(ro.run_selected(selected, m))
    finally:
        ro.crawl_tier = orig

    assert (pushed, failed) == (2, 1)
    assert m.value(mx.RUN_TOTAL, tier="tier1", status="error") == 1
    assert m.value(mx.PUSH_SENT_TOTAL, tier="tier1") == 2
    assert m.value(mx.PUSH_FAILED_TOTAL, tier="tier1") == 1
    assert m.value(mx.RUN_ACTIVE, tier="tier1") == 0


def test_run_selected_records_error_status_and_reraises(monkeypatch):
    m = mx.CrawlerMetrics()

    async def boom(tier_name, stores):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(run_once, "crawl_tier", boom)

    selected = [("tier1", {"stores": [{"domain": "a"}]})]
    with pytest.raises(RuntimeError):
        asyncio.run(run_once.run_selected(selected, m))

    # error is recorded with the gauge reset before the exception propagates
    assert m.value(mx.RUN_TOTAL, tier="tier1", status="error") == 1
    assert m.value(mx.RUN_ACTIVE, tier="tier1") == 0


def test_run_selected_records_skipped_for_tier_without_stores():
    m = mx.CrawlerMetrics()
    selected = [("empty", {"stores": []})]

    pushed, failed = asyncio.run(run_once.run_selected(selected, m))

    assert (pushed, failed) == (0, 0)
    assert m.value(mx.RUN_TOTAL, tier="empty", status="skipped") == 1
    assert m.value(mx.RUN_ACTIVE, tier="empty") == 0


# --- resolver helpers ------------------------------------------------------

def test_resolve_metrics_port_disabled_when_unset(monkeypatch):
    monkeypatch.delenv("METRICS_PORT", raising=False)
    args = run_once.parse_args(["--all"])
    assert run_once._resolve_metrics_port(args) is None


def test_resolve_metrics_port_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("METRICS_PORT", "1111")
    args = run_once.parse_args(["--all", "--metrics-port", "2222"])
    assert run_once._resolve_metrics_port(args) == 2222


def test_resolve_metrics_port_from_env(monkeypatch):
    monkeypatch.setenv("METRICS_PORT", "9090")
    args = run_once.parse_args(["--all"])
    assert run_once._resolve_metrics_port(args) == 9090


def test_resolve_metrics_port_invalid_env_disables(monkeypatch):
    monkeypatch.setenv("METRICS_PORT", "not-a-port")
    args = run_once.parse_args(["--all"])
    assert run_once._resolve_metrics_port(args) is None


def test_resolve_metrics_port_out_of_range_disables(monkeypatch):
    monkeypatch.delenv("METRICS_PORT", raising=False)
    args = run_once.parse_args(["--all", "--metrics-port", "70000"])
    assert run_once._resolve_metrics_port(args) is None


def test_resolve_linger_seconds_default_zero(monkeypatch):
    monkeypatch.delenv("METRICS_LINGER_SECONDS", raising=False)
    args = run_once.parse_args(["--all"])
    assert run_once._resolve_linger_seconds(args) == 0


def test_resolve_linger_seconds_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("METRICS_LINGER_SECONDS", "5")
    args = run_once.parse_args(["--all", "--metrics-linger-seconds", "11"])
    assert run_once._resolve_linger_seconds(args) == 11


def test_resolve_linger_seconds_negative_clamped_to_zero(monkeypatch):
    monkeypatch.delenv("METRICS_LINGER_SECONDS", raising=False)
    args = run_once.parse_args(["--all", "--metrics-linger-seconds", "-4"])
    assert run_once._resolve_linger_seconds(args) == 0


def test_resolve_linger_seconds_invalid_env_uses_zero(monkeypatch):
    monkeypatch.setenv("METRICS_LINGER_SECONDS", "soon")
    args = run_once.parse_args(["--all"])
    assert run_once._resolve_linger_seconds(args) == 0
