# Fingerprint Report - F0 Autopilot

- [x] Generated data/competitors/fingerprint.json for 30 unique target domains. Evidence: validation assertions passed.
- [x] Required fields present for every fingerprint. Evidence: validation assertions passed.
- [x] Tier counts: {'yellow': 9, 'red': 16, 'green': 5}
- [x] silverback-airsoft.com: tier=red, antibot=captcha, http_status=200
- [x] Zero cart/write/POST to competitors. Evidence: scripts/fingerprint_domains.py uses urllib Request method GET only; probes robots, root, products.json, Woo Store API.
