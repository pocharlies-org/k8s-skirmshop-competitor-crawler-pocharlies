from datetime import datetime, timezone

import pytest

from src import history_runtime as hr


T0 = datetime(2026, 6, 27, 18, 0, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0

    def execute(self, sql, params):
        self.conn.operations.append((sql, params))
        if "competitor_intel_observation_key" in sql:
            self.rowcount = 1
        elif "price_stock_observation" in sql:
            self.conn.observations.append(params)
            self.rowcount = 1
        else:
            raise AssertionError(sql)

    def close(self):
        self.conn.cursor_closed = True


class FakeConn:
    def __init__(self):
        self.operations = []
        self.observations = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.cursor_closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def env(**overrides):
    base = {
        "HISTORY_ENABLED": "true",
        "PGHOST": "postgres-shared-rw.databases.svc.cluster.local",
        "PGPORT": "5432",
        "PGDATABASE": "competitor_intel",
        "PGUSER": "skirmshop",
        "PGPASSWORD": "secret",
    }
    base.update(overrides)
    return base


def test_disabled_history_is_noop_and_does_not_connect():
    called = False

    def connect(_config):
        nonlocal called
        called = True
        raise AssertionError("must not connect")

    result = hr.write_docs_history(
        [{"source_id": "competitor:a.com:p1"}],
        domain="a.com",
        run_id="run-1",
        observed_at=T0,
        config=hr.load_history_config({"HISTORY_ENABLED": "false"}),
        connect=connect,
    )

    assert result == hr.HistoryWriteResult(enabled=False)
    assert called is False


def test_enabled_history_writes_mapped_observation():
    conn = FakeConn()
    docs = [{
        "source_id": "competitor:a.com:https://a.com/p1",
        "metadata": {
            "domain": "a.com",
            "price": 12.34,
            "availability": "https://schema.org/InStock",
            "is_promotion": True,
        },
    }]

    result = hr.write_docs_history(
        docs,
        domain="a.com",
        run_id="run-1",
        observed_at=T0,
        config=hr.load_history_config(env()),
        connect=lambda _config: conn,
    )

    assert result == hr.HistoryWriteResult(enabled=True, inserted=1, skipped=0)
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert conn.closed is True
    observation = conn.observations[0]
    assert observation[0] == "a.com|competitor:a.com:https://a.com/p1|run-1"
    assert observation[5] == 12.34
    assert observation[9] == "in_stock"
    assert observation[10] == "visible"
    assert observation[11] is True


def test_enabled_history_missing_env_fails_closed_without_secret_values():
    with pytest.raises(hr.HistoryConfigError) as exc:
        hr.load_history_config(env(PGPASSWORD=""))

    assert "PGPASSWORD" in str(exc.value)
    assert "secret" not in str(exc.value)


def test_invalid_port_fails_closed():
    with pytest.raises(hr.HistoryConfigError, match="PGPORT"):
        hr.load_history_config(env(PGPORT="not-a-port"))


def test_observations_from_docs_requires_source_id():
    with pytest.raises(ValueError, match="source_id"):
        hr.observations_from_docs(
            [{"metadata": {"domain": "a.com"}}],
            domain="a.com",
            run_id="run-1",
            observed_at=T0,
        )
