# F7 Backend Report - Brain push-ingest auth

**Role:** rho-backend attempted, but Claude CLI timed out with no stdout.  
**Integration:** Codex PMO reviewed the resulting diff and added tests/report as an explicit limited exception.  
**Scope:** `src/push_client.py`, `tests/test_push_client.py`.  
**No production writes:** no `kubectl apply`, no Brain `push-ingest`, no deploy.

## RHO Checklist

### Directives
- [x] Limit exception to the F7 auth blocker. Evidence: touched code/test files are `src/push_client.py` and `tests/test_push_client.py`.
- [x] Do not expose secrets. Evidence: tests use `test-secret`; code logs only env var names, never values.
- [x] Do not alter k8s/prod in backend exception. Evidence: no `k8s/**` files touched.

### Acceptance Criteria
- [x] `push_documents` sends `X-API-Key` when `BRAIN_API_KEY` is configured. Evidence: `tests/test_push_client.py::test_push_documents_sends_brain_api_key`.
- [x] Runtime can fail closed when auth is mandatory. Evidence: `REQUIRE_BRAIN_API_KEY=true` raises `BrainAuthError` before any POST; `tests/test_push_client.py::test_push_documents_fails_closed_when_key_required`.
- [x] Existing unauthenticated/local behavior remains available when explicitly not required. Evidence: `tests/test_push_client.py::test_push_documents_preserves_batching_without_required_key`.
- [x] Retry/batch call shape is preserved. Evidence: batching test verifies two POST calls for `PUSH_BATCH_SIZE=1`; original retry loop remains structurally unchanged.

## Residual Risks
- F7 DevOps must set `BRAIN_API_KEY` through `competitor-crawler-secrets` and set `REQUIRE_BRAIN_API_KEY=true` in production manifests.
- This does not activate crawler/prober and does not validate live `push-ingest`; live writes require explicit F7 apply/smoke gate.
