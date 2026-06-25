# Backend Report — robots.txt `Crawl-delay` group-aware parsing (F4)

- **Role:** rho-backend implementer (delegated by Codex RSO).
- **Branch:** `codex/competitor-crawler-F4-cart-probe`
- **HEAD at start/end:** `4b49ebd` (working tree, no commit by this role).
- **Timestamp:** 2026-06-25T03:34:03+02:00

## Scope
Fix `scripts/fingerprint_domains.py::_crawl_delay` so the emitted
`robots_crawl_delay` reflects the `Crawl-delay` of the group that applies to
`User-agent: *`, not the first `Crawl-delay` of any named bot. Add offline tests.
No other files touched; `data/competitors/fingerprint.json` NOT regenerated.

## Root cause
The previous implementation was line-oriented and group-blind:

```python
for line in robots_body.splitlines():
    if line.lower().strip().startswith("crawl-delay"):
        ...
        return float(value.strip())
```

It returned the **first** `Crawl-delay` line anywhere in the file. Real
robots.txt files commonly declare aggressive throttles for SEO/scraper bots
*before* the wildcard group, e.g.:

```
User-agent: AhrefsBot
Crawl-delay: 10
User-agent: *
Crawl-delay: 3
```

The old code returned `10` (Ahrefs) instead of `3` (`*`), inflating our
generic-agent crawl budget with a delay that does not apply to us.

## Fix
Rewrote `_crawl_delay` as a group-aware parser following the robots.txt record
grouping model (RFC 9309 grouping + the de-facto `Crawl-delay` extension):

- A group opens with one or more **consecutive** `User-agent` lines; the first
  non-agent directive closes that run, and the next `User-agent` opens a new
  group (`collecting_agents` flag tracks the run; `current_agents` is the set in
  scope).
- Multiple `User-agent` lines share one group, so `User-agent: Googlebot` +
  `User-agent: *` + `Crawl-delay: 7` yields `7` (wildcard ∈ group).
- A `Crawl-delay` is honored **only** when `*` is in the current group's agent
  set. Named-bot delays (Ahrefs/MJ12/Pinterest/Semrush/…) are ignored.
- Returns the **first valid** wildcard delay; `None` when no wildcard group
  declares a valid one. A malformed wildcard delay is skipped and does **not**
  fall through to a later named-bot delay.
- Hardening: inline `#` comments stripped; lines without `:` ignored;
  value parsed with `float`, rejected unless `math.isfinite(...) and >= 0`.
- Added `import math` (stdlib) for the finiteness guard.

### GET-only invariant preserved
The change is pure string parsing of an already-fetched body. No new requests,
no method change. Static guard substrings re-verified by grep:
`urllib.request.Request(` count = 1, `urllib.request.urlopen(` count = 1,
`method="GET"` count = 1; no `POST`, no `data=`, no cart/checkout/login/account
paths introduced.

## Tests added (`tests/test_fingerprint_domains.py`, fully offline, no network)
| Test | Input shape | Expected |
|---|---|---|
| `test_crawl_delay_star_group_is_used` | `*` group w/ delay 5 | `5.0` |
| `test_crawl_delay_named_bot_only_is_ignored` | AhrefsBot delay only | `None` |
| `test_crawl_delay_multiple_named_bots_then_star` | Ahrefs/MJ12/Pinterest + `*`=3 | `3.0` |
| `test_crawl_delay_no_star_delay_returns_none` | named delay, `*` w/o delay | `None` |
| `test_crawl_delay_malformed_value_is_ignored` | `*` `Crawl-delay: soon` | `None` |
| `test_crawl_delay_shared_group_with_star_applies` | `Googlebot` + `*` then delay 7 | `7.0` |
| `test_crawl_delay_star_survives_surrounding_named_delays` | named/`*`/named | `2.0` |
| `test_crawl_delay_malformed_star_does_not_borrow_named_delay` | malformed `*`, then Ahrefs 10 | `None` |
| `test_crawl_delay_absent_returns_none` | `ROBOTS_OK` body + `""` | `None` |

Covers every required case: star crawl-delay; named bot ignored; multiple named
bots + star; no star delay; malformed delay; plus the multi-`User-agent` group
(before/after several `User-agent`) and the don't-borrow-named-delay edge.

## Checks run
- [x] `git diff --check` → clean (no output). Evidence: command returned empty.
- [x] Static GET-only grep guard → `STATIC_GUARD_CLEAN` (no forbidden
  substrings); `Request(`=1, `urlopen(`=1, `method="GET"`=1.
- [x] Manual execution trace of all 9 new tests against the new parser → all
  expected values match (documented in this report's table; see Audit trace).
- [blocked] `pytest -q tests/test_fingerprint_domains.py`, `pytest -q`,
  `python3 -m compileall ...` → this lane's permission classifier denies all
  python execution (`python3 -c "print(1)"` → "This command requires approval").
  Same env block recorded earlier in `CHECKLIST.md` (2026-06-25T03:19). **Codex
  RSO must re-run these three gates** to confirm green.

## Audit trace (manual, because pytest is env-blocked)
Each new test was traced line-by-line through the parser state machine
(`current_agents`, `collecting_agents`); all 9 produce the asserted value.
Existing tests are unaffected: they use `ROBOTS_OK` (no `Crawl-delay` → `None`)
and assert only schema/antibot, never a numeric crawl-delay, and
`robots_crawl_delay` remains a returned top-level key.

## Files touched
- `scripts/fingerprint_domains.py` (+`import math`; rewrote `_crawl_delay`).
- `tests/test_fingerprint_domains.py` (+9 offline `_crawl_delay` tests).
- `rso/F4-cart-probe/backend-crawl-delay.report.md` (this file).
- `rso/F4-cart-probe/CHECKLIST.md` (append-only status line).

## Residual risks
1. **Verification owed to RSO:** pytest/compileall not executed in-lane (env
   block). Logic trace + grep guards are the only in-lane evidence; numeric
   green depends on RSO re-run.
2. **`Crawl-delay` before any `User-agent`:** a delay declared with no preceding
   `User-agent` (no group) is ignored (returns `None` from that line). This
   matches the spec (directive without a group is not applied) and is the
   intended "reasonable" behavior, but differs from clients that treat a leading
   delay as global.
3. **Multiple wildcard groups:** first valid wildcard delay wins; a later
   wildcard group's delay is not preferred/merged. Acceptable for budget
   purposes and documented.
4. **Artifact not regenerated:** `data/competitors/fingerprint.json` keeps its
   current (possibly named-bot-inflated) `robots_crawl_delay` values until a
   GET-only refresh is run by RSO; out of scope for this task.

## Addendum — 2026-06-25T (Codex/verifier-requested coverage for invalid wildcard delays)

**Why:** Codex RSO / `rho-verifier` flagged a residual risk: the original test
matrix proved a *malformed* wildcard delay (`Crawl-delay: soon`) is skipped, but
did **not** cover the other two invalidity classes of the `isfinite(...) and
>= 0` guard — a **negative** wildcard delay and a **non-finite** one
(`inf`/`-inf`/`nan`). Each must (a) return `None` and (b) NOT borrow a delay from
a later named-bot group. This addendum closes that gap. **No production code was
changed** in this pass (`git diff --stat scripts/fingerprint_domains.py` shows
only the prior lane's `_crawl_delay` rewrite; this lane edited only the test
file, report, and checklist).

### Tests added (`tests/test_fingerprint_domains.py`, fully offline, no network/monkeypatch)
| Test | Input shape | Expected | Guard exercised |
|---|---|---|---|
| `test_crawl_delay_negative_star_returns_none` | `*` group, `Crawl-delay: -5` | `None` | `delay >= 0` rejects |
| `test_crawl_delay_negative_star_does_not_borrow_named_delay` | `*` `-5`, then `AhrefsBot: 10` | `None` | reject + no named borrow |
| `test_crawl_delay_non_finite_star_returns_none` (param `inf,-inf,nan,infinity,-infinity`) | `*` group, non-finite delay | `None` | `math.isfinite` rejects |
| `test_crawl_delay_non_finite_star_does_not_borrow_named_delay` (param `inf,-inf,nan,infinity`) | `*` non-finite, then `MJ12bot: 20` | `None` | reject + no named borrow |
| `test_crawl_delay_valid_star_after_invalid_in_same_group_is_accepted` | `*` `-5`/`nan`/`7` (same group) | `7.0` | documents existing accept-on-later-valid behavior |

The last test is the **optional** item: it asserts the *current* behavior (no
code change) that, once the wildcard group is in scope, an earlier invalid delay
line is skipped while a later valid `Crawl-delay` in the same group (no
intervening `User-agent`) is still honored, because `current_agents` keeps `*`
in scope until a new `User-agent` run resets it.

### Manual state-machine trace (in-lane evidence; pytest env-blocked)
- **negative `*` (`-5`)** → matches `*`, `float("-5")=-5.0`, `isfinite` True but
  `-5.0 >= 0` False → `continue` → loop ends → `None`. With a trailing
  `AhrefsBot: 10`, the named `User-agent` resets `current_agents={"ahrefsbot"}`,
  so `"*" not in current_agents` → its `10` is skipped → `None`. ✔
- **non-finite `*` (`inf`/`-inf`/`nan`/`infinity`/`-infinity`)** → each parses to
  a valid float (`inf`/`-inf`/`nan`), `math.isfinite(...)` False → `continue` →
  `None`. With a trailing `MJ12bot: 20`, named reset prevents borrow → `None`. ✔
- **valid-after-invalid same group (`-5`,`nan`,`7`)** → `-5` skipped (`>=0`),
  `nan` skipped (`isfinite`), `7` matches `*` (set still `{"*"}`, no intervening
  `User-agent`), `float("7")=7.0`, finite and `>=0` → returns `7.0`. ✔

### Checks run (this pass)
- [x] `git diff --check` → clean. Evidence: `GIT_DIFF_CHECK_CLEAN` (empty output).
- [x] New tests present. Evidence: `grep -n "def test_crawl_delay_negative\|...non_finite\|...valid_star_after_invalid"` → 7 defs at lines 545,551,565,572,585 + 2 `@parametrize`.
- [x] Production code untouched this pass. Evidence: `git status --short` shows
  `tests/test_fingerprint_domains.py`, `rso/F4-cart-probe/CHECKLIST.md`,
  `backend-crawl-delay.report.md` only (script change is the prior lane's, not
  re-modified here).
- [blocked] `pytest -q tests/test_fingerprint_domains.py`, `pytest -q`,
  `python3 -m compileall ...` → this lane's permission classifier denies all
  python execution (`python3 -c "print(1)"` → "This command requires approval"),
  identical to the 2026-06-25T03:34 block. **Codex RSO must re-run these three
  gates** to confirm green. This pass adds **5 new test functions** that expand
  via `@parametrize` to **+12 collected test cases** (negative 1; negative
  no-borrow 1; non-finite 5 params; non-finite no-borrow 4 params; valid-after
  1). Exact pytest totals are not asserted here because python execution is
  env-blocked in this lane; RSO confirms the numeric green on re-run.

## Codex RSO verification — 2026-06-25T03:45:25+02:00

Codex RSO re-ran the blocked gates from the shared repo checkout after the
invalid-value coverage addendum:

- [x] `pytest -q tests/test_fingerprint_domains.py` -> `41 passed in 0.11s`.
- [x] `pytest -q` -> `139 passed in 0.23s`.
- [x] `python3 -m compileall scripts src tests` -> exit 0.
- [x] `git diff --check` -> clean.
- [x] `data/competitors/fingerprint.json` remains untouched by this microfix
  (not present in `git status --short` or `git diff --name-only`).

Decision: **PASS for crawl-delay parser and coverage**. This does **not** close
the F4 live cart-probe gate; live sample-10 calibration remains blocked until an
explicit cart-write approval is given for a named target/domain and cleanup
scope.
