"""Unit tests for the one-shot CronJob runner src.run_once — no real network.

``crawl_tier`` is monkeypatched with an in-memory fake that records the tiers it
was asked to run, so these tests exercise CLI parsing, tier selection, config
loading and process exit-code semantics without any HTTP/crawl side effects.
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
