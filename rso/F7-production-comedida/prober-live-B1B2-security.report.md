# RHO Security Report - F7 Prober Live B1

Timestamp: 2026-06-30T02:32:57+02:00

## Scope
- [x] Review B1 code for anti-bot, domain, secrets and forbidden path controls. Evidence: direct file inspection + grep below.
- [x] No live competitor traffic in this security pass. Evidence: all tests use fakes/httpx `MockTransport`; no curl or prober Job was executed.

## Controls Verified
- [x] Approved domain only. Evidence: `src/prober/run_once.py` rejects domains other than `airsoftquimera.com`; `src/prober/http_transport.py` blocks off-domain URL hosts before HTTP.
- [x] No checkout/login/account/payment paths. Evidence: grep hits for those words are documentation comments/checklist only; executable adapter uses only `/cacc_4_50_1_...` and `/cacc_4_50_2_...`.
- [x] No CAPTCHA solving or bypass. Evidence: `captcha` is only a challenge marker; it maps to blocked/fail-closed behavior.
- [x] No raw body logging. Evidence: runner logs only domain, product_key, status, stock fields, cleanup, error/block reason; it never logs response body content.
- [x] Missing PG env fails before traffic when `--write-history` is requested. Evidence: `tests/test_prober_run_once.py::test_write_history_missing_env_fails_before_probe`.
- [x] Dirty cleanup fails closed. Evidence: `tests/test_prober_airsoftquimera.py::test_cleanup_failure_demotes_to_error_dirty`.

## Grep Evidence
Command:

```bash
rg -n "checkout|login|account|register|payment|captcha|raw html|response\\.text|print\\(|logger\\." src/prober tests/test_prober_*.py rso/F7-production-comedida/prober-live-B1B2-checklist.md
```

Findings:
- Checklist/docs mention forbidden paths as prohibitions.
- `src/prober/http_transport.py` contains `captcha` only as a challenge marker.
- `tests/test_prober_http_transport.py` uses `/captcha.php` only to verify challenge detection.
- `src/prober/run_once.py` `logger.*` calls log status metadata only, not response bodies or secrets.
- No `response.text` literal, `print(` calls, checkout/login/account/register/payment executable paths were introduced in B1.

## Residual Risks
- [blocked] B2 still needs runtime pin evidence.
- [blocked] B3 live smoke must re-run this security review against real logs before any PASS.

## Checklist
- [x] Domain guard verified.
- [x] Anti-bot fail-closed verified.
- [x] Secret/log hygiene verified.
- [x] No live traffic executed.
