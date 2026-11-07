---
affected_files: []
cycle_number: 2
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T14:15:18Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP09
---

# WP09 review cycle 2: changes requested (reviewer-renata), one required out-of-map fix

All four cycle-1 blockers are fixed. Verified independently:

1. Sparse policy: `_policy_from_meta` covers every Mission with a slug. The expected patterns come from `lane_mission_dir_name_from_meta` + `lane_status_exclusion_patterns`, the derivation the helper writes with. The match is exact. Every route passes the `implement` and `consolidate` preflight, and an operator `!src/` pattern stays refused. The coordination-topology patterns are byte-identical to the old ones, so existing lanes still read as MANAGED_LANE.
2. Index regeneration: the scratch Mission dir has the same name and carries the index `meta.json` and the stage-2 snapshot. The result is byte-identical to an in-place `reconcile_status_snapshot`, `mission_type` is kept, nothing is written into the checkout, and `notify_written` does not fire.
3. Deletion scope: the deleted symbols (`create_wp_workspace`, `create_feature_worktree`, `setup_feature_directory`, `_exclude_from_git`, `GitVCS.create_workspace` + protocol stub, `GitPreflightError`) had no production caller outside the deleted chain at 77d765b3ee. No reference remains in src/, the tests or the skills. Only historical `kitty-specs/`, `.kittify/evidence`, `docs/reports` and `.github/ci-shard-timings.json` still mention them. The `pyproject.toml` and `ci-windows.yml` edits are minimal (only the deleted files' entries). The gate allowlist holds three non-lane entries and no lane entry.
4. One exclusion authority: `exclude_lane_status_files`. The `workspace.py` registrars are deleted.
5. The CPU-time budget is justified honestly (1.2 s alone, 7.4 s wall clock under `-n 8`).

## Blocking (required out-of-map fix, from WP08 commit bcc5274731, which this lane contains)

`tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported` is RED on this lane. It is red at bcc5274731 too, so WP08 introduced it:

    - specify_cli.lanes.for_review_gate::LANE_BRANCH_MISSING
    - specify_cli.lanes.for_review_gate::LANE_NO_COMMIT_BEYOND_BASE

Neither `GateDecision.reason_code` nor these constants has a production reader. Fix: delete the two names from `__all__` in `src/specify_cli/lanes/for_review_gate.py` (2 lines). Both stay as module constants, which the gate's own `evaluate_for_review_gate` references, and that satisfies the gate (its fix option 2). Do not allowlist them. Record it as an out-of-map edit and re-run the gate file.

## Non-blocking

- The ADR text still says the helper covers "the printed recreate command" (2026-04-03-1:240, 2026-07-29-1:296). The `landed_worktrees` hint is allowlisted as non-lane and spec-kitty never runs it. Name it as the one exception, or drop the phrase.
- `tests/git_ops/test_git.py::test_create_workspace_with_base_branch` now exercises a raw-git helper, not product code. Its docstring still names `create_workspace`. Consider deleting or renaming it.
- Deleting about 1,500 test lines changes the per-module collected counts. `test_module_length_agreement.py` timed out locally (environmental, the whole-repo collect is over 240 s). Make sure CI's length-agreement gate is checked or the timings are recaptured.
