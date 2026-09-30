---
affected_files: []
cycle_number: 3
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T10:38:43Z'
reviewer_agent: claude
wp_id: WP13
---

# WP13 review, cycle 3: REJECTED (reviewer-renata)

All three cycle-2 MEDIUMs and both LOWs are fixed and pinned. Item 6 and the lane-i merge are sound. Two items block approval, and both are small.

## Blocking

1. **[MEDIUM] `mission_finalize.py:3854`: a new `mypy --strict` error, `expected_wp_ids` is `list[str]` but the field is `set[str]`.**
   - T071's extraction introduced `_FinalizeRequirementGates.expected_wp_ids: set[str]`. It is fed from `_extract_wp_ids_from_task_files`, which returns `list[str]`.
   - Earlier invocations missed it because they left out the callee `mission_parsing.py`. With `mission_parsing.py` in the file list, `mypy --strict --explicit-package-bases` reports 9 errors on base (lane-i tip 5faee3662) and 10 on head. This is the only new one.
   - Without `mission_parsing`, mypy instead reports `_finalize_refusal_envelope` as "Returning Any". That is an artefact of skipped imports; the real error is this one.
   - **Fix:** annotate the field as `list[str]`, or convert at the call site. Then add `mission_parsing.py` to the standard mypy invocation in the commit bodies and the task file.

2. **[MEDIUM] `tests/integration/test_owned_lifecycle_acceptance_finalize.py:792` (`_ALLOWED_RESOLVER_READ_ANCHORS`). The allow-list hides a real content read against R, and the pin's comment is inaccurate.**
   - I enumerated all 68 post-mint `get_main_repo_root` pass-through reads on an owned `under_worktrees` finalize.
   - **60 are resolver-only.** They come from `resolve_topology`, `_resolve_coordination_branch`, `mission_has_coordination_branch`, `candidate_feature_dir_for_mission`, `coord_read_dir_for`, `_resolve_group_placement` and `ledger_posture`, and only decide which directory or branch to use. No write happens against R: `RSnapshotter` stays byte-identical.
   - **8 are not resolver-only.** They come from `bootstrap_canonical_state > emit_status_transition_transactional > _resolve_dependency_readiness > _declared_dependencies`. `status/emit.py:366-372` re-anchors `planning_feature_dir` through `resolve_canonical_root(P/kitty-specs/<slug>)`, which returns R. It then reads WP frontmatter `dependencies` from **R/kitty-specs/<slug>/tasks**, not from P.
   - I confirmed this by recording `_match_wp_files`: it was called with `R/kitty-specs/owned-fixture-01M2D900` for WP01 and WP02, and found 0 matches.
   - During finalize the bootstrap moves WPs only to `planned`, so the readiness verdict has no effect here. On the same emitter path for an owned claim, `planned->claimed` is gated. There the check would read R's copy: it treats "no file in R" as "no dependencies", and would use a stale R copy's dependencies if one exists. That bypasses FR dependency gating for owned missions.
   - The anchor `bootstrap_canonical_state` whitelists this silently. That is exactly the "allow-list hides a future leak" risk.
   - **Fix for WP13, a test-only change:**
     - Replace the three broad subsystem anchors with an exact, shrink-only ledger of leaf resolver frames. Use the frame immediately above `_compose_primary_feature_dir`, `resolve_canonical_root` or `resolve_topology`, with a count.
     - List `_declared_dependencies` as a **named known violation**, citing a tracker issue, not as an allowed resolver read.
     - Correct the comment that says these reads "only compute WHICH directory/branch to consult".
   - The `emit.py` fix itself belongs to the status-emitter owner (WP07's file), not to WP13. The orchestrator should route it, together with the issue.

## Verified OK

- **Cycle-2 MEDIUM-1 (ContextVar):**
  - It is set under a token and `reset` in a `finally`.
  - `test_owned_envelope_key_does_not_leak_into_a_later_non_owned_payload` pins it; mutating the reset away makes exactly that test fail.
  - The rationale is documented.
- **Cycle-2 MEDIUM-2 (overloads):** reverted. `_owned_checkout.py` is byte-identical to base again.
- **Cycle-2 MEDIUM-3 (version key):** `_finalize_refusal_envelope` now includes `spec_kitty_version` via `_with_cli_version`, and it is pinned. `indent=2` is kept as `emit_owned_refusal`'s canonical style.
- **LOWs:**
  - `_atomic_write_issue_matrix` is the one serializer.
  - The `test_issue_matrix_scaffold.py` change is now purely additive: 40 insertions, 0 deletions.
- **Item 6 pins are non-vacuous.** Mutating all `repo_root=` threading back to `None` fails both armed pins. The finalize pin fails, and the create pin fails with `MissionCreationError ... owned arm resolved a lifecycle-log root via get_main_repo_root`.
- **`lifecycle_events.py` out-of-map edit:** additive `repo_root: Path | None = None` on three functions. It is passed straight to `persist_lifecycle_event_local`, where it is only the lock root. With `None`, behaviour is unchanged. The edit is declared.
- **Merge 32f944025:**
  - On the lane-l side, the merge touches only `mission_create.py` and `mission_creation.py`.
  - `mission_create.py` equals lane-i's version.
  - `mission_creation.py` equals lane-i's version plus 10 lines (`lifecycle_root` on `_emit_create_events` and 2 `repo_root=` pass-throughs).
  - WP10's decision records are preserved. C901 ≤ 15, with no suppression.
  - The decomposition, owned-charter and checkout-restore tests are green.
- **Lint:** ruff check and format are clean.
