# IC-11 — Retire the hash-toll surfaces + docs (WP12 refresh-helper retirement + WP13)

Per tasks.md closeout step 1, this concern merges WP12's refresh-helper retirement (scratchpad
`wp12/WP12-evidence.md`, commit `407d57b0f3`) with WP13's `SymbolKey.source_module` retirement
(scratchpad `wp13_evidence_note.txt`, commit `6b60ef0637b9ea56b4bb1ab4abe760dc0eb4dbbe`), and
both WPs' full approval notes (`status.events.jsonl`,
`review_ref: auto-approval:WP12:20260930` and `auto-approval:WP13:20260930` — considerably
more itemized than the one-line `review-cycle-1.md` files).

## WP12 — retire `_refresh_dead_symbol_hashes.py` + its 17 tests (C-002)

```yaml
id: EV-IC11-00
item: "C-002 covering guard for retiring _refresh_dead_symbol_hashes.py + test_refresh_dead_symbol_hashes.py (17 tests); quickstart Break #20 / M2 at real-tree scale"
kind: RETIRE
planted_break:
  target: "src/specify_cli/dashboard/server.py"
  description: 'add "PlantedDead5346" to __all__ plus `PlantedDead5346 = 1` (a new dead __all__ symbol in an allowlisted module)'
  reverted: true
command: "pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported tests/architectural/test_p1_planted_regression.py::test_planted_dead_symbol_still_red_by_dead_symbol_gate -n0 -q"
covering_guard:
  node_id: "tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported"
  under_break: fail   # names "specify_cli.dashboard.server::PlantedDead5346" (new gate); old gate also fails, same name
results:
  old_form_under_break: "n/a -- the retired helper never guarded deadness; it only rewrote hash literals"
  p1_synthetic_plant_under_break: "pass -- test_planted_dead_symbol_still_red_by_dead_symbol_gate green: _compute_offenders path live"
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP12:20260930): "new dead PlantedDeadR5346 in
  sparse_checkout_remediation both RED, named" — an independent variant of this covering-guard
  proof (a different allowlisted module/symbol pair than the WP's own PlantedDead5346 in
  dashboard/server.py, same invariant). Tallied in evidence/README.md (same reproduction cited
  under `EV-IC10b-03` in `IC-10-dead-symbol-allowlist-rekey.md`; this is that record, duplicated
  here per the closeout split-concern instruction).
  Deleted: tests/architectural/_refresh_dead_symbol_hashes.py,
  tests/architectural/test_refresh_dead_symbol_hashes.py (17 tests),
  docs/development/reference/ci-gate-mechanics.md's refresh-tool section (moved to WP15),
  tests/architectural/README.md's mention (WP13). Retired-file refs: only each other
  (git grep refresh_dead_symbol). This is the same EV-IC10b-03 record cross-referenced from
  IC-10 (duplicated here per the data-model §4 split-concern instruction: IC-11 = WP12's
  refresh-helper retirement + WP13).
```

## WP13 — retire `SymbolKey.source_module` (the hash-toll field) and its 7 G1-G6 tests

```yaml
id: EV-IC11-01
item: "G1-G6 (SymbolKey.source_module field + its 7 unit tests)"
kind: RETIRE
planted_break:
  target: "scratch YAML (outside repo, tempfile) parsed by tests.architectural._dead_symbol_allowlist.load_allowlist"
  description: >
    planted `source_module: pkg.delta` on entries[1] of a minimal WP11-shaped doc (1
    category, 2 entries, empty widened section).
  reverted: true   # scratch tempfile only, never committed; repo state untouched by this proof
command: "uv run --frozen python <scratchpad>/wp13_c002_plant.py"
results:
  old_form_under_break: "n/a -- no pre-existing loader-shaped covering guard to compare against; the field being deleted was previously guarded only by the 7 SymbolKey-level unit tests (G1-G6), not by the loader"
  new_form_under_break: >
    RED (covering guard) -- raises AllowlistSchemaError: "<tmp>.yaml: entries[1]: [L5]
    unknown key(s) ['source_module']; allowed: ['category', 'issue', 'module', 'name', 'rationale']"
  clean_tree: "n/a (scratch tempfile only)"
counts:
  executed_before: 47   # pre-WP13: grep -c '^def test_' tests/unit/test_symbol_key.py
  executed_after: 40    # post-WP13: a drop of exactly 7, matching the 7 deleted G1-G6 tests
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP13:20260930): "C-002 re-run: scratch YAML
  from _minimal() + source_module on entries[0] -> AllowlistSchemaError [L5]" — exactly this
  record's planted break, reproduced independently. The reviewer also planted an additional
  variant not in the WP's own report: "also planted on widened_grandfathered_470.entries[0]
  -> [L5]" (the same `source_module` key rejected in the widened section, not just the
  `entries` section) — "clean doc loads" confirms both the main and the widened-section
  variant revert clean. Tallied in evidence/README.md. Also ran WP11's own M12 plant for this exact case:
  `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -k unknown`
  -> 5 passed, including test_m12_schema_plant_is_rejected[unknown-key-retired-provenance].
  Subject deletion: SymbolKey.source_module field + its docstring paragraph removed from
  tests/architectural/_symbol_key.py; all 7 G1-G6 tests deleted from tests/unit/test_symbol_key.py
  (test_source_module_is_non_comparing, _ignored_by_equality_content_tier,
  _ignored_by_equality_collision_tier, _ignored_by_hash_and_frozenset_membership,
  _does_not_escalate_content_tier, _excluded_from_as_tuple_content_and_collision_tier,
  _does_not_affect_body_hash_and_resolver_key_has_none). Scan for non-source_module
  assertions worth keeping found none: as_tuple() content/collision-tier shape is already
  covered elsewhere; no unique coverage lost.
```

```yaml
id: EV-IC11-02
item: "grep-gate output (F-01) confirming the field has no other reader"
kind: KEEP
command: 'rg -n "\.source_module\b|source_module=" src tests scripts'
results:
  before_this_wps_edits: "8 hits, ALL in tests/unit/test_symbol_key.py (lines 681,693,704,724,737,740,753,755) -- the owned file, now deleted"
  after_this_wps_edits: "0 hits"
  refresh_helper_import_check: "rg -n \"import .*_refresh_dead_symbol_hashes|from tests\\.architectural\\._refresh_dead_symbol_hashes\" tests scripts -> 0 hits before and after (WP12 already deleted the helper)"
reviewer_rerun: false
notes: >
  Informational-only non-usage hits before edits: test_dead_symbol_allowlist_loader.py:53
  (_FORBIDDEN_KEYS literal, WP11-owned, expected) and :211 (M12 plant, WP11-owned, expected);
  _symbol_key.py:98/:114 (the field's docstring + declaration, WP13-owned, now removed).
  git grep "as_tuple" -- tests: SymbolKey.as_tuple has no external caller; left in place (not
  in scope per plan IC-11), noted as a follow-up candidate, not actioned. git grep "SymbolKey("
  -- tests: no external constructor calls left behind by WP12; removing the trailing
  defaulted field breaks no positional construction.
```

```yaml
id: EV-IC11-03
item: "timing invariant green, == 400 retained verbatim"
kind: KEEP
command: "rg -n 'len\\(index\\) == 400' tests/unit/test_symbol_key.py"
results:
  hit_count: 1   # exactly 1 hit (the pinned assertion, unchanged)
  combined_run: "uv run --frozen pytest tests/unit/test_symbol_key.py tests/architectural/test_timing_coverage_invariant.py -n0 -q -> 111 passed"
reviewer_rerun: false
notes: "keep_reason (data-model §3): pinned verbatim by test_timing_coverage_invariant.py:338; not touched by this WP's field deletion."
```

## Full named-file Test Strategy run (WP13)

`uv run --frozen pytest tests/unit/test_symbol_key.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q` -> **204 passed in 98.84s**.

Re-run after the sanctioned YAML campsite trim (one-line rationale prose edit, triggering a
non-blocking `ACTIVE_WP_SCOPE_VIOLATION` guard warning on the safe-commit, which still
succeeded): `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_no_dead_symbols.py -n0 -q` -> **83 passed in 77.68s**.

## Quality gates / make test-fast

- `ruff check tests/architectural/_symbol_key.py tests/unit/test_symbol_key.py` -> All checks passed!
- `ruff format --check tests/unit/test_symbol_key.py` -> 1 file already formatted (`_symbol_key.py` is format-excluded).
- No `src/` files touched -> no mypy run required.
- Deleted the now-unused `field` import from `dataclasses` in `_symbol_key.py`, and the
  now-unused `dataclasses` import in `test_symbol_key.py`. No new noqa added.
- `git diff --stat src/` -> empty (before both the tracer commit and the implementation commit).
- `make test-fast` -> `2162 passed, 5 skipped, 5 warnings in 257.78s`.

## Commits

- WP12: `407d57b0f3` "test(WP12): retire the dead-symbol hash refresh helper and its tests (#5346, C-002)"
- WP13: `6b60ef0637b9ea56b4bb1ab4abe760dc0eb4dbbe` "feat(WP13): retire the hash-toll SymbolKey.source_module surfaces (#5346)" on `kitty/mission-test-suite-remediation-01M3SSDW-lane-m`; tracer commit `3b2a77c9b7`.

No new product defect was exposed by either WP (no `src/` change in WP13's final commit).
