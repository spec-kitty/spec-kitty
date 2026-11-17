# Discovery squad: similar surfaces (pre-spec)

All paths are under `src/specify_cli/`.

## The seam to reuse for the retarget commit
- **Template:** the mission-number primary-tree bake, `consolidation/mission_number/bake.py::_bake_mission_number_on_primary_tree`.
  - It refuses first (`_primary_checkout_refusal`: detached HEAD, off-target checkout, or meta untracked/dirty/skip-worktree).
  - It writes with `mission_metadata.locked_update_meta` and keeps the before and written bytes.
  - It commits with `git/bookkeeping_commit.py::commit_merge_bookkeeping(..., destination_ref_override=<new target>)`.
  - It undoes with `restore_meta_text(..., expected_current=written)`.
- **Do not use:** `set_target_branch` (no CAS undo, no commit). The #5100 clear in `phase_teardown` is fail-open, so it is wrong for a first mutation.
- `destination_ref_override` is required. Without it, placement resolves the old `target_branch`, and the commit fails with `SafeCommitHeadMismatch`.

## lanes.json
It is read once, in `executor._run_lane_based_consolidation`. `--target` sets `manifest.target_branch` in memory only, and the manifest is reseeded from `state.target_branch` after the state loads. No on-disk lanes.json write is needed for the run. Whether to persist it as well is a plan decision; the CAS writer is `write_lanes_json_if_bytes_match`.

## Rollback door ordering (load-bearing)
- `capture_pre_mutation_snapshot` is keyed on `lanes_manifest.target_branch`. The retarget must therefore be in effect in memory, in the manifest and in a fresh record, BEFORE the snapshot, so the NEW target's pre-retarget tip is captured.
- The retarget commit is the first statement inside the rollback `try` in `executor` (before `_phase_merge_lanes`). It is recorded through `run_state._records_post_mutation_tips` or `rollback.note_advance_intent`; otherwise it reads as an unexplained move.
- `rollback_to_snapshot` restores the NEW target's ref to its snapshot tip, which undoes the meta commit. The old recorded target is never written, so it needs no restore.
- `ConsolidationState` gains a `retarget` field, defaulted in `from_dict`.

## Resume, abort and guards
- On resume, the persisted `state.target_branch` already equals the new value in meta.
- The entry guards (`entry_preflight`, `forecast`, `orchestrator_api`) re-read meta. After the commit they see the new target, so a resume is not a retarget. On a resume they must not misfire.

## Provenance
- **Actor:** `done_bookkeeping._resolve_merge_actor` (`SPEC_KITTY_AGENT`, git `user.name`, ...).
- **Operator reason:** follows the attestation pattern (`OPERATOR_REASON_SOURCE`).
- **History:** a bounded history follows `record_acceptance` / `acceptance_history` (`HISTORY_CAP`); a new optional meta key goes in `MissionMetaOptional`.
