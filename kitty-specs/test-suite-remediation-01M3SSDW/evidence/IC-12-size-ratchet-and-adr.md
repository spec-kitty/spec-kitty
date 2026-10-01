# IC-12 — Size ratchet + top-level-keys floor + ADR (WP14 + WP15)

Per tasks.md closeout step 1, this concern merges WP14's reported evidence (scratchpad
`wp14-evidence.md`) with WP15's reported evidence (scratchpad `wp15-evidence.md`), and both
WPs' full approval notes (`status.events.jsonl`, `review_ref: auto-approval:WP14:20260930`
and `auto-approval:WP15:20261001` — considerably more itemized than the one-line
`review-cycle-1.md` files).

## WP14 — size-ratchet rows + `_REQUIRED_TOP_LEVEL_KEYS` floor

### #5346-1 / F2 — `:618` conversion (T065)

```yaml
id: EV-IC12-F2
item: "#5346-1 / F2"
kind: FIX
planted_break:
  target: "tests/architectural/dead_symbol_allowlist.yaml + tests/architectural/test_no_dead_symbols.py::allowlist_entries _SIZE_RATCHETS row"
  description: "neutral plant: added the new _SIZE_RATCHETS row + YAML leaf WITHOUT touching :618"
  reverted: true
command: "uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -n0 -q -k test_size_ratchet_table_meets_floor"
results:
  old_form_under_break: "RED -- AssertionError: assert 16 == 15 (len(_REQUIRED_TOP_LEVEL_KEYS) now 16, the ==15 pin reds)"
  new_form_under_break: "GREEN -- 1 passed, after converting == 15 to a shrink-only floor >= 16"
  violation_plant: "scratch-deleted BOTH new _SIZE_RATCHETS rows AND both new YAML leaves -> RED: AssertionError: assert 15 >= 16 (back to 15, floor catches the silent removal)"
  clean_tree: "pass (full-file re-run, all green)"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP14:20260930): "F-03 delete both rows +
  section -> test_size_ratchet_table_meets_floor RED 'assert 15 >= 16', 41 others pass (floor
  is the sole catcher)" — exactly this record's violation plant, reproduced independently
  (sha256-verified byte-exact revert). The reviewer also ran an additional plant not in the
  WP's own report: "duplicate allowlist_entries row -> duplicate (section, leaf) check RED" —
  recorded here since it directly exercises this record's own "duplicate (section,leaf) check
  :620-621" claim below. Tallied in evidence/README.md.
  Repins since 2026-08-01: 3 (`f6c137cc1d` 12->13, `ed03553692` 13->14, `639aa2febc` 14->15).
  New invariant: `>= 16` (live section count at landing, with the new test_no_dead_symbols
  section); the duplicate (section,leaf) check :620-621 + the leaf<->row bijection test
  carry the rest.
```

### K-14a / K-14b (new) — the two new cap rows

```yaml
id: EV-IC12-K14a
item: "K-14a (new) test_no_dead_symbols.allowlist_entries (SYMBOL_ALLOWLIST)"
kind: FIX
planted_break:
  target: "tests/architectural/dead_symbol_allowlist.yaml::entries"
  description: "scratch-appended one entry (charter.activation._scratch_growth_plant_wp14::SCRATCH_GROWTH_PLANT_WP14, category_a_slice_f_deferred) without raising the _baselines.yaml leaf"
  reverted: true   # git checkout -- tests/architectural/dead_symbol_allowlist.yaml
command: "uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -n0 -q -k test_growing_an_allowlist_above_baseline_fails"
results:
  old_form_under_break: "n/a -- new row; growth was previously unconstrained"
  new_form_under_break: "RED -- AssertionError: ... test_no_dead_symbols.allowlist_entries (SYMBOL_ALLOWLIST): baseline=293 current=294. Remove the new entry OR edit _baselines.yaml from 293 to 294 ..."
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "growth plant +1 entries row -> test_growing_an_allowlist_above_baseline_fails
  RED 'test_no_dead_symbols.allowlist_entries (SYMBOL_ALLOWLIST): baseline=293 current=294'"
  — exactly this record's planted break and message, reproduced independently (scratch,
  reverted, sha256-verified byte-exact). Tallied in evidence/README.md.
  First cap (Burn-down (a)) on the dead-symbol allowlist (FR-009, #5346).
  `test_lowering_an_enforced_leaf_below_live_fails[test_no_dead_symbols.allowlist_entries]`
  passes (proves the row reads its own leaf): `uv run --frozen pytest
  tests/architectural/test_ratchet_baselines.py -n0 -q -k "test_no_dead_symbols"` -> 2 passed.
```

```yaml
id: EV-IC12-K14b
item: "K-14b (new) test_no_dead_symbols.widened_grandfathered_470 (WIDENED_SCOPE_GRANDFATHERED_470)"
kind: FIX
planted_break:
  target: "tests/architectural/dead_symbol_allowlist.yaml::widened_grandfathered_470.entries"
  description: "scratch-appended one entry (charter.activation._scratch_growth_plant_wp14::SCRATCH_GROWTH_PLANT_WP14) without raising the _baselines.yaml leaf"
  reverted: true
command: "uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -n0 -q -k test_growing_an_allowlist_above_baseline_fails"
results:
  new_form_under_break: "RED -- AssertionError: ... test_no_dead_symbols.widened_grandfathered_470 (WIDENED_SCOPE_GRANDFATHERED_470): baseline=91 current=92. ..."
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "+1 widened entry -> RED 'widened_grandfathered_470 ...
  baseline=91 current=92'" — exactly this record's planted break and message, reproduced
  independently. Tallied in evidence/README.md. RK-6 ruling: second leaf in the same section,
  no new top-level key. Parametrized lowering test for this leaf also passes.
```

### Planted-leaf re-plant (T068)

```yaml
id: EV-IC12-T068
item: "test_leaf_drift_detects_planted_unenforced_leaf re-plant"
kind: FIX
planted_break:
  target: "the test itself"
  description: >
    changed the plant from planted["test_no_dead_symbols"] = {"x": 1} (now a REAL, enforced
    section -- would silently replace it and invalidate the test's intent) to
    planted["test_never_enforced_section"] = {"x": 1}.
  reverted: true
command: "uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -n0 -q -k test_leaf_drift_detects_planted_unenforced_leaf"
results:
  old_form_under_wp14_new_rows: 'RED (pre-re-plant) -- AssertionError: assert ([\'test_layer...ist_entries\']) == ([\'test_layer...mbols.x\'], [])'
  new_form: "GREEN -- folded into the 43-test full-file run"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "(4) duplicate allowlist_entries row -> duplicate
  (section, leaf) check RED; (5) rows removed, leaves kept -> test_every_baseline_leaf_is_enforced_by_a_size_ratchet
  RED naming both leaves" — item (5) is exactly this record's "kept rows, dropped leaves"
  claim, now actually executed as its own scratch state (rather than reasoned through
  without a fourth revert cycle, as the WP's own report states it did). Tallied in
  evidence/README.md. Planted proof (kept rows, dropped leaves): removing the two new
  _SIZE_RATCHETS rows while keeping their YAML leaves makes _leaf_drift report both new
  leaves as unenforced, redding test_every_baseline_leaf_is_enforced_by_a_size_ratchet -- the
  same code path as the F2 violation plant above.
```

### SC-004 / FR-008 disposition table (as reported)

| id | site | class | disposition | keep_reason / invariant_form | repins since 2026-08-01 |
|---|---|---|---|---|---|
| #5346-1 / F2 | `test_ratchet_baselines.py:618` (converted) | live-structure-pin | **convert** (floor) | `>= 16` | 3 |
| K-14a (new) | `_baselines.yaml: test_no_dead_symbols.allowlist_entries: 293` | ratchet | **keep-ratchet (new)** | first cap (Burn-down (a)) | 0 (new row) |
| K-14b (new) | `_baselines.yaml: test_no_dead_symbols.widened_grandfathered_470: 91` | ratchet | **keep-ratchet (new)** | RK-6 ruling | 0 (new row) |
| K-1 | `_baselines.yaml:387` `destructive_op_allowlist: 61` | ratchet | **keep-ratchet** | every growth matched an allowlist row | 2 |
| K-2 | `_baselines.yaml:231` `test_no_inert_schema_slots.baseline_entries: 36` | ratchet | **keep-ratchet** | 3/4 moves burn-down, 1 real new debt row | 4 |
| K-3 | `_baselines.yaml:158` `category_7_grandfathered_orphans: 5` | ratchet | **keep-ratchet** | visibility device, every move justified | 13 |
| K-4 | `_baselines.yaml:321` `egress_allowlist_files: 17` (+ other leaves) | ratchet | **keep-ratchet** | each growth coincides with a reviewed allowlist row | 1-8 each |
| K-5 | `test_charter_path_literal_authority.py:575` `CHARTER_PATH_LITERAL_FLOOR = 49` | ratchet (misnamed ceiling) | **keep-ratchet** | one historical FR-008 lapse noted (`583db03345`, behaviour-neutral refactor) — not touched in this WP | 6/8 |
| K-6 | `test_inline_meta_read_gate.py:75` `INLINE_META_READ_FLOOR = 2` | ratchet (lock-in-on-shrink) | **keep-ratchet** | moved only on burn-down | 1 |
| K-7 | `test_ratchet_positional_anchor_ban.py:1055` `_FR014_DEFERRED_CENSUS_ALLOWLISTS == 1` | ratchet (enumerated shrink-only) | **keep-ratchet** | moved only on burn-down | 1 |
| K-8 | 6 non-vacuity `>=`/`<=` floors across 6 files | ratchet / non-vacuity floor | **keep-ratchet** | compared with inequality, not `==` | 1-2 each |
| N-1 | 11 local-test-value counts across 6 files | local-test-value | **not-a-pin** | counts of what the unit under test emitted for a fixture | 1 each |
| C-1 | `test_timing_coverage_invariant.py:386` `== 62` | contract | **keep-contract** | frozen evidence table, canonical-commit snapshot | n/a |
| R-1 | `test_inline_meta_read_gate.py` `ROUTED_LOAD_META_FLOOR` | pin | **resolved** | deleted outright by `dd82bd340b` (#4315), after 17 re-pins | n/a |
| R-2 | DRG `_EXPECTED_NODE_COUNT`/`_EXPECTED_EDGE_COUNT` | pin | **resolved** | `2e40057da1` (#3234): filesystem-derived | n/a |
| R-3 | destructive-op line re-pins | line anchors | **resolved** | `133755de03` (#5085) | n/a |
| W-1 | FR-010 (shift-left census gate) | n/a | **withdrawn** | Withdrawn at plan time (DM-01M3SVDP); ADR 2026-09-14-1; no gate added (C-008) | n/a |

Rows NOT duplicated here (owned by other WPs): F12b (`test_tracker_egress_guards_3108.py:965`,
keep-contract) — recorded by WP08 under IC-07; `test_symbol_key.py:644` `== 400` — recorded by
WP13 under IC-11.

### Final named-file test run (WP14, all green)

`uv run --frozen pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q` -> **242 passed in 81.92s**.

Quality gates: `ruff check test_ratchet_baselines.py` -> All checks passed!; `ruff format --check` -> 1 file already formatted. `make test-fast` -> `2169 passed, 5 skipped, 4 warnings in 260.05s (0:04:20)`. `git diff --stat src/` empty before commit (no rule-A product fix).

Commit: `448fdbf97886ef413c3a24c6f015782dd268e1aa` "feat(WP14): size-ratchet rows for the dead-symbol allowlist + top-level-keys floor".

---

## WP15 — ADR + gate-mechanics docs (lane-o)

```yaml
id: EV-IC12-ADR
item: "C-011 RED/GREEN leg: new ADR present but unregistered, then registered"
kind: FIX
planted_break:
  target: "docs/adr/4.x/2026-10-01-1-dead-symbol-allowlist-module-name-identity.md present, NOT registered in docs/adr/4.x/index.md or the inventory"
  description: "a docs-gate break, not a code mutation (WP15 is docs-only)"
  reverted: true   # resolved by registering, not by reverting a plant
command: "PYTHONPATH=. uv run --frozen python scripts/docs/check_docs_freshness.py --ci"
results:
  e0_baseline_clean_tree: "exit=0 findings=3 errors=0 warnings=3 (3x pre-existing HELP-DRIFT 'moments drain*' warnings, not WP15)"
  r1_red_leg: >
    exit=1 findings=10 errors=4 warnings=6 -- ERROR DOCS-INDEX-DRIFT, ERROR
    INVENTORY-INCOMPLETE, ERROR INVENTORY-LOCKFILE-DRIFT, ERROR LEAK-MISSING-INVENTORY
    (all naming the new ADR file)
  r2_red_leg_freshener: "freshen_adr_inventory --check <file> -> ADR-README-ROW-MISSING; INVENTORY-LOCKFILE-DRIFT; STALE (missing_rows=1 inventory_stale=True) exit=1"
  r3_tooling_self_test: "uv run --frozen pytest tests/docs/test_freshen_adr_inventory.py tests/docs/test_docs_index_freshness.py -n0 -q -> 23 passed (tests tooling against synthetic fixtures, green in both states; R1/R2 are the live-tree red->green legs)"
  g1_green_leg: "exit=0 findings=4 errors=0 warnings=4 (3 pre-existing HELP-DRIFT + 1 LINK-HEALTH-FAILED external 403 on an untouched page, network-flaky)"
  g2_green_leg_freshener: "freshen_adr_inventory --check <file> -> clean (missing_rows=0 inventory_stale=False) exit=0"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP15:20261001): "C-011 red reproduced in a
  scratch export (errors=6 with index, inventory and retrieval index reverted), green at
  HEAD" — the same red->green docs gate recorded here, reproduced independently by the
  reviewer via a separate scratch-export method (errors=6 vs. the implementer's own errors=4
  — both runs confirm red, the different error count reflecting a different revert scope: the
  reviewer additionally reverted the retrieval index, which the implementer's own R1 run did
  not separately revert). Tallied in evidence/README.md.
  T072 register: `freshen_adr_inventory <file>` -> README-ROW-ADDED, rows_added=1,
  inventory=regenerated (exit 0); docs/adr/4.x/index.md `updated:` bumped by hand
  2026-09-30 -> 2026-10-01 (the tool does not bump it). T073 regenerate:
  docs_index.py --write -> generated=849 committed=849; inventory_lockfile.py --write ->
  idempotent (drift=False). Self-caught defect during T073: the how-to's new unquoted
  description: contained ": " -> YAML mis-parse -> description_length_check 1 violation;
  fixed by quoting; re-run -> 813 pages checked, 0 violations.
```

### Named tests, terminology, scope, make test-fast

- `uv run --frozen pytest tests/docs/test_freshen_adr_inventory.py tests/docs/test_inventory_lockfile.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_index_freshness.py tests/architectural/test_no_legacy_terminology.py -n0 -q` -> **135 passed in 25.22s** (0 failed).
- Stale-guidance sweep: `git grep -n -e "renaming-a-symbol-whose-body" -e "hash-refresh" -e "refresh_dead_symbol" -- ':!kitty-specs'` -> only 4 hits, all historical `docs/changelog/CHANGELOG.md` entries (immutable history, no edit). `ci-gate-mechanics.md` no longer mentions the refresh tool.
- Terminology (NFR-005): manual scan of added prose for `-w feature/features/primary/merge/routing` -> 1 hit, a code-spanned `merge` -> `consolidate` package rename (qualified). `test_no_legacy_terminology.py` green (in the 135).
- Scope rule A: `git diff --stat src/ tests/` -> empty; `git diff --stat` -> exactly the 6 owned paths (`docs/adr/4.x/index.md`, `3-2-docs-retrieval-index.yaml`, `3-2-page-inventory.yaml`, `add-architectural-gate-exemption.md`, `ci-gate-mechanics.md`, + new ADR). No CHANGELOG edit.
- `make test-fast` -> `2162 passed, 5 skipped, 5 warnings in 253.91s`, exit 0.

Commit: `6b40ebc865` "docs(WP15): ADR for (module, name) dead-symbol allowlist identity + gate-mechanics docs (#5346)".

**Rule B note (as reported):** WP15 is docs-only; there is no planted code mutation. The one
verifiable break->fix pair is the C-011 docs gate above.
