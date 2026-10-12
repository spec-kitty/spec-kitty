# Code grounding: remove the dead #2985 compatibility-repair machinery (#6095)

Read-only grounding run, 2026-10-12. Base: `origin/main` `8a911083` (the #6058 fix
"claim-slot drift is a blocking SNAPSHOT_DRIFT again now that events 10.4.4 keeps
attribution"), which is HEAD of `main`. Environment: `spec-kitty-cli 4.0.0rc7`,
`spec_kitty_events 10.4.4` (runtime-verified, not just the lockfile pin).

This note establishes that the #2985 compatibility-repair path mints nothing under
events 10.4.4, confirms the removal is behaviour-preserving, and maps the exact
dead-reference chain so nothing is left dangling. It is a tidy-first / structural
change (Charter Standing Order 2, `DIRECTIVE_025`), **not** a bugfix.

## 0. Hard precondition (the whole premise)

```
$ python -c "import spec_kitty_events as e; print(e.__version__)"
10.4.4
$ grep -n -A1 'name = "spec-kitty-events"' uv.lock | tail -2
2390:name = "spec-kitty-events"
2391-version = "10.4.4"
```

If events were not 10.4.4 the premise would not hold and nothing would be deleted.
It is 10.4.4, resolved exactly by `uv.lock`; `pyproject.toml` pins `>=10.4.4,<11`.
`#6058` (the reducer folding old-seed claim slots so the birth-cutover snapshot holds
without a repair) and `#6084` (events 10.4.4 adoption) are both already on `main`.

## 1. Current shape of `src/specify_cli/migration/backfill_runtime_state.py`

2512 lines. The module's live job is unchanged by this mission: read legacy runtime
(`read_legacy_runtime`), build deterministic seed events (`_build_seed_events`), append
them idempotently (`backfill_runtime_state` / `_backfill_runtime_state_locked`), and
verify no data loss (`verify_backfill`). Layered on top is the #2985 append-only
**compatibility-repair** machinery — the subject of this removal.

Responsibility map of every repair symbol named in #6095 (re-located on this checkout;
the issue's line numbers were not trusted):

| Symbol | Def | Role | Disposition |
|---|---|---|---|
| `COMPATIBILITY_REPAIR_ACTOR` | 127 | actor tag for minted repair rows | **remove** |
| `_repair_id` | 339 | deterministic id in the repair namespace | **remove** (only callers are the repair planner) |
| `_compatibility_repair_at` | 485 | timestamp strictly after pre-repair history | **remove** (only caller is the repair planner) |
| `_stream_without_compatibility_repairs` | 1218 | read-path filter dropping repair rows | **remove** (only caller is the repair planner) |
| `_repair_scalar_value` | 1226 | changed-value helper | **remove** (only used by `_runtime_repair_delta`) |
| `_runtime_repair_delta` | 1240 | builds the runtime-slot repair annotation | **remove** |
| `_misaligned_seed_wps` | 1170 | set of WPs whose seeds predate the floor | **remove** (becomes unreferenced — see §4) |
| `_plan_compatibility_repairs` | 1280 | the planner/minter | **remove** + fold out both call sites |
| `_verify_compatibility_repairs` | 1983 | verifies minted repair witnesses | **remove** + fold out its call site |
| `_is_migration_actor` | 344 | folds `BACKFILL_ACTOR` **and** repair actor | **keep, drop repair branch** (live: `_wp_events`, `_stream_without_migration`, `_seeded_frontmatter_slots`) |

Read-path filters that reference the repair actor and must be simplified (not deleted):
`_wp_events` (431) `include_seeds=True` branch (line 456) and the `_is_migration_actor`
body (line 346).

## 2. PROOF OF DEATH (empirical)

The codebase's own 10.4.2-era RETIRED note (`tests/unit/migration/test_backfill_runtime_state.py`
lines 1161-1172) records that the former `test_compatibility_repair_lands_after_history...`
stopped minting under 10.4.2 and names the **birth-cutover mixed mission** as the *last*
scenario still minting a repair. `#6084` then loosened that birth-cutover assertion from
`assert repairs` to `assert all(event.wp_id == "WP01" for event in repairs)` — vacuously
true on an empty list — with an inline comment that under 10.4.4 the reducer folds the old
seed's claim slots so the snapshot holds *without* a repair. The assertion deliberately
tolerates BOTH outcomes, so the "mints nothing" claim had to be settled empirically.

A throwaway probe (`tests/migration/test_zzz_probe_6095_proof_of_death.py`, not committed)
mirrored the real birth-cutover test but replaced the vacuous assertion with an explicit
`assert repairs == []`, across both `at_encoding` values the real test parametrizes:

```
$ PWHEADLESS=1 .venv/bin/python -m pytest \
    tests/migration/test_zzz_probe_6095_proof_of_death.py -q -s -p no:randomly
[PROBE #6095] at_encoding='offset': repair_count=0 repairs=[]
[PROBE #6095] at_encoding='zulu':   repair_count=0 repairs=[]
2 passed
```

WP01 is still *flagged* misaligned (`_misaligned_seed_wps` returns it), but the `desired`
and `current` snapshots collapse to `desired == current` for every repairable seed shape
under the correct Lamport reducer (lane `done`, `shell_pid=4201`,
`agent=later-legitimate-agent` all equal) — so `_plan_compatibility_repairs` returns
`([], [])`. The probe also re-asserts the end-state invariants (lanes, claim slots,
idempotency) that MUST survive removal; they pass. No still-diverging seed shape could be
constructed under 10.4.4 — the reduction argument in #6095 (both snapshots are `reduce()`
outputs, and a correct causal reducer orders a pre-floor seed identically with and without
the corrected seed) shows why none can exist.

Corroboration (independent, treated as supporting data): the real dogfood corpus test
`tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` is green under 10.4.4
(`verify_backfill` passes with no repair witness demanded). The nightly `#6073`
repair-witness red was a **10.4.2-era** run that self-heals under 10.4.4, not live evidence
the repair is still needed.

**Decision gate:** `repairs == []` witnessed. The code is dead → proceed with removal. (Had
any seed shape minted a repair, the mission would have halted and reported the counterexample
instead of deleting.)

## 3. Caveat check (#6095): no external dependence on a repair row

```
$ grep -rn "COMPATIBILITY_REPAIR_ACTOR\|_is_migration_actor\|compatibility_repair" \
    src/ --include="*.py" | grep -v backfill_runtime_state.py
(none)
```

Every reference to the repair actor and the repair helpers is internal to
`backfill_runtime_state.py` (26 references, all inside the module). The module's external
importers (`migrate_cmd.py`, `status/cutover_eligibility.py`,
`upgrade/migrations/m_zz_runtime_state_backfill.py`, `migration/runtime_state_cutover.py`,
`cli/commands/migrate/backfill_wp_status.py`) consume only the LIVE public surface —
`read_legacy_runtime`, `verify_backfill`, `backfill_runtime_state`,
`backfill_runtime_state_repo`, `apply_wp_status_backfill`. No reader anywhere in `src/`
special-cases a `COMPATIBILITY_REPAIR_ACTOR` row on disk. The caveat is satisfied.

## 4. The dead-reference chain (what is live, what becomes unreferenced)

Definitive reference census (code refs only) drove these calls:

**Keep — live callers remain after the repair planner/verifier go:**
- `_stream_without_migration` — live callers at 652, 720, 1898, 2137 (not repair).
- `_is_migration_actor` — live callers 457, 1213-1214, 1888. Simplify body to
  `return actor == BACKFILL_ACTOR`; drop the repair-actor branch.
- `_wp_history_floor` — live caller 888 (`_claim_carrier` path).
- `_wp_events` — after `_compatibility_repair_at` goes, its only remaining caller
  (`_wp_history_floor`) uses `include_seeds=False`. Collapse to the migration-excluding
  filter; drop the `include_seeds` parameter and the repair-actor reference at line 456.
- `_legacy_contract_carriers`, `_matches_legacy_contract`, `_LegacyCarrier` — **LIVE**,
  despite being on #6095's removal list. They are used by `_seed_row_mismatch` (1928) and
  `_verify_expected_seed_events` (1966) to *tolerate* a legitimately-shaped pre-floor seed
  during verify (old `at`, or the pre-#2985 full-payload carrier) so verify does not
  false-fail. That tolerance is live behaviour, independent of minting. **KEEP all three.**
  Only their repair-path callers (`_misaligned_seed_wps`, now removed) go away.
- `_seed_row_mismatch`, `_verify_expected_seed_events`, `_verify_claim_slot_witnesses`,
  `_claim_witness_denominator` — the live, fail-closed data-loss / claim-slot parity guards.
  **KEEP.** Only reword the `_seed_row_mismatch` docstring, which currently frames the
  tolerance as "routes to the append-only repair path"; the tolerance stays, the repair
  framing goes.

**Remove — every caller is repair code:** `_plan_compatibility_repairs`,
`_verify_compatibility_repairs`, `_misaligned_seed_wps`, `_runtime_repair_delta`,
`_repair_scalar_value`, `_compatibility_repair_at`, `_repair_id`,
`_stream_without_compatibility_repairs`, `COMPATIBILITY_REPAIR_ACTOR`.

**Fold out two live call sites (no behaviour change — the planner always returns `[],[]`):**
- `_backfill_runtime_state_locked` (1463-1474): delete the `_plan_compatibility_repairs`
  call and the two `.extend(...)` of repair rows; the deduped seeds flow straight to
  `seeded_count`.
- `verify_backfill` (2333-2348): delete the `_build_seed_events`-for-expected-repairs call
  and the `_verify_compatibility_repairs` extend; keep the `_verify_expected_seed_events`
  (2332) and `_verify_claim_slot_witnesses` (2352) extends.

## 5. Invariants that must survive (with citations)

- The end-state / lane / runtime-slot / idempotency behaviour of backfill+cutover — the
  snapshot assertions in `tests/migration/test_birth_cutover.py::test_issue_2985_...`
  (lanes, `shell_pid`, `agent`, `shell_pid_created_at`, the `new_seed_rows` ordering, and
  the second-cutover byte-identical idempotency) — stays green. Only the repair-exercising
  block (lines 729-734, already vacuous) is removed.
- `verify_backfill`'s live guards stay: `_verify_expected_seed_events` (seed presence +
  pre-floor tolerance) and `_verify_claim_slot_witnesses` (independent claim-slot parity).
- Reducer duality (CLAUDE.md "Status Model Patterns"): the Lamport `reduce`/`materialize`
  authority is untouched; this mission does not alter the reducer.
- Shared Package Boundary: `spec-kitty-events` is an external contract — untouched.

## 6. Architectural gates that reference this module (keep green honestly)

- `tests/architectural/test_no_dead_symbols.py` — walks `__all__` + allowlist
  (`dead_symbol_allowlist.yaml`). The module's allowlist entries are its LIVE public
  symbols (`assert_zero_readers`, `backfill_runtime_state_repo`, `run_backfill_and_verify`),
  NOT the repair symbols — the repair symbols stay "alive" only via internal references, so
  a clean full removal removes them without any allowlist edit.
- `tests/architectural/test_no_dead_modules.py` — the module keeps live external callers, so
  it never becomes an orphan.
- `tests/architectural/_baselines.yaml` — notes at lines 95/109 reference
  `migration.backfill_runtime_state` (shrink-only ratchet; shrinkage WARNS, never FAILS, per
  Burn-down Policy). Re-point honestly if a count moves; never loosen, never add an allowlist
  entry (operator ruling: no new size/length/ratchet gates).
- Other references found: `_load_meta_census.py`, `test_status_unsafe_allowlist.py`,
  `test_status_events_writes_gate.py` — to be re-checked during slice 4; the removal touches
  no public symbol they key on.

## 7. Test seams and their cost

- `tests/migration/test_birth_cutover.py` — the end-state cutover coverage. KEEP; delete only
  the vacuous repair-assertion block.
- `tests/unit/migration/test_backfill_runtime_state.py` — carries the 10.4.2-era RETIRED note
  and a `test_...repairs == []` assertion referencing `COMPATIBILITY_REPAIR_ACTOR`. The
  end-state assertions stay; the repair-actor-referencing machinery/notes that only document
  the retired repair are pruned so no test references a removed symbol.
- Full test-reference sweep for removed symbols is slice-3 scope.

## 8. Interactions / prerequisites

No open PR touches this file. `#6084`/`#6058` are already merged on `main`; events 10.4.4 is
pinned. No sibling run known. Consolidation regressions in `#6071`/`#6073`
(lane_planning_data_loss, skip-lanes, coord-topology) are a different, unrelated bugfix —
out of scope for this mission.

## 9. 90-day churn

The grounding clone was shallow (`--depth 1`), so `git log --since=90.days` over
`backfill_runtime_state.py` and the two tests surfaces only HEAD (`#6058`). History before
that is truncated in this checkout; the salient recent churn is exactly the 10.4.4 adoption
chain (`#6084` loosening the birth-cutover assertion, `#6058` the reducer fold) that makes
this removal possible.
