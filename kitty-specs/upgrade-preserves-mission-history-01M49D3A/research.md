# Research: Upgrade must not rewrite healthy Mission history

The grounding squad and the post-spec squad, run 2026-10-06/07, produced these findings. All were checked at `1fb084d7f2`.

## R-1: Root causes are live (#5811)

- **Decision**: Fix all four root causes. None of them is superseded.
- **Evidence**:
  - `upgrade.py:1287` passes `repair_opt_in=confirm`.
  - `_teamspace_mission_state_gate.py:232` calls `repair_repo(project_path)` with no scope.
  - `mission_state.py:2517-2523` selects every directory.
  - `:2414` and `:2417` always emit `reason_source` and `review_result`.
  - `:2001` sorts the rows.
  - `:1797-1801` rewrites `status.json`.
  - ADR `2026-10-06-1` changes only how hosted surfaces are shown; it does not touch this gate.
  - No open PR touches `mission_state.py`.

## R-2: Drain is a safe gate

- **Decision**: Evaluate the upgrade-time gate only under drain.
- **Rationale**:
  - Drain (`core/hosted_posture.py`) is on only when both the repository `hosted.drain` key and the personal `[hosted] drain` key are true, so it is off by default.
  - In upgrade the gate only advises: it never exits non-zero, and its only side effect is the repair.
  - The blocking gate `enforce_teamspace_mission_state_ready` lives in `tracker.py:247` and is untouched.
  - Doctor still reports findings to users without hosted access.
- **Alternatives**:
  - Repair only the blocked Missions (option A). Rejected: `--yes` could still mutate history, and residue blockers would mint identities.
  - Report always (option B without drain). Rejected: Team Kitty is unsupported, so the noise has no value.

## R-3: Row serialization has two authorities

- **Decision**: Lane rows round-trip through `StatusEvent.from_dict(...).to_dict()` and the store's row-to-line function. Delete the `_build_canonical_row` allowlist.
- **Evidence**: The allowlist drifts from `StatusEvent.to_dict()` in three ways:
  1. It emits null optional keys.
  2. It flattens a structured `actor` with `str(...)`.
  3. It overwrites `mission_id` unconditionally.

  `_build_canonical_row` already calls `from_dict` (`:2448`), but only to validate. The store applies `sanitize_event_for_log` (`status/store.py:300`, `:385`), so the repair must apply the same function.
- **Rows that bypass the round trip, byte-preserved**:
  - authoritative non-lane event types (`AUTHORITATIVE_NON_LANE_EVENT_TYPES`, #4897/#4993);
  - annotation rows;
  - preserved non-lane rows (`_is_preserved_non_lane_row`).
- **Legacy typed rows**: `WPStatusChanged` rows get their alias and strip rules first.
- **Other serializers, follow-up only**: `status/event_log_merge.py:79,99`, `status/lifecycle_events.py:601` and `status/migrate_lifecycle_envelope.py:394`. These are not on the repair path.

## R-4: Ordering

- **Decision**: Remove the sort and keep the physical order.
- **Rationale**: The reducer applies its own ordering, so lane state does not depend on the file order. The WP02 tests materialize before and after on a shuffled fixture to prove that lane state is unchanged. No ordering operation is added; if one is ever needed, it will be a separate, explicit, reported command (spec FR-004).

## R-5: Mission classification has several authorities

- **Decision**: Add a public `is_mission_dir` next to `_iter_mission_dirs` (`context/mission_resolver.py:221`, population rule at `:279`: "`spec.md` or `meta.json`"). Its new aspect is that the file must be git-tracked. `_select_mission_dirs` and `audit/engine.py` consume it.
- **Deferred**: Unifying the other walkers (`retrospective/summary.py:291`, `runtime/next/_internal_runtime/discovery.py:246`). A follow-up issue will be filed.

## R-6: What `errors=52` counts

- **Finding**: `missions_error` counts Missions in which any row failed `_canonicalize_status_row` (collected at `mission_state.py:1951`). The likely reasons are `missing required to_lane` (`:2342`) and `missing required wp_id` (`:2349`): legacy or non-lane rows.
- **Decision**: The repair outcome names each errored Mission and its first reason and exits non-zero. WP02 characterizes the class on a sample from the dogfooding corpus; if those rows are preserved non-lane shapes, they become byte-preserved instead of errors.

## R-7: Tests that pin today's behaviour

The following tests are expected to change deliberately; each gets a KEEP or RETIRE verdict at closeout:
- `tests/integration/migration/fixtures/12_canonical_row.json`, which pins `reason_source: null`;
- `test_mission_state_repair_fidelity_e2e.py`;
- `test_repair_primary_anchor.py`;
- `test_audit_trail_durability_4928.py`;
- `tests/status/test_authoritative_non_lane_registry_4897.py`, for its sort rationale;
- `tests/upgrade/test_teamspace_consent_scope.py`;
- `test_yes_consent_exit_honesty.py`;
- `test_upgrade_outcome_rendering.py`;
- `test_upgrade_auto_commit_unit.py`;
- `test_recovery_composition.py`.

## Squad findings disposition

- **Reviewer lens: 9 findings.** All were folded into the spec (`18350b4`).
- **Boundary lens: 4 findings.** Three were folded into the spec and this plan. One was deferred: the walker unification, which is a follow-up.
