# RHO Backend Report - F7 Prober Live B1

Timestamp: 2026-06-30T02:32:57+02:00

## Scope
- [x] Implement AirsoftQuimera-only adapter. Evidence: `src/prober/airsoftquimera.py`; `tests/test_prober_airsoftquimera.py`.
- [x] Implement bounded live HTTP transport. Evidence: `src/prober/http_transport.py`; `tests/test_prober_http_transport.py`.
- [x] Implement one-shot runner. Evidence: `src/prober/run_once.py`; `tests/test_prober_run_once.py`.
- [x] Dispatch via existing service facade. Evidence: `src/prober/service.py`; `tests/test_prober_service.py::test_airsoftquimera_target_dispatches_to_approved_adapter`.
- [x] Preserve F3 append-only history mapping. Evidence: runner uses `probe_result_to_observation` + `write_observations`; `tests/test_prober_run_once.py::test_runner_writes_history_with_fake_connection`.

## Evidence
- [x] Targeted prober suite PASS. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q tests/test_prober_airsoftquimera.py tests/test_prober_http_transport.py tests/test_prober_run_once.py tests/test_prober_service.py tests/test_prober_contract.py tests/test_prober_generic.py tests/test_prober_shopify.py tests/test_prober_woo.py` -> `59 passed in 0.12s`.
- [x] Full suite PASS. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `234 passed in 3.00s`.
- [x] Compile PASS. Evidence: `/tmp/crawler-f7-venv/bin/python -m compileall src tests` -> PASS.
- [x] Diff whitespace PASS. Evidence: `git diff --check` -> exit 0.
- [x] K8s render/server dry-run still PASS before B2 pin. Evidence: `kubectl kustomize k8s >/tmp/f7-b1b2-kustomize.yaml && kubectl apply --dry-run=server -k k8s` -> PASS.

## Implementation Notes
- The adapter probes only the F4-evidenced paths:
  - add `/cacc_4_50_1_<product_id>_<qty>_0/`
  - remove `/cacc_4_50_2_<product_id>_0_0/`
- Exact stock is accepted only from the site's `Actualmente tenemos en stock N` text.
- A successful add at the B1 ceiling is cleaned and recorded as `stock_qty=None` (in stock, exact ceiling not proven).
- `403`, `429`, `503`, and challenge/captcha indicators trip the domain cooldown.

## Residual Risks
- [blocked] No live HTTP smoke was run in B1; this is intentional until B3.
- [blocked] B2 release/pin is still pending.

## Checklist
- [x] Adapter implemented and tested.
- [x] Transport implemented and tested.
- [x] Runner implemented and tested.
- [x] History mapping path tested.
- [x] Full local suite passed.
