---
work_package_id: WP17
title: History and support module conversion
dependencies:
- WP04
- WP07
- WP13
- WP14
- WP15
- WP16
requirement_refs:
- FR-001
- FR-022
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T090
- T091
- T092
- T093
- T094
phase: Phase 4 - Conversion sweep
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/test_owned_history_support.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/tasks/issue_matrix.py
- src/specify_cli/review/cycle.py
- src/specify_cli/consolidation/baseline.py
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/missions/_read_path_resolver.py
- src/specify_cli/migration/runtime_state_cutover.py
- src/specify_cli/migration/backfill_runtime_state.py
- tests/specify_cli/test_owned_history_support.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP17 – History and support module conversion

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. The charter (`.kittify/charter/charter.md`) is binding.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This is the support-module tail of IC-10b: the issue matrix, the review cycle, the consolidation baseline, the commit helper, the read-path resolver and the two runtime-state migrations. It is a **behaviour-preserving signature migration**; the proof is each module's existing tests passing unchanged plus `mypy --strict`.

Done means:

1. The seven owned files contain **zero** occurrences of the identifier `effective_root`, zero `effective_root_kwargs`, zero `OwnedMission` references, and zero legacy attribute reads on the fact (`.root`, `.primary`, `.directory`, `.slug`, `.target`).
2. Every converted function takes `owned: OwnedCheckout | None = None` (keyword-only, default `None`) where it took `effective_root: Path | None` or `owned: OwnedMission | None`; `safe_commit`'s dead `effective_root` parameter is deleted, not converted (T093).
3. `create_rejected_review_cycle` (complexity 12) is campsite-extracted before its signature changes and stays ≤ 15, like every function you touch.
4. Every existing test of these modules passes unchanged; the only existing-test edit allowed is the single out-of-map re-point in T092 (explained there).
5. **Owned-arm tests (non-vacuity).** Every converted function has a focused owned-arm test in the new file `tests/specify_cli/test_owned_history_support.py`: with a stale copy of M in R, the function called with `owned=fact` produces its output under P and **nothing** under R. Each is committed **red before** its conversion commit (on the red commit it fails with `TypeError` for `owned=` or with an R path), and the reviewer verifies the order in `git log`.
6. ruff check, ruff format, `mypy --strict` clean on the touched files; `make test-fast` green.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP17 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Mission docs**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/` → `spec.md` (FR-001, FR-022), `plan.md` (Staging Strategy; IC-10b lists exactly these modules; Campsite list names `create_rejected_review_cycle` at 12), `research.md` R-03, `contracts/architectural-gate.md` (G4/G5), `contracts/owned-checkout-carrier.md` §3, `data-model.md`, `occurrence_map.yaml`.
- **Landed prerequisites** (verify shapes on your lane base):
  - WP01 `from mission_runtime import OwnedCheckout` (public import only; MR-1/MR-2). Canonical fields `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology`, `target_branch`; the legacy properties are deleted by WP18, so never read them.
  - WP04 `placement_seam(..., owned=)` (dual keyword until WP18) and the converted `mission_runtime.resolve_artifact_surface` (verify: if it still takes only `effective_root`, use the bridge rule).
  - WP07 `agent_tasks_ports.MissionHandle(owned=)`, `coordination/write_seam.write_artifact(owned=)`, `coordination/commit_router` and `status/transition_pipeline` conversions.
- **Callee rule.** For each call out of these files: callee takes `owned` → `owned=owned`; callee is a dual-keyword seam → `owned=owned` (never the legacy keyword); callee still takes only `effective_root` → bridging keyword `effective_root=owned.owned_root if owned else None` as a plain keyword, marked `# bridging: WP<n> converts` naming the callee's owner (after WP17, only WP18 remains), and logged in the Activity Log.
- **Caller rule (cross-WP call sites).** Converting a public function breaks callers that pass the old keyword. On the planning base:

  | Callee (this WP) | Caller passing the keyword | Caller's WP | Dependency of WP17? |
  |---|---|---|---|
  | `scaffold_issue_matrix` | `cli/commands/agent/mission_finalize.py:922-930` (`**({"effective_root": owned.root} if owned else {})`) | WP13 | yes |
  | `create_rejected_review_cycle` | `cli/commands/agent/tasks_verdict_persistence.py:901, 936` | WP16 | yes |
  | `verify_pr_merge_evidence` | `cli/commands/accept.py:906` (`**scope`) | WP14 | yes |
  | `record_pr_merge_baseline_for_mission` | `cli/commands/accept.py:398-402` | WP14 | yes |
  | `stamp_accept_cutover` | `cli/commands/accept.py:346` (already passes `owned`) | WP14 | yes (type-only change, no call break) |
  | `resolve_subtasks_gate_dir` | `status/transition_pipeline.py:102` | WP07 | yes |
  | `safe_commit` | `coordination/commit_router.py:438`, `coordination/transaction.py:836` | WP07, WP06 | yes (WP06 via WP07) |

  For callers whose WP is a dependency (already merged), change the call expression to `owned=...` (or delete the keyword, for `safe_commit`) as a **one-line out-of-map edit**, with the rationale "WP17 converted the callee; caller already holds the fact" in the commit message and Activity Log. For callers whose WP is **not** a dependency, check your lane base with `git log --oneline`: if that WP has merged, make the same one-line out-of-map edit; if not, do **not** touch the caller file (a parallel lane owns it) — convert everything else, leave that public signature for last, and ask the orchestrator to sequence (record it in the Activity Log). Callers that pass no keyword (`issue_verdict.py`, `issue_matrix_migration.py`, `tasks_materialization.py:234`, `migrate_cmd.py`, `consolidation/executor.py`, `consolidation/ordering.py`, `_cutover_doctor.py`, `upgrade/migrations/m_zz_runtime_state_backfill.py`, `status/cutover_eligibility.py`) are unaffected.
- **Behaviour preservation.** The owned arms and the non-owned arms of each function stay as they are; only the parameter's type and the forwarding keyword change. `serialized_keys`/`logs_telemetry` are `do_not_change` (issue-matrix JSON, review-cycle frontmatter, `meta.json` fields, `pr_merge_evidence`, error messages such as "Owned issue matrix write failed.").
- **Terminology (C-008)**: update docstring sentences that name the removed parameter to "owned checkout"; no "feature", no bare "primary" as a checkout alias in new prose (existing `PRIMARY` partition vocabulary stays).
- **No suppressions**; complexity ≤ 15.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: assigned in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json` by `spec-kitty agent mission finalize-tasks`. Start with `spec-kitty implement WP17` and use only the workspace path it prints.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Occurrence census (planning base `df1588860`)

```bash
F="src/specify_cli/tasks/issue_matrix.py src/specify_cli/review/cycle.py src/specify_cli/consolidation/baseline.py \
   src/specify_cli/git/commit_helpers.py src/specify_cli/missions/_read_path_resolver.py \
   src/specify_cli/migration/runtime_state_cutover.py src/specify_cli/migration/backfill_runtime_state.py"
grep -nw "effective_root\|effective_root_kwargs\|OwnedMission" $F
grep -nE "owned\.(root|primary|directory|slug|target)\b" $F
```

Planning-base identifier lines: `issue_matrix.py` 8, `review/cycle.py` 15, `consolidation/baseline.py` 17, `git/commit_helpers.py` 2, `missions/_read_path_resolver.py` 3, `migration/runtime_state_cutover.py` 10, `migration/backfill_runtime_state.py` 5. The end state is empty apart from logged bridges.

## Subtasks & Detailed Guidance

### Owned-arm tests (apply to every subtask T090–T094)

- **File:** `tests/specify_cli/test_owned_history_support.py` (new; markers `integration` + `git_repo`). The WP02 fixtures live in `tests/integration/conftest.py`, so import `owned_checkouts`, `stale_root_copy` and `r_snapshot` explicitly and re-export them through `__all__` (the pattern of `tests/integration/test_owned_checkout_mark_status.py:13-22`); never import a test module.
- **One test per converted function** (the census below lists them per file). Each test mints the fact with the WP02 helper (real validator), activates `stale_root_copy`, calls the function with `owned=fact`, and asserts: the output (written file, returned path, or recorded ref) is under P; nothing is under R (`Path.is_relative_to`, excluding P's subtree when P is under R); `r_snapshot` shows 0 differences.
- **Red-first per subtask:** commit the tests for a subtask's functions before that subtask's conversion commit. On the red commit they fail with `TypeError` (no `owned=`) or with an R path; record the reason in the commit message.
- Functions whose output is not path-shaped (for example a pure predicate) assert on the P-derived value instead, and say so in the test docstring.


### Subtask T090 – Convert `tasks/issue_matrix.py`

> **Carry-forward from WP13.** WP13 added an additive `fold_into_caller_commit` keyword to `scaffold_issue_matrix`, so that finalize's issue-matrix scaffold rides the single final commit. T090's conversion to `owned=` must keep that keyword and its behaviour, including the tests in `tests/specify_cli/tasks/test_issue_matrix_scaffold.py`. It must also convert the `# bridging: WP17 converts` call site in `mission_finalize.py`. When T090 converts `placement_seam(..., effective_root=)` to `owned=`, it must also drop the `("candidate_feature_dir_for_mission", "_compose_primary_feature_dir"): 4` row from `_RESOLVER_READ_LEDGER` in `tests/integration/test_owned_lifecycle_acceptance_finalize.py`. The ledger asserts equality, and those 4 reads, which take R's stored topology from `meta.json`, disappear with the bridge.

- **Purpose**: the issue-matrix writer and its finalize-time scaffold thread the owned root into the write seam and the placement seam. Owned `finalize-tasks` (O6) writes the issue matrix through here, so a missed site would write it into the repository root checkout.
- **Steps**:
  1. Import (`:51`): replace `from specify_cli.core.owned_mission import effective_root_kwargs` with `OwnedCheckout` from `mission_runtime` (follow the module's `TYPE_CHECKING` style if it has one).
  2. `write_issue_matrix` (`:350-405`):
     - the parameter at `:358` becomes `owned: OwnedCheckout | None = None`;
     - `:393-404` `write_artifact(..., effective_root=effective_root)` (the keyword is on `:403`) → `owned=owned` (WP07 `write_seam`; callee rule).
  3. `scaffold_issue_matrix` (`:437-513`):
     - the parameter at `:445` becomes `owned`;
     - `:478` `if effective_root is not None:` → `if owned is not None:`;
     - `:481` `placement_seam(repo_root, mission_slug, effective_root=effective_root)` → `owned=owned`;
     - `:495-503` `write_issue_matrix(..., **effective_root_kwargs(effective_root))` → `owned=owned`;
     - `:511` `if effective_root is not None: raise RuntimeError(result.diagnostic or "Owned issue matrix write failed.")` → `if owned is not None:` with the same message.
  4. Update docstrings that name the removed parameter.
  5. Apply the caller rule for `cli/commands/agent/mission_finalize.py:922-930` (WP13), which passes `**({"effective_root": owned.root} if owned else {})`.
  6. Commit: `refactor(tasks): issue matrix takes the OwnedCheckout fact (WP17/T090)`.
- **Files**:
  - `src/specify_cli/tasks/issue_matrix.py`
  - Possibly one call in `src/specify_cli/cli/commands/agent/mission_finalize.py` (out-of-map, only after WP13 merged).
- **Parallel?**: `[P]`.
- **Validation checklist**:
  - [ ] `tests/specify_cli/tasks/test_issue_matrix_scaffold.py`, `test_issue_matrix_structured.py`, `test_issue_ref_url_provenance.py` pass unchanged.
  - [ ] `tests/mission_runtime/test_issue_matrix_content_source.py`, `tests/mission_runtime/test_issue_matrix_ref_read.py` pass unchanged.
  - [ ] `tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py`, `test_zero_reference_not_applicable.py`, `tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py` pass unchanged.
  - [ ] `tests/integration/test_issue_verdict_concurrent_lock.py`, `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py`, `tests/policy/test_issue_matrix_cross_site_consistency.py`, `tests/tasks/test_issue_reference_classification.py` pass unchanged.
  - [ ] `tests/integration/test_explicit_checkout_commands.py::test_finalize_issue_matrix_uses_owned_writer` passes unchanged.
- **Edge cases**:
  - The non-owned arm uses `coord_read_dir_for(...) or feature_dir`; the owned arm uses the placement seam's `ISSUE_MATRIX` read dir. Keep both.
  - The idempotent early return (existing JSON or legacy `.md`) must fire before any write in both arms.
  - `write_issue_matrix` has non-owned callers (`cli/commands/agent/issue_verdict.py`, `tasks/issue_matrix_migration.py`) that pass no keyword; they are unaffected.

### Subtask T091 – Campsite plus conversion: `review/cycle.py`

- **Purpose**: the review-cycle writer is on the owned review path (`move-task --to planned` with feedback, the rejection cycle). `create_rejected_review_cycle` is at complexity 12 and is in the plan's campsite list; tidy it first, then convert.
- **Steps**:
  1. **Campsite commit first** (behaviour-preserving, no signature change). The expression `effective_root or main_repo_root` is computed in three functions: `_commit_review_cycle_artifact` (`:705`), `_adopt_or_allocate_review_cycle_locked` (`:1010`) and `create_rejected_review_cycle` (`:1179`). Extract one private helper, for example `_operation_root(main_repo_root, ...)`, and any sub-block needed to bring `create_rejected_review_cycle` comfortably under 15. Natural seams: the sub-artifact directory resolution (`:1179-1185`) and the persistence-outcome construction (`:1246-1260`). Commit: `refactor(review): campsite create_rejected_review_cycle before owned conversion (WP17/T091)`.
  2. **Conversion commit**:

     | Line | Function | Change |
     |---|---|---|
     | 179 | `_review_cycle_wp_dir(..., effective_root)` | param → `owned`; `:281` `placement_seam(..., effective_root=effective_root)` → `owned=owned` |
     | 683 | `_commit_review_cycle_artifact(..., effective_root)` | param → `owned`; `:699` `MissionHandle(effective_root=...)` → `owned=owned` (WP07); `:702-705` operation root via the helper; `:717-718` `placement_seam(effective_root=)` → `owned=owned` |
     | 1001 | `_adopt_or_allocate_review_cycle_locked(..., effective_root)` | param → `owned`; `:1010-1012` operation root and `placement_seam` |
     | 1125 | `create_rejected_review_cycle(..., effective_root)` (public) | param → `owned`; forwards at `:1180`, `:1231`, `:1246`, `:1272`; operation-root reads `:1179, 1184, 1240, 1247, 1280` |

  3. The operation-root helper returns `owned.owned_root if owned is not None else main_repo_root`. If you bind its result to a local, do not call it `effective_root` or annotate it as an owned root (gate G4 bans the identifier everywhere in `src/`; G5 scans parameters and fields).
  4. Apply the caller rule for `cli/commands/agent/tasks_verdict_persistence.py:901, 936` (WP16). `tasks_materialization.py:234` and `tasks_move_task.py` call it without the keyword and are unaffected.
  5. Update the docstrings of the four functions to describe `owned`.
- **Files**:
  - `src/specify_cli/review/cycle.py`
  - Possibly two calls in `src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py` (out-of-map, only after WP16 merged).
- **Parallel?**: No internal dependency on the other subtasks.
- **Validation checklist**:
  - [ ] `uv run --frozen ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' src/specify_cli/review/cycle.py` is clean, and `create_rejected_review_cycle` is below its planning-base 12.
  - [ ] `tests/review/test_cycle.py`, `tests/specify_cli/review/test_cycle_kind_flip.py`, `tests/review/test_artifacts.py`, `tests/review/test_arbiter.py` pass unchanged.
  - [ ] `tests/review/test_verdict_status_lock_bound.py`, `tests/review/test_verdict_save_performance.py`, `tests/mission_runtime/test_coord_read_seam_callers.py`, `tests/agent/test_workflow_review_cycle_pointer.py` pass unchanged.
  - [ ] `tests/architectural/test_single_mission_surface_resolver.py` still passes (it pins the review-cycle sub-artifact routing).
  - [ ] The campsite commit alone passes the same list before the conversion commit.
- **Edge cases**:
  - The commit retry loop in `_commit_review_cycle_artifact` (`attempt` counter) keeps its exact retry semantics.
  - `evidence_ref` is computed relative to the operation root; for owned runs that stays the owned checkout, so evidence paths remain relative to P.
  - `tests/mission_runtime/test_coord_read_seam_callers.py:262, 271, 330` build `MissionHandle(..., effective_root=...)` for this module's callers; that is WP07's `MissionHandle` shape — if it is red after WP07, report it (WP18/T097 re-points leftovers), do not edit it here.

### Subtask T092 – Convert `consolidation/baseline.py`

- **Purpose**: `accept --mode pr --merge-commit` records the PR merge baseline from the owned checkout's own `meta.json`. That declared-target read and the write leg are threaded through `effective_root` today (#4231 fold).
- **Steps**:
  1. Convert the five functions; each `effective_root` parameter becomes `owned: OwnedCheckout | None = None`:

     | Line | Function | Forwards / reads |
     |---|---|---|
     | 447 | `_resolve_pr_target_ref` | `:476` `resolve_primary_meta_dir(..., effective_root=effective_root)` |
     | 497 | `verify_pr_merge_evidence` (public) | `:617` `_resolve_pr_target_ref(..., effective_root=effective_root)` |
     | 724 | `_record_pr_merge_baseline` | `:759` `verify_pr_merge_evidence(effective_root=)`; `:765` read |
     | 792 | `resolve_primary_meta_dir` (public) | `:804` lazy import of `effective_root_kwargs`; `:806` `placement_seam(**effective_root_kwargs(effective_root))` → `placement_seam(..., owned=owned)` |
     | 814 | `record_pr_merge_baseline_for_mission` (public) | `:833, 834, 841` forwards |

  2. Delete the lazy `effective_root_kwargs` import at `:804`.
  3. Update the docstrings at `:466` and `:828-831` to describe `owned` ("the owned checkout's own `meta.json`").
  4. Apply the caller rule for `cli/commands/accept.py:398-402` and `accept.py:906` (WP14). `cli/commands/migrate_cmd.py` calls `verify_pr_merge_evidence`, `record_pr_merge_baseline_for_mission` and `resolve_primary_meta_dir` without the keyword and is unaffected.
  5. **Out-of-map test re-point (the one test edit this WP makes).** `tests/consolidation/test_pr_merge_baseline.py:842-894` (`test_verify_effective_root_resolves_declared_target_from_owned_checkout`) calls `verify_pr_merge_evidence(..., effective_root=worktree_root)` directly. No WP owns that file, and the call cannot survive the signature change.
     - Re-point exactly that one call to `owned=<fact>`.
     - Build the fact with the WP02 test helper for minting a fact in tests: the checkout in that test is a bare `git worktree add` on branch `owned-checkout` without an ownership claim, so the production validator would refuse it. Never call `OwnedCheckout._mint` (gate G3).
     - Keep the test name, the docstring's intent and both assertions unchanged.
     - Rationale for the commit message and the Activity Log: "WP17: verify_pr_merge_evidence now takes the validated fact; the one direct unit call is re-pointed; assertions unchanged (FR-022)."
  6. Commit: `refactor(consolidation): PR-merge baseline takes the OwnedCheckout fact (WP17/T092)`.
- **Files**:
  - `src/specify_cli/consolidation/baseline.py`
  - `tests/consolidation/test_pr_merge_baseline.py` (one call, out-of-map)
  - Possibly two calls in `src/specify_cli/cli/commands/accept.py` (out-of-map, only after WP14 merged)
- **Parallel?**: `[P]`.
- **Validation checklist**:
  - [ ] `tests/consolidation/test_pr_merge_baseline.py` (all tests) and `tests/consolidation/test_baseline_committed_meta_decode.py` pass.
  - [ ] `tests/specify_cli/cli/commands/review/test_dead_code_baseline.py`, `tests/specify_cli/cli/commands/test_accept_merge_commit.py`, `tests/cli/commands/test_merge_status_commit.py`, `tests/consolidation/test_merge_done_recording.py` pass unchanged.
  - [ ] `git diff -- tests/consolidation/test_pr_merge_baseline.py` touches only the one call plus the fact construction lines.
  - [ ] `grep -nw "effective_root\|effective_root_kwargs" src/specify_cli/consolidation/baseline.py` prints nothing.
- **Edge cases**:
  - The bare (non-owned) call in the same test must still raise `PrMergeEvidenceError` for the bogus repository-root target branch; that proves the owned arm reads P's `meta.json`, which is the whole point of the arm.
  - `record_pr_merge_baseline_for_mission` resolves both the write leg's `feature_dir` and the declared-target read from the same `owned`; they must never resolve different `meta.json` files.
  - `verify_pr_merge_evidence` is read-only git; keep it free of writes in both arms (`--diagnose` / `--no-commit` rely on that).

### Subtask T093 – Convert `git/commit_helpers.py`, `missions/_read_path_resolver.py`

- **Purpose**: two small, isolated sites. `safe_commit` accepts an `effective_root` it immediately discards (`del effective_root` at `commit_helpers.py:1091`, "Compatibility-only routing hint after retirement of the ambient sync emitter"), so the right conversion is deletion. `resolve_subtasks_gate_dir` is on the status-transition subtask gate.
- **Steps**:
  1. `git/commit_helpers.py`: delete the `effective_root: Path | None = None` parameter (`:1003`) and the `del effective_root` line with its comment (`:1090-1091`). Do not add an `owned` parameter: nothing in `safe_commit` uses the owned checkout, and FR-001 bans bare owned roots, not missing dead parameters.
  2. Remove the keyword from its two callers. Both are in merged prerequisite WPs; each is a one-line out-of-map edit with the rationale "dead parameter deleted in `safe_commit` (WP17/T093)":
     - `coordination/commit_router.py:438` (`**effective_root_kwargs(effective_root)` on the planning base; WP07 may already have changed it — delete whatever owned-root keyword it now passes to `safe_commit`);
     - `coordination/transaction.py:836` (`effective_root=self.worktree_root if self._primary_root is not None else None`).
  3. Confirm no other caller passes it: `grep -rn -A10 "safe_commit(" src --include=*.py | grep effective_root` (30 call sites on the planning base; only those two pass it). Check tests too: `grep -rln "safe_commit(" tests --include=*.py | xargs -r grep -ln effective_root` (none on the planning base).
  4. `missions/_read_path_resolver.py`, `resolve_subtasks_gate_dir` (`:1478-1530`):
     - the parameter at `:1485` becomes `owned: OwnedCheckout | None = None`;
     - `:1520` `if effective_root is not None:` → `if owned is not None:`;
     - `:1523-1524` `placement_seam(primary_root, mission_slug, effective_root=effective_root)` → `owned=owned`.
  5. Its caller `status/transition_pipeline.py:102` (WP07, merged): switch the keyword to `owned=` in a one-line out-of-map edit if WP07 left a bridge there. `status/emit.py:695` only mentions it in a docstring.
  6. Commit: `refactor(git,missions): drop dead safe_commit effective_root; subtasks gate dir takes the fact (WP17/T093)`.
- **Files**:
  - `src/specify_cli/git/commit_helpers.py`, `src/specify_cli/missions/_read_path_resolver.py`
  - Out-of-map one-liners: `src/specify_cli/coordination/commit_router.py`, `src/specify_cli/coordination/transaction.py`, `src/specify_cli/status/transition_pipeline.py`
- **Parallel?**: `[P]`.
- **Validation checklist**:
  - [ ] `uv run --frozen mypy --strict src/specify_cli/git/commit_helpers.py` (it is in the `make typecheck` target) plus the multi-file command in Test Strategy.
  - [ ] `tests/git_ops/test_safe_commit_helper_integration.py`, `tests/git_ops/test_safe_commit_commit_failure_classification.py`, `tests/integration/git/test_safe_commit_backstop.py`, `tests/git/test_guard_capability_regression.py`, `tests/git/test_protection_preserved.py` pass unchanged.
  - [ ] `tests/specify_cli/status/test_subtasks_gate_dir_seam.py`, `tests/specify_cli/status/test_infer_subtasks_primary.py`, `tests/specify_cli/missions/test_read_path_resolver_redundant_cast_gate.py`, `tests/task_utils/test_set_scalar_retired.py` pass unchanged.
  - [ ] `tests/architectural/test_no_read_side_bypass.py` passes (it references `resolve_subtasks_gate_dir`).
  - [ ] `tests/specify_cli/coordination/test_commit_router_partition.py` and `tests/specify_cli/coordination/test_status_transition.py` pass (callers of `safe_commit`).
- **Edge cases**:
  - `_read_path_resolver.py` is referenced by 110 test files; most do not exercise `resolve_subtasks_gate_dir`. Run the targeted list above plus `make test-fast`, not all 110.
  - `safe_commit` is also reached through `destination_ref`/`target` compatibility handling right below the deleted line; do not touch that shim (out of scope, separate retirement).
  - If WP06/WP07 already dropped the keyword at their call sites, steps 2-3 reduce to the grep confirmation; record that in the Activity Log instead of making an empty edit.
  - `resolve_subtasks_gate_dir` has a `primary_root is None` fallback through `resolve_canonical_root(feature_dir)` before the owned branch; keep that order, so an owned call with no primary root still resolves the root first.

### Subtask T094 – Convert `migration/runtime_state_cutover.py`, `migration/backfill_runtime_state.py`

- **Purpose**: the birth-cutover and backfill already receive the validated value object (`owned: OwnedMission | None`, #3866). Here the conversion is a type change, canonical attribute names, removal of the `{"owned": owned}` splats, and one owned-root keyword. The accept flow (WP14) and owned finalize depend on these legs writing only into P.
- **Steps**:
  1. `runtime_state_cutover.py` import: the `TYPE_CHECKING` block at `:50-51` becomes `from mission_runtime import OwnedCheckout` (keep it under `TYPE_CHECKING` unless runtime needs it).
  2. Retype `owned: OwnedMission | None` → `OwnedCheckout | None` in:
     - `_seed_phase` (`:129`), `_verify_phase` (`:149`);
     - `_resolve_primary_home_or_degrade` (`:199`), `_flip_target` (`:253`);
     - `_already_at_snapshot_authority` (`:271`), `_flip_phase` (`:291`);
     - `cutover_mission` (`:347`), `stamp_accept_cutover` (`:486`).
  3. `_resolve_primary_home_or_degrade` `:226-230`: `resolve_artifact_surface(owned.primary, owned.slug, MissionArtifactKind.PRIMARY_METADATA, effective_root=owned.root)` → `resolve_artifact_surface(owned.repository_root, owned.mission_slug, MissionArtifactKind.PRIMARY_METADATA, owned=owned)` (callee rule for `resolve_artifact_surface`).
  4. `cutover_mission` `:406`: delete `scope = {"owned": owned} if owned is not None else {}` and pass `owned=owned` at `:413`, `:421`, `:435`, `:448`. Every callee already defaults `owned=None`, so the plain keyword is equivalent.
  5. `backfill_runtime_state.py` import: the `TYPE_CHECKING` block at `:84-85` becomes `OwnedCheckout`.
  6. Retype `_runtime_feature_dir` (`:1433`), `backfill_runtime_state` (`:1453`), `_invocation_write_refusal` (`:2081`), `verify_backfill` (`:2129`).
  7. `_runtime_feature_dir` `:1445-1447`: `owned.directory` → `owned.mission_dir`. Keep the exact-directory guard and its `OWNED_MISSION_PATH_REFUSED` code unchanged.
  8. `verify_backfill` `:2169-2170`: delete the `scope` splat and pass `owned=owned`.
  9. Update the #3866 comments (`backfill_runtime_state.py:1438-1442` and the equivalent note in `runtime_state_cutover.py`) so they name the fact rather than a re-resolution that no longer exists.
  10. Commit: `refactor(migration): cutover and backfill take the OwnedCheckout fact (WP17/T094)`.
- **Files**:
  - `src/specify_cli/migration/runtime_state_cutover.py`
  - `src/specify_cli/migration/backfill_runtime_state.py`
- **Parallel?**: `[P]`.
- **Validation checklist**:
  - [ ] `tests/specify_cli/migration/` (all), `tests/migration/test_birth_cutover.py`, `tests/migration/test_corpus_frontload_idempotent.py`, `tests/migration/test_runtime_feature_dir_threading.py` pass unchanged.
  - [ ] `tests/integration/test_migration_backfill.py`, `tests/specify_cli/cli/commands/test_backfill_runtime_state_cli.py`, `tests/specify_cli/cli/commands/test_cutover_doctor.py`, `tests/specify_cli/upgrade/test_runtime_state_backfill_migration.py` pass unchanged.
  - [ ] `tests/specify_cli/cli/test_accept_birth_cutover.py`, `tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py` pass unchanged.
  - [ ] `tests/integration/test_explicit_checkout_commands.py::test_accept_commits_metadata_matrix_and_cutover_only_in_owned` passes unchanged.
  - [ ] `grep -nw "OwnedMission\|effective_root" src/specify_cli/migration/runtime_state_cutover.py src/specify_cli/migration/backfill_runtime_state.py` prints nothing.
- **Edge cases**:
  - `tests/migration/test_runtime_feature_dir_threading.py:16-38` constructs `OwnedMission(...)` directly and asserts `_runtime_feature_dir(owned.directory, owned) == owned.directory`. You do not own that file. WP02's transitional `OwnedMission` legacy factory function mints a real `OwnedCheckout` (which exposes `mission_dir`), so it keeps passing; if it goes red, report it in the Activity Log (do not edit the file). WP18/T097 re-points every remaining `OwnedMission` test construction when the factory is deleted.
  - `_runtime_feature_dir` is called for both the PRIMARY and the status leg in `cutover_mission` (`:409-410`); both must stay anchored to `owned.mission_dir`.
  - The backfill's foreign-lane write refusal (`_invocation_write_refusal`) must keep returning the same checkout-naming message.

## Test Strategy

Targeted (existing files unchanged except the one T092 re-point; plus the new owned-arm file):

```bash
uv run --frozen pytest -q tests/specify_cli/test_owned_history_support.py
uv run --frozen pytest -q \
  tests/specify_cli/tasks/test_issue_matrix_scaffold.py tests/specify_cli/tasks/test_issue_matrix_structured.py \
  tests/specify_cli/tasks/test_issue_ref_url_provenance.py tests/mission_runtime/test_issue_matrix_content_source.py \
  tests/mission_runtime/test_issue_matrix_ref_read.py tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py \
  tests/specify_cli/cli/commands/review/test_zero_reference_not_applicable.py tests/integration/test_issue_verdict_concurrent_lock.py \
  tests/integration/test_issue_verdict_coord_legacy_md_preservation.py tests/policy/test_issue_matrix_cross_site_consistency.py \
  tests/tasks/test_issue_reference_classification.py \
  tests/review/test_cycle.py tests/specify_cli/review/test_cycle_kind_flip.py tests/review/test_artifacts.py \
  tests/review/test_arbiter.py tests/review/test_verdict_status_lock_bound.py tests/review/test_verdict_save_performance.py \
  tests/mission_runtime/test_coord_read_seam_callers.py tests/agent/test_workflow_review_cycle_pointer.py \
  tests/consolidation/test_pr_merge_baseline.py tests/consolidation/test_baseline_committed_meta_decode.py \
  tests/specify_cli/cli/commands/review/test_dead_code_baseline.py tests/specify_cli/cli/commands/test_accept_merge_commit.py \
  tests/cli/commands/test_merge_status_commit.py tests/consolidation/test_merge_done_recording.py \
  tests/git_ops/test_safe_commit_helper_integration.py tests/git_ops/test_safe_commit_commit_failure_classification.py \
  tests/integration/git/test_safe_commit_backstop.py tests/git/test_guard_capability_regression.py tests/git/test_protection_preserved.py \
  tests/specify_cli/status/test_subtasks_gate_dir_seam.py tests/specify_cli/status/test_infer_subtasks_primary.py \
  tests/specify_cli/missions/test_read_path_resolver_redundant_cast_gate.py tests/task_utils/test_set_scalar_retired.py \
  tests/specify_cli/migration/ tests/migration/test_birth_cutover.py tests/migration/test_corpus_frontload_idempotent.py \
  tests/migration/test_runtime_feature_dir_threading.py tests/integration/test_migration_backfill.py \
  tests/specify_cli/cli/commands/test_backfill_runtime_state_cli.py tests/specify_cli/cli/commands/test_cutover_doctor.py \
  tests/specify_cli/cli/test_accept_birth_cutover.py tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py \
  tests/specify_cli/upgrade/test_runtime_state_backfill_migration.py \
  tests/specify_cli/coordination/test_commit_router_partition.py tests/specify_cli/coordination/test_status_transition.py \
  tests/integration/test_explicit_checkout_commands.py
```

To find any further test for a touched module: `grep -rl "<module_name>" tests --include=*.py` (planning-base counts: `issue_matrix` 16, `review.cycle` 155, `consolidation.baseline` 24, `commit_helpers` 38, `_read_path_resolver` 110, `runtime_state_cutover` 20, `backfill_runtime_state` 28). Run the ones that exercise the functions you changed; `make test-fast` covers the rest of the fast tier.

Specific architectural gates implicated (files, not the directory):

```bash
uv run --frozen pytest -q \
  tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_no_read_side_bypass.py \
  tests/architectural/test_lifted_cli_accept_birth_cutover.py \
  tests/architectural/test_issue_matrix_json_migration_completeness.py \
  tests/architectural/test_owned_checkout_gate_selftest.py
```

Baseline and quality gates:

```bash
make test-fast
uv run --frozen ruff check $F tests/consolidation/test_pr_merge_baseline.py
uv run --frozen ruff format --check $F tests/consolidation/test_pr_merge_baseline.py
uv run --frozen mypy --strict $F src/specify_cli/coordination/commit_router.py src/specify_cli/coordination/transaction.py \
  src/specify_cli/status/transition_pipeline.py src/specify_cli/cli/commands/accept.py \
  src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py src/specify_cli/cli/commands/agent/mission_finalize.py
```

(`$F` is the seven-file list from the census.) Callers and callees go into **one** mypy invocation: `follow_imports = "skip"` for `specify_cli.*` makes cross-module keyword mismatches invisible otherwise. Record commands and counts in the Activity Log and the PR's *Tests run* section.

## Risks & Mitigations

- **Cross-WP callers** (WP13, WP14, WP16 call into this WP's modules). They are now dependencies of this WP, so they are merged on your lane base; mitigation: the caller rule in Context (one-line declared out-of-map flips).
- **Dead-parameter deletion touching two other WPs' files** (`safe_commit`). Mitigation: both owners (WP06, WP07) are merged prerequisites; each edit is one line with rationale.
- **Review-cycle retry semantics** during the campsite extraction. Mitigation: separate refactor commit; `tests/review/test_cycle.py` and the verdict durability tests run after each commit.
- **Alias-constructed test objects** (`OwnedMission(...)` in unowned test files). Mitigation: report, do not edit; WP18 owns the final re-point.

## Review Guidance

- Re-run the census; only logged bridges may remain.
- Check that the T091 campsite commit is refactor-only and precedes the conversion.
- Check every out-of-map edit is one line (or one call) with a written rationale, and that none landed in a caller file whose WP had not merged.
- Check the `tests/consolidation/test_pr_merge_baseline.py` diff is limited to the one call and keeps both assertions.
- Confirm the multi-file mypy command ran clean.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-29T13:37:49Z – claude – shell_pid=27961 – WP17 done. Red-first commits precede each conversion (83c0c4c8e/85a9aef9c T090; 2b4bc2644/82bf714ce T091 with campsite 228134420; 838f7d8cd/d079314e0 T092; 029f57219/b10a18a98 T093; 63f3ec0d2/f1bc8e958 T094). Markers: TRANSITIONAL(WP18) added 0; bridging added 1 (status/transition_pipeline.py _bare_root_subtasks_dir placement_seam effective_root -> WP18 converts); bridging: WP17 grep empty. Out-of-map edits: mission_finalize.py 1 call; tasks_verdict_persistence.py 2 calls; accept.py 2 calls; commit_router.py 1 call+import; transaction.py 1 call; transition_pipeline.py default resolver + private bare-root helper; tests: test_owned_lifecycle_acceptance_finalize.py (ledger row + bridge assertion), test_pr_merge_baseline.py (one call + OwnedMission fact), test_accept_decomposition.py (2 bridge assertions). Tests 3592 passed / 2 failed (both red on base: test_birth_cutover[coord], test_dogfood_corpus_backfilled). mypy strict base 5 errors == head 5 errors.
