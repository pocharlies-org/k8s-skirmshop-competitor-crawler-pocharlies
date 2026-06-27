import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import push_client


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.request = object()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected status {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._responses.pop(0)


def test_push_documents_sends_brain_api_key(monkeypatch):
    fake = _FakeAsyncClient([_FakeResponse()])
    monkeypatch.setenv("BRAIN_API_KEY", "test-secret")
    monkeypatch.delenv("REQUIRE_BRAIN_API_KEY", raising=False)
    monkeypatch.setattr(push_client, "BRAIN_URL", "http://brain")
    monkeypatch.setattr(push_client, "BRAIN_INSTANCE", "skirmshop")
    monkeypatch.setattr(push_client, "PUSH_BATCH_SIZE", 20)
    monkeypatch.setattr(push_client.httpx, "AsyncClient", lambda timeout: fake)

    sent, failed = asyncio.run(push_client.push_documents([{"id": "p1"}]))

    assert (sent, failed) == (1, 0)
    assert fake.calls[0]["headers"] == {"X-API-Key": "test-secret"}
    assert fake.calls[0]["json"]["adapter"] == "competitor"


def test_push_documents_fails_closed_when_key_required(monkeypatch):
    fake = _FakeAsyncClient([_FakeResponse()])
    monkeypatch.delenv("BRAIN_API_KEY", raising=False)
    monkeypatch.setenv("REQUIRE_BRAIN_API_KEY", "true")
    monkeypatch.setattr(push_client.httpx, "AsyncClient", lambda timeout: fake)

    with pytest.raises(push_client.BrainAuthError, match="BRAIN_API_KEY"):
        asyncio.run(push_client.push_documents([{"id": "p1"}]))

    assert fake.calls == []


def test_push_documents_preserves_batching_without_required_key(monkeypatch):
    fake = _FakeAsyncClient([_FakeResponse(), _FakeResponse()])
    monkeypatch.delenv("BRAIN_API_KEY", raising=False)
    monkeypatch.delenv("REQUIRE_BRAIN_API_KEY", raising=False)
    monkeypatch.setattr(push_client, "BRAIN_URL", "http://brain")
    monkeypatch.setattr(push_client, "BRAIN_INSTANCE", "skirmshop")
    monkeypatch.setattr(push_client, "PUSH_BATCH_SIZE", 1)
    monkeypatch.setattr(push_client.httpx, "AsyncClient", lambda timeout: fake)

    sent, failed = asyncio.run(push_client.push_documents([{"id": "p1"}, {"id": "p2"}]))

    assert (sent, failed) == (2, 0)
    assert len(fake.calls) == 2
    assert fake.calls[0]["headers"] == {}
    assert fake.calls[1]["json"]["documents"] == [{"id": "p2"}]
