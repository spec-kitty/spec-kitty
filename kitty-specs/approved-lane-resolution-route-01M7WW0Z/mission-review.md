# Mission review: approved-lane-resolution-route-01M7WW0Z (#5604)

- **Reviewed head:** `fix/approved-lane-resolution-route` at `3b2b98fa66` (PR #7886, draft). This is the consolidated, re-signed squash landing, rebased onto `origin/main` `75b829eaff`, plus the fold of the adversarial review.
- **Reviewer:** `claude::architect-alphonso` (orchestrating session). The per-WP reviews were done by a separate session (`claude::reviewer-renata`).
- **Machine report:** `mission-review-report.md` (`spec-kitty review`, post-merge mode): `pass_with_notes`.

## Verdict

**PASS with notes.**
- All 13 FRs trace to tests, and those tests were red before the fix.
- No constraint is violated.
- The notes below are tool false positives or residuals that are recorded and filed.

## FR → evidence

| FR | Evidence (tests) | Drift |
|---|---|---|
| FR-001 runnable re-review route | `tests/lanes/test_approved_lane_stale_remedy.py::test_every_printed_route_command_runs_and_the_mission_lands`; terminus route E2E | None. Since fold F1, the route support runs `move-task --to for_review` exactly as printed. |
| FR-002 exact siblings | `tests/terminus/test_approved_lane_resolution_route_three_lane.py` | None |
| FR-003 halt reason | `test_conflict_halt_lists_exactly_the_conflicted_paths`, `test_7755_stale_sibling_lane_recovery.py` | Fold F4 renamed the source-conflict test so its name matches what it pins. |
| FR-004 claim-time refusal | `test_resolution_merge_unreviewed.py`, `tests/orchestrator_api/test_consolidate_mission_resolution_merge.py` | Fold A2 narrowed the recorded-merge skip; see FR-005. |
| FR-005 durable tool record | `test_auto_rebase_record.py`, `test_recorded_merge_resolution_5604.py`, `test_auto_rebase_merge_attribute_guard.py` | **Intended change:** the claim skips a recorded merge only when its resolution is attributable to a parent or to the pre-run target tip. The contract and ADR `2026-10-04-5` were amended, and the acceptance evidence re-recorded. |
| FR-006 re-review hint | `test_unreviewed_merge_hint.py` | None |
| FR-007 review context lists merges | `tests/review/test_review_context_merge_lines.py` | None |
| FR-008 route end to end (squash + merge) | `tests/terminus/test_approved_lane_resolution_route*.py`, with no xfail or skip | None |
| FR-009 rollback own lane moves | `test_rollback_own_lane_moves.py`; three-lane rollback re-run | None |
| FR-010 fail-closed merge probes | `test_merge_attribute_guard.py`, `test_auto_rebase_merge_attribute_guard.py`, `test_5604_auto_rebase_merge_attributes_e2e.py` | Fold changes I1–I3, A1 and R1 strengthen it: the guard runs in the merging checkout, config reads are live, there is one attribute source, there is one env builder, and porcelain reads ignore signatures. |
| FR-011 canceled via re-approved dependency | `test_canceled_via_reapproved_dependency_7497.py`, including `test_protection_is_load_bearing` | None |
| FR-012 non-vacuous #7307 tests | `test_dependency_merge_attribution_7307.py` | After the rebase, main's one-side controls assert the claim refusal and then the gate FAIL, with the claim bypassed. |
| FR-013 ADR / doc amendments | ADRs 2026-10-04-5, 2026-09-29-1, 2026-09-19-1, 2026-11-08-2; AGENTS.md; `troubleshoot-merge.md`; orchestrator-api docs; changelog fragment | None |

**NFRs**
- **NFR-001:** the count tests in `test_7689_git_read_cache_call_sites.py` cover it, and `test_git_version_is_read_once_per_run_scope` was extended in fold F5.
- **NFR-002:** probe errors refuse. This is covered in the guard, record and rollback tests.
- **NFR-003:** ruff, format and C901 are clean across the whole repository, and mypy shows 0 new errors.
- **NFR-004:** each WP has red-first evidence in its review history, and each fold finding has red-first evidence in the PR #7886 review comment.

**Constraints**
- **C-001, C-002, C-003, C-004:** hold. No attestation lifts `RESOLUTION_MERGE_UNREVIEWED`, and the record is never read by the gate.
- **C-005:** scope held. #7324 and #7766 are left alone.
- **C-006:** one rollback authority, pinned by the AST gate.
- **C-007:** orchestrator-api contract 1.31.0.

## Machine-report findings

The dead-code scan flagged 10 symbols, all false positives:
- **Eight symbols in this Mission's code** are used inside their own modules: `kept_one_side`, `MergeAttributeRefused`, `RegisteredDriver`, `merge_probe_env`, `wp_windows`, `recorded_merges`, `merge_message`, `resolution_command`. `tests/architectural/test_no_dead_symbols.py` passes.
- **Two migration classes** (`m_4_0_0rc9_*`) came in from `main` through the rebase. The migration registry loads them dynamically.

## Risks and residuals

- **Merge the auto-rebase makes after the claim.** It is judged only at the gate: a novel resolution FAILs and is rolled back, with no exit 0. This is recorded in ADR `2026-10-04-5` Amendment 2026-11-26.
- **#7880:** a stale lane that depends on the sibling it must incorporate meets the dependency self-heal first. This is a usability gap only; the operator ruled it deferred.
- **CLI gaps found during closeout:**
  - #7884: `spec-commit` and squad records;
  - #7885: `accept --mode auto` on a coordination Mission;
  - #7887: the squash landing re-materializes other Missions' `status.json`;
  - #7838 (comment): superseded lanes kept after a verified squash landing.
- **Security:** integrity is the point of this change. The attacker lens did not show unreviewed content landing with exit 0. Its MED findings (I1, I2) and the reviewer's R1 are folded with red-first tests.

## Follow-ups

#7766, #7864, #7866, #7880, #7884, #7885, #7887, and #7838 (comment). All are filed. Nothing new comes from this review.
