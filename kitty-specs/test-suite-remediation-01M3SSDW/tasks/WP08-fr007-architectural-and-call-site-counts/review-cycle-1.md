---
affected_files: []
cycle_number: 1
mission_slug: test-suite-remediation-01M3SSDW
reproduction_command:
reviewed_at: '2026-09-30T22:25:54Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review — cycle 1 — CHANGES REQUESTED (reviewer-renata)

One blocking item. Everything else re-verified and approvable as-is.

## Blocking

**Issue 1 — F9: the retired guard's implicit property is left uncovered; the docstring still carries the counts.**

The WP objective is explicit: "F9, RETIRE: the prose-denominator test ... **with the counts stripped from the docstring**." The keyword-contract check (what did the exact value implicitly guard?) gives one answer for F9: `test_recorded_denominator_matches_docstring_claim` guarded *docstring prose vs. the constants*. Retiring it is correct only if the prose no longer carries numbers — otherwise the prose becomes silently stale-able with no guard at all, which is the exact defect the retired test existed to prevent.

Commit `4e2a88a996` stripped only the two bullet lines. Three numeric references remain in the module docstring of `tests/architectural/test_no_absolute_event_timestamp_mixture.py` (byte-identical to the base):

- `:107` — "Every one of these **14** is an already-audited case"
- `:114` — "The newest pair (**14th**, #3938's ``user``-actor resume regression)"
- `:121` — "a future maintainer who actually fixes one of the **14** shrinks the recorded set"

The evidence record for F9 also states "docstring numbers replaced with named-constant prose, no counts", which is not accurate for the tree as committed.

**Fix (≈3 lines, same file, format-excluded):** reword the three sentences to be count-free, e.g. "Every one of these recorded pairs is an already-audited case ...", "The most recently recorded pair (#3938's ``user``-actor resume regression) ...", "... who actually fixes one of the recorded pairs shrinks the recorded set ...". Then verify with `grep -nE '\b(14|14th|2 files)\b' tests/architectural/test_no_absolute_event_timestamp_mixture.py` → no docstring hits, re-run the file (expect 9 passed), `uv run --frozen ruff check` on it, and correct the F9 evidence line.

## Non-blocking (record or ignore; no change required for approval)

- **F11 naming drift:** `test_remediation_state_floor_is_pinned`, `test_producer_floor_is_pinned`, `test_exemption_set_size_is_pinned` now assert `>=` floors; the `_is_pinned` names contradict the new "floor, not a pin" comments. An optional rename to `*_meets_floor` would align names with behavior.
- **F11 walker scope (pre-existing, not a regression):** the walker visits only top-level `ast.FunctionDef` and bare-`Name` `FreshnessSubState(...)` calls. A construction in an `async def`, a class method, at module level, or via attribute access (`mod.FreshnessSubState(...)`) would be unvisited rather than failing closed. The fail-closed raise covers only an unreadable `state=`. No such shape exists in `computer.py` today; consider a tracer entry.
- **F3/F6 accepted residual:** the `>= 1` floors no longer detect *one of N* call sites becoming invisible to the AST counter (e.g. aliased), only total vanishing. This is the WP-prescribed disposition; noted for the record.

## Re-verified (reviewer re-runs, all plants reverted, `git diff --stat` empty after each)

- Named files: 87 passed (`-n0`). `ruff check` clean on all 6; `ruff format --check` clean on the 3 non-excluded (whole-dir check of the four parent dirs: 262 formatted, exclusions honored); `ruff check --select C901` clean.
- F11 split-site (`computer.py:525` `_REMEDIATE_UPGRADE_YES` → `None`, floor 7→6, `_CASES` row 525 deleted): `test_every_construction_site_is_partitioned` RED at line 522; floors/exemption/case-table 4 GREEN — the partition alone carries it.
- F11 fail-closed (`state=` via a named constant): RED with "no readable state= string literal".
- F11 disjointness (real emitting pair `(_synthesized_drg_missing_graph_state, missing)` added to both `_EXEMPT_STATES` and `expected_exempt`, `_CASES` 723 dropped): disjointness RED, everything else GREEN.
- F11 swap (exempt `(_compute_synced_bundle, stale)` swapped out in both sets): partition RED at line 625.
- F12a (stub `_check_sync_readiness`'s `tracker_egress_verdict(` call): set-equality RED, symmetric difference `['_check_sync_readiness']`.
- F12b: `EXPECTED_CALL_EXPRESSION_COUNT = 5` unchanged, KEEP reason recorded in the comment — justified as an audited egress census.
- F3 vacuity (alias all 29 `_materialize_decision(` call sites): floor RED.
- F8 violation (undocumented enum member): `:31` and `:48` both RED.
