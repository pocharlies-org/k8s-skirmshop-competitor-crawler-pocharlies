# Codex RSO Audit - F4c Endpoint-Scoped Fingerprint

**Auditor:** Codex RSO/PMO.
**Decision:** **F4c PASS for GET-only fingerprint/read-discovery; F4 full remains BLOCKED on live cart-probe calibration.**

## Acceptance Checklist
- [x] Researcher expanded candidates without repo edits. Evidence: `/tmp/f4c-candidate-targets.json`, `/tmp/f4c-fingerprint.json`, researcher report in session.
- [x] Architect approved endpoint-scoped antibot. Evidence: `rho-architect` report; fail-closed invariants for data endpoints.
- [x] Backend implemented within scope. Evidence: `scripts/fingerprint_domains.py`, `tests/test_fingerprint_domains.py`, `backend-fingerprint.report.md`.
- [x] Security independently reviewed. Evidence: `rho-security` PASS; no live cart authorized.
- [x] Verifier independently re-ran gates. Evidence: `rho-verifier` PASS.
- [x] Codex re-ran gates. Evidence: `pytest -q tests/test_fingerprint_domains.py` -> 20 passed; `pytest -q` -> 118 passed; `python3 -m compileall scripts src tests` -> exit 0; `git diff --check` clean.
- [x] Codex re-ran GET-only fingerprints to `/tmp`. Evidence: top30 now has 2 Woo endpoint-green candidates; expanded provisional list has 3 Shopify/Woo endpoint-green candidates.
- [blocked] Live sample-10 calibration. Blocker: no specific cart-write domain has been approved; fingerprint green is read-only endpoint green, not cart-write green.

## RSO Decision
Commit F4c code/tests/reports. Keep F4 full gate closed. Prepare, but do not execute, a cart-probe live approval gate.

## Do Not Misread
`tier=green` after F4c means the product data endpoint is readable by GET. It does not mean `/cart/add.js` or Woo cart POST is safe or approved.
