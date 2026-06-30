"""B1 tests for the explicit target-file prober runner."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.prober import run_once
from src.prober.transport import ProbeResponse


class FakeTransport:
    def __init__(self, add_resp, *, cleanup_resp=None) -> None:
        self._add_resp = add_resp
        self._cleanup_resp = cleanup_resp or ProbeResponse(status_code=200)
        self.calls = []

    def request(self, method, url, json=None):
        self.calls.append((method, url, json))
        if "cacc_4_50_2_" in url:
            return self._cleanup_resp
        return self._add_resp

    def close(self):
        self.closed = True


def _targets_file(tmp_path: Path, targets: list[dict]) -> Path:
    path = tmp_path / "targets.json"
    path.write_text(json.dumps({"targets": targets}), encoding="utf-8")
    return path


def _target(**overrides):
    values = {
        "domain": "airsoftquimera.com",
        "product_key": "competitor:airsoftquimera.com:15229",
        "url": (
            "https://www.airsoftquimera.com/"
            "cargador-midcap-para-m4-200bbs-tornado-p-4-50-15229/"
        ),
        "platform": "airsoftquimera",
    }
    values.update(overrides)
    return values


def test_load_targets_accepts_dict_payload(tmp_path):
    path = _targets_file(tmp_path, [_target()])

    targets = run_once.load_targets(path)

    assert len(targets) == 1
    assert targets[0].domain == "airsoftquimera.com"
    assert targets[0].platform == "airsoftquimera"


def test_load_targets_rejects_unapproved_domain(tmp_path):
    path = _targets_file(tmp_path, [_target(domain="example.com")])

    with pytest.raises(ValueError, match="not approved"):
        run_once.load_targets(path)


def test_run_success_without_history(tmp_path, monkeypatch):
    monkeypatch.delenv("HISTORY_ENABLED", raising=False)
    path = _targets_file(tmp_path, [_target()])
    transport = FakeTransport(
        ProbeResponse(
            status_code=200,
            text="Actualmente tenemos en stock 4",
        )
    )

    rc = run_once.run(
        ["--targets", str(path), "--run-id", "run-1"],
        transport_factory=lambda _target: transport,
    )

    assert rc == run_once.EXIT_OK
    assert transport.calls[0][1].endswith("/cacc_4_50_1_15229_10_0/")


def test_write_history_missing_env_fails_before_probe(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_ENABLED", "true")
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("PGDATABASE", raising=False)
    monkeypatch.delenv("PGUSER", raising=False)
    monkeypatch.delenv("PGPASSWORD", raising=False)
    path = _targets_file(tmp_path, [_target()])
    calls = []

    rc = run_once.run(
        ["--targets", str(path), "--run-id", "run-1", "--write-history"],
        transport_factory=lambda target: calls.append(target),
    )

    assert rc == run_once.EXIT_USAGE_ERROR
    assert calls == []


def test_runner_returns_runtime_error_on_blocked_result(tmp_path):
    path = _targets_file(tmp_path, [_target()])
    transport = FakeTransport(ProbeResponse(status_code=503))

    rc = run_once.run(
        ["--targets", str(path), "--run-id", "run-1"],
        transport_factory=lambda _target: transport,
    )

    assert rc == run_once.EXIT_RUNTIME_ERROR


def test_runner_writes_history_with_fake_connection(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_ENABLED", "true")
    monkeypatch.setenv("PGHOST", "postgres")
    monkeypatch.setenv("PGDATABASE", "competitor_intel")
    monkeypatch.setenv("PGUSER", "skirmshop")
    monkeypatch.setenv("PGPASSWORD", "test-secret")
    path = _targets_file(tmp_path, [_target()])
    transport = FakeTransport(
        ProbeResponse(
            status_code=200,
            text="Actualmente tenemos en stock 2",
        )
    )
    conn = _FakeConn()

    rc = run_once.run(
        ["--targets", str(path), "--run-id", "run-1", "--write-history"],
        transport_factory=lambda _target: transport,
        history_connect=lambda _config: conn,
    )

    assert rc == run_once.EXIT_OK
    assert conn.commits == 1
    assert len(conn.observations) == 1
    assert conn.observations[0][8] == 2
    assert conn.observations[0][10] == "cart_probe"


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0

    def execute(self, sql, params):
        if "competitor_intel_observation_key" in sql:
            self.rowcount = 1
            return
        if "price_stock_observation" in sql:
            self.conn.observations.append(params)
            self.rowcount = 1
            return
        raise AssertionError(sql)

    def close(self):
        self.conn.cursor_closed = True


class _FakeConn:
    def __init__(self):
        self.observations = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.cursor_closed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True
