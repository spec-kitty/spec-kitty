---
affected_files: []
cycle_number: 1
mission_slug: single-branch-topology-honesty-01M3M22V
reproduction_command:
reviewed_at: '2026-09-28T19:01:39Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested, for one blocking item: SC-003 accounting.** Everything else is sound:

- red→green;
- five mutation spot-checks, all caught;
- the layer rule;
- the private deferred symbols;
- `topology=` threading;
- the mission-state finding;
- the gate additions.

Details are under "Verified" below.

## Blocking

**Issue 1: the re-stamp dry-run reports 63, not 64, because `064-complete-mission-identity-cutover` is silently skipped with a false reason. The doctor then reports no finding for it, so SC-003's "doctor reports 0 remaining" would be a false green.**

Evidence. I ran the WP03 code against the root checkout's `kitty-specs/`:

- The raw predicate (stored `topology == "single_branch"` AND any `lanes.json` lane id other than `lane-planning`) selects **64** missions: 139 are stored single_branch, 64 of them have a `lanes.json`, and all 64 have a code lane.
- `restamp_single_branch_with_code_lanes(dry_run=True)` selects **63**. The only difference is `064-complete-mission-identity-cutover`. It is not a mission merge, and it is not a predicate misunderstanding at the pre-spec level.
- Why that mission drops out: its `lanes.json` is a legacy manifest keyed `feature_slug` (no `mission_slug`), with one code lane `lane-a` holding WP01–WP09. The canonical `read_lanes_json` raises `CorruptLanesError: ... 'mission_slug'`.
  - `restamp_single_branch_with_code_lanes` (`migration/backfill_topology.py`, the `except CorruptLanesError: manifest = None` arm) then records `action="skip", reason="no code lanes"`, which is **factually wrong**: the mission has a code lane, and its manifest is merely unreadable to the canonical reader.
  - `_identity_audit._topology_finding` has the same arm (`except CorruptLanesError: return None`), so the doctor shows no finding.
- Net effect: after the T015 data commit, one mission still violates Invariant T-1, and both the migration and the doctor report it as clean.

Required change. Pick the mechanism, but all three points must hold:

1. **Report it honestly in both places.** A `lanes.json` that exists but is unreadable must not be reported as "no code lanes".
   - In `RestampResult`, use a distinct action or reason, for example `reason="lanes.json unreadable: <exc>"`. Consider whether `"error"` is right, given that `apply()` turns any error into `success=False` for `spec-kitty upgrade` in consumer repos. A non-failing `skip` with an honest reason, plus a doctor finding, is probably the better trade-off.
   - In `_topology_finding`, emit a finding for stored `single_branch` + an unreadable `lanes.json`. Either reuse `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` with an "unverifiable" note, or add a new code. It must not be `None`.
2. **Do not add a `feature_slug` alias to the canonical `read_lanes_json`.** The Terminology Canon forbids preserving `feature*` aliases in active code paths. The legacy manifest is data to repair, not a shape to re-support.
3. **Reconcile the SC-003 evidence in the Activity Log.** State the dry-run count and why it differs from 64, and say how 064 gets to `lanes` at wrap-up. For example, the orchestrator's T015 data commit also repairs 064's `lanes.json` key, or re-stamps it explicitly, so that the doctor reports 0 remaining. Add a unit test covering a stored-single_branch mission whose `lanes.json` is unreadable, asserting both the migration result reason and the doctor finding.

## Non-blocking (nits; fix if cheap, else note in the Activity Log)

**Nit 2.** `test_planning_only_unstamped_mission_classification_unchanged` is misnamed. At the red commit it fails with `LANES is not SINGLE_BRANCH`. That proves the `has_code_lanes` change DOES reclassify an unstamped planning-only mission, from LANES to SINGLE_BRANCH, which is the intended R-3 semantics. The test really pins "planning-only unstamped derives SINGLE_BRANCH and is never selected by the re-stamp". Rename it or fix its docstring so a later reader does not believe the classification was invariant. No such mission exists in this repo today (I checked), so there is no live impact.

**Nit 3.** `tasks_finalize._ft_apply_writes` explicitly tolerates a missing or malformed `meta.json` (`load_meta_or_empty`, the silent-degrade contract). The new `read_topology(st.primary_feature_dir)` a few lines later raises `FileNotFoundError` or `MissionMetaReadError` in exactly those cases, so a new raw raise now sits on a CLI path. `mission_finalize._compute_and_write_lanes` has the same exposure. It is not reachable for a well-formed mission, and nothing consumes the value yet. Before WP05 makes it load-bearing, either derive the topology from the already-loaded meta, or document why fail-loud is correct there.

**Nit 4.** `backfill-topology --restamp-single-branch --mission X` silently ignores `--mission`. Either honour it (`_kitty_specs_mission_dirs` already supports `mission_slug`) or reject the combination.

**Nit 5.** The canonical sorted-key rewrite produces non-topology line churn in 2 of the 63 candidate meta files: the values are unchanged, but formatting and ordering differ. That is fine per the contract ("no other field" means values); just expect it in the T015 data-commit diff.

## Verified

**Red→green.** At 1f8b8dcc, 4 of 4 fail on assertions: three `assert None is not None` from the registry lookup, plus the control's LANES-vs-SINGLE_BRANCH assertion. There are no ImportErrors. At HEAD, all pass.

**Migration behaviour.** It writes `topology` only, is idempotent (a second run shows byte-identity), does not commit (subprocess spy), and sets `runs_on_worktrees=False`. The doctor finding has positive and negative controls.

**C-003.** `read_topology` and the doctor never raise because of the mismatch. The assertion is uncalled from `src/` until WP05, per fold B-2.

**Layer rule.** `mission_runtime/context.py` imports nothing from `specify_cli`. `TopologyManifestMismatch` is a plain `RuntimeError` with an inline `error_code`. `test_layer_rules` passes.

**Private deferred symbols.** Making `_assert_topology_matches_manifest` and `_has_code_wps` private with no callers yet is acceptable. It follows the WP02 precedent, `grep` shows no reachable `src/` dependency, and WP05/WP04 must promote them when wiring.

**`topology=` threading.** All three callers pass it (`tasks_finalize:388`, `mission_finalize:2507`, `mission_state:1633`). `doctor mission-state --fix` catches `TopologyManifestMismatch` and reports `lanes_rebuild_skipped_topology_unmigrated`, with a test.

**Mutations.** I ran each in a throwaway worktree, then restored and removed it. All were caught:

| Mutation | Failing tests |
|---|---|
| M1: `has_code_lanes` changed to `bool(lanes)` | 6 |
| M2: `_has_lanes` changed to `True` | 1 |
| M3: the mission_state catch re-raises | 1 |
| M4: the doctor finding returns `None` | 1 |
| M5: the assertion made a no-op | 3 |

**Out-of-map edits and gates.** The edits to 5 test files are mechanical `topology=`/meta fixture additions. `test_no_dead_modules` gains an auto-discovered-migration entry of the same shape as its siblings. `test_mission_runtime_surface` adds `TopologyManifestMismatch` to the public surface. Neither gate is weakened.

**Tests and tools.**
- Targeted and gates: 332 passed, 3 skipped. The run covered:
  - `test_layer_rules`, `test_no_dead_symbols`, `test_no_dead_modules`, `test_mission_runtime_surface`, `test_migration_chain_integrity`;
  - the migration, predicates, assertion, backfill, CLI, identity-audit and mission-state tests;
  - `refinalize`, `finalize_phases`, `compute_and_persist_core`.
- `ruff check` and `ruff format --check` are clean on all 22 changed files.
- `mypy --strict` on the changed src files reports three errors, all pre-existing or a known pattern:
  - `BaseMigration`-is-Any, which the sibling rc5 migrations also hit;
  - `mission_finalize:179`;
  - `issue_matrix_migration:254`.
