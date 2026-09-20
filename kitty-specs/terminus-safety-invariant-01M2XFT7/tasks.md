# Tasks: Terminus-Safety Invariant

**Mission**: `terminus-safety-invariant-01M2XFT7`
**Mission branch**: `issue-4764-terminus-safety-invariant` (planning base AND merge target; the mission branch later opens a PR to `main`, which the operator merges)
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md) · **Data model**: [data-model.md](data-model.md) · **Contract**: [contracts/terminus-safety-contract.md](contracts/terminus-safety-contract.md)

This breakdown authors the plan's **Implementation Concern Map** + **Parallel Work Analysis** into 7 file-partitioned work packages. Every WP is `execution_mode: code_change`, `agent_profile: python-pedro`, `role: implementer`. Owned-file sets are disjoint by construction; `finalize-tasks --validate-only` rejects any overlap.

**Execution model (single-branch, per operator directive)**: WPs are implemented by subagents **directly on the single mission branch `issue-4764-terminus-safety-invariant`** — NOT in lane worktrees. Sequencing follows the dependency graph below; the integrated diff gets a pre-PR adversarial squad before the PR opens. Each WP commits its red-first regression test as a distinct preceding commit (ATDD C-004 / C-011).

---

## Dependency Graph

```
WP01 (enabler, tidy-first)  ──►  WP02  ──►  WP04  (post-merge backstop resume-coherence)
        │                          └──►  WP05  (--skip-lanes affordance)
        ├──►  WP03  (topology-aware bake)
        ├──►  WP06  (close safety + orphan robustness)
        └──►  WP07  (accept guidance liveness)
```

- **WP01 must land first** — the shared aggregate is behavior-preserving and every functional WP consumes it (DIRECTIVE_025 tidy-first: enabler before functional change).
- **Parallel after WP01**: WP02, WP03, WP06, WP07 (disjoint files/surfaces).
- **Sequential after WP02**: WP04 (post-merge backstop cooperates with WP02's rollback), WP05 (direct-on-target reuses the WP02 precondition).

---

## Subtask Index

| Txxx | Description | WP | Parallel |
|------|-------------|-----|----------|
| T001 | RED-first unit tests: `mission_terminal_acceptability` truth table (US1-6 cancelled-without-provenance ⇒ not-ready; US4-2 provenance-cancelled ⇒ ready) | WP01 | after none |
| T002 | ADD pure `mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)` to `status_lanes.py` | WP01 | after none |
| T003 | Reroute accept terminal-readiness (`gates_core._all_work_packages_terminal` :66 / `summary_core` :226) onto the aggregate; parity tests | WP01 | after none |
| T004 | Retire duplicate terminal-set in `doctor.py` (:28 `_TERMINAL_LANES` / :270 inline) → `status_lanes.TERMINAL_LANES` | WP01 | after none |
| T005 | RED-first `@regression` #4764: warn-mode unapproved merge → Exit(1), no consolidation, no bake, WP reaches `for_review`; + `--resume` vacuous-pass refusal (US1-5) | WP02 | after WP01 |
| T006 | De-conflate terminal-lane invariant OUT of the mode-softened evidence gate in `merge_gates.py` | WP02 | after WP01 |
| T007 | Add unconditional merge-ready precondition `_assert_mission_terminal_ready(run)` in `executor._phase_gates_and_state` before `_phase_merge_lanes` (C901 ≤ 15, `typer.Exit(1)`) | WP02 | after WP01 |
| T008 | Unify coord-transaction machinery (`_capture_pre_target_coord_ref_sha`/`_restore_and_guard_coord_coherence`/`_revert_coord_done_commit`) into ONE checkpoint primitive + new pre-mutation checkpoint + reset-before-cleanup | WP02 | after WP01 |
| T009 | Direct-on-target refuse-before-advance guard (US3-3); refusal must originate from `_assert_mission_terminal_ready` on the skip-lanes path, NOT a vacuous `MissingLanesError` (FOLD 3); D5 target-advance rollback caveat | WP02 | after WP01 |
| T010 | RED-first `@regression` rollback resume-coherence + non-vacuous direct-on-target refuse (reaches target-advance via skip-lanes path; refusal is `_assert_mission_terminal_ready`, not `MissingLanesError`; target ref unchanged) | WP02 | after WP01 |
| T021 | Executor-side skip-lanes plumbing (FOLD 1): skip-lanes flag on `_MergeRunState` (:268) + `_run_lane_based_merge` (:1831) + absent-lane tolerance in `require_lanes_json` (:1918)/`_phase_merge_lanes` (:397-460); merge-ready no-lane mission completes transactionally, precondition still runs | WP02 | after WP01 |
| T011 | RED-first `@regression` #4474: reachable-primary case PERSISTS number (doctor pending→assigned, surfacing insufficient); separate genuinely-unreachable case surfaces it (FOLD 4) | WP03 | after WP01 |
| T012 | Make `ordering.py` bake write-back topology-aware (reach primary-tree meta.json) OR surface the unbaked field as a queryable event + merge-summary line | WP03 | after WP01 |
| T013 | RED-first `@regression` resume-after-rolled-back-merge reads coherent state (no split-brain) | WP04 | after WP02 |
| T014 | Ensure post-merge validation-failure path cooperates with WP02 rollback so committed coordination `done` markers stay coherent with worktree bytes | WP04 | after WP02 |
| T015 | RED-first `@regression` #2745: direct-on-target mission GENUINELY completes via `--skip-lanes` (merge baseline recorded AND target ref advanced — not just exit-0/no-hard-fail) + transactional-rollback assertion; not-merge-ready mission still refuses (FOLD 1) | WP05 | after WP02 |
| T016 | Add the `--skip-lanes`/`--no-lanes` CLI option on `merge` and wire it to WP02's executor skip-lanes capability (no `executor.py` edit here); keep the fixed error-translation chain (`merge.py` :541-554) | WP05 | after WP02 |
| T017 | RED-first `@regression` #4765: unmerged non-discard close → Exit(1), NO retrospective committed, coord worktree intact; + orphan-branch close succeeds with `--json` | WP06 | after WP01 |
| T018 | Fail-closed `is_mission_merged(feature_dir)` guard at TOP of `close_cmd` non-discard else (`mission_type.py` :639, before `_teardown_coordination_worktree` :644); Exit(1) via `_emit_mission_error`, point at `--discard` | WP06 | after WP01 |
| T019 | Tolerate orphaned `coordination_branch` marker (no traceback), fix doubled-slug render, honor `--json` | WP06 | after WP01 |
| T020 | RED-first liveness probe: `accept` SUBSTANTIVELY names the real escape hatch (not tautological, not impossible "materialize-then-retry"); paste the actual green probe run as evidence; document verified-already-fixed if green on current main (accept.py :1007) (FOLD 5) | WP07 | after WP01 |

---

## WP01 — Shared terminal-readiness authority (tidy-first enabler, behavior-preserving)

**Prompt**: [tasks/WP01-shared-terminal-readiness-authority.md](tasks/WP01-shared-terminal-readiness-authority.md)

**Summary**
- **Goal**: Add ONE pure, provenance-aware **snapshot-shaped** aggregate `mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)` to the orchestration-free `status_lanes.py` for the merge/close consumers (WP02, WP06), and retire the duplicate terminal-set in `doctor.py`. Behavior-preserving. Delivers FR-009 (C-001; no 6th definition). **FOLD 2**: does NOT reroute accept's provenance-blind lane views (`gates_core`/`summary_core`) — they already route through the canonical per-lane `is_acceptable_ending`; rerouting would flip accept's verdict. Owned files = `status_lanes.py` + `status/doctor.py` only.
- **Priority**: P0 build-order (enabler; every functional WP depends on it). Value-priority Medium per FR-009, but it MUST land first.
- **Independent test**: The aggregate truth table is exercised directly (approved/done ⇒ ready; cancelled-with-provenance ⇒ ready; cancelled-without-provenance ⇒ not-ready with the WP in `missing_wp_ids`), and accept + doctor parity tests prove no behavior change (accept is NOT modified but must be proven unchanged).

**Included subtasks**: T001 aggregate truth-table RED tests (WP01) · T002 add aggregate (WP01) · T003 confirm accept already single-authority (NO reroute) + parity guard (WP01) · T004 retire doctor.py duplicate (WP01)

**Implementation sketch**: Reuse `is_acceptable_ending` (`status_lanes.py:42`) + `has_operator_provenance` (`:70`) + `TERMINAL_LANES` (`:25`). The aggregate iterates the mission's work-package **snapshots** (the shape merge/close pass), returns `(all-acceptable, sorted missing WP ids)`. Do NOT touch `gates_core._all_work_packages_terminal` (:66) or `summary_core` (:226) — they are provenance-blind lane views that already consume the canonical predicate (FOLD 2). Retire `doctor.py._TERMINAL_LANES` (:28) and the inline `terminal_lanes` set (:270). `status_lanes` is NOT in the `specify_cli.status` facade, so this import is facade-safe.

**Dependencies**: none.

**Risks**: (1) scope-creep into accept — mistakenly rerouting the provenance-blind accept lane views would flip the cancelled-WP verdict; accept files are un-owned and proven unchanged by a parity test (FOLD 2). (2) doctor.py uses `Lane` enum members while `status_lanes.TERMINAL_LANES` is a `frozenset[str]` — the retirement must reconcile the type at the call site without widening behavior.

**Estimated prompt size**: ~260 lines.

---

## WP02 — Merge safety core (#4764 + rollback + direct-on-target refuse)

**Prompt**: [tasks/WP02-merge-safety-core.md](tasks/WP02-merge-safety-core.md)

**Summary**
- **Goal**: The cohesive merge-path core. De-conflate the terminal-lane invariant out of the mode-softened evidence gate; add an unconditional merge-ready precondition before lane consolidation; unify the coord-transaction machinery into one checkpoint primitive with a pre-mutation checkpoint and reset-on-failure; add the direct-on-target refuse-before-advance guard; **build the executor-side skip-lanes plumbing (FOLD 1) that WP05's CLI option wires onto**. Delivers FR-001, FR-002, FR-003, FR-006, FR-007, FR-008, FR-010, and the executor half of FR-012.
- **Priority**: P1. The heart of the invariant (US1, US3).
- **Independent test**: A default-config (`warn`) merge on a mission with an unapproved non-cancelled WP is refused before any mutation (no consolidation, no bake, WP still reaches `for_review`); a `--resume` re-evaluates live readiness and still refuses; a forced post-mutation failure rolls coord ref/worktree back; a not-merge-ready direct-on-target mission (via the skip-lanes path) refuses before advancing the target ref, and the refusal originates from `_assert_mission_terminal_ready` (not `MissingLanesError`).

**Included subtasks**: T005 #4764 + --resume RED tests (WP02) · T006 de-conflate evidence gate (WP02) · T007 unconditional precondition `_assert_mission_terminal_ready` (WP02) · T008 unified checkpoint primitive + reset-before-cleanup (WP02) · T009 direct-on-target refuse-before-advance, non-vacuous (WP02) · T010 rollback + non-vacuous direct-on-target refuse RED tests (WP02) · T021 executor-side skip-lanes plumbing (WP02, FOLD 1)

**Implementation sketch**: In `merge_gates.py`, keep evidence-quality gates (`_evaluate_evidence_gate` :147, risk/dependency/issue-matrix) softenable under `warn`, but remove the terminal-lane readiness from that softenable path. In `executor.py`, extract `_assert_mission_terminal_ready(run)` invoked at the top of `_phase_gates_and_state` (:343) before `_phase_merge_lanes` (:397), calling the WP01 aggregate; raise `typer.Exit(1)` (no new error type). Unify `_capture_pre_target_coord_ref_sha` (:553), `_restore_and_guard_coord_coherence` (:788), `_revert_coord_done_commit` (:644) into one checkpoint primitive holding named checkpoints (new pre-mutation + existing pre-done); reset runs BEFORE `_phase_cleanup_worktrees_and_branches` (:1588) — after teardown a reset silently no-ops. Add refuse-before-advance for the direct-on-target path (`done_marked_before_target` :282/:486). Build skip-lanes plumbing (T021): flag on `_MergeRunState` (:268) + `_run_lane_based_merge` (:1831), absent-lane tolerance in `require_lanes_json` (:1918)/`_phase_merge_lanes` (:397-460) so a merge-ready no-lane mission completes transactionally while the precondition still runs — this is also what lets T009/T010's refuse test reach `_assert_mission_terminal_ready` rather than tripping `MissingLanesError` first (FOLD 3).

**Dependencies**: WP01.

**Risks**: (1) **D5 caveat** — if the *rollback-after-target-advance* on the direct-on-target path proves mission-sized, ship the refuse-before-advance guard and mark the target-advance rollback as a tracked #3897 follow-up in the WP's Definition of Done (do NOT silently drop it). (2) C901 ≤ 15 on `_phase_gates_and_state` — extract the precondition, don't inline. (3) NFR-002 — no false-block on a legitimate merge-ready mission, including on `--resume`. (4) FOLD 3 — the direct-on-target refusal must originate from `_assert_mission_terminal_ready` on the skip-lanes path, not vacuously from `MissingLanesError` (which fires first today at :1918).

**Estimated prompt size**: ~680 lines (the cohesive merge-path core; +T021 skip-lanes plumbing).

---

## WP03 — Topology-aware mission_number bake (#4474)

**Prompt**: [tasks/WP03-topology-aware-mission-number-bake.md](tasks/WP03-topology-aware-mission-number-bake.md)

**Summary**
- **Goal**: Fix the merge-READY coord fail-open at `ordering.py:407/:414` — make the `mission_number` write-back topology-aware (reach the primary-tree `meta.json`) OR, only when the primary tree is genuinely unreachable, surface the unbaked field as a queryable event + merge-summary line (never a silent log-only `return False`). Delivers FR-011 (#4474's actual defect, distinct from FR-006).
- **Priority**: P1 (High FR).
- **Independent test (FOLD 4)**: a NORMAL merge-ready coord mission (primary reachable) has `mission_number` PERSISTED — `doctor` flips `pending`→`assigned` (surfacing-only is insufficient here); a separately-constructed genuinely-unreachable mission surfaces the field via event + summary line.

**Included subtasks**: T011 #4474 RED tests — reachable-primary PERSIST case + genuinely-unreachable surface case (WP03) · T012 topology-aware bake write-back (persist preferred, surface fallback) (WP03)

**Implementation sketch**: At `ordering.py`, the bake composes the meta path in the mission-branch tree and `return False` when it is absent-on-branch (or resolves under `.worktrees/`). Make the write-back reach the correct (primary-tree) `meta.json` surface (PERSIST — the preferred outcome when reachable, FOLD 4); only if it genuinely cannot, emit a queryable event + a merge-summary line naming the unbaked field. FR-006 (never bake a not-merge-ready mission) is upstream in WP02; this is the OPPOSITE mode (a merge-ready mission losing its number). **Dead-symbol re-pin (FOLD 4/paula)**: if the fix changes the body of `_is_assigned_mission_number` (:1318)/`_mark_mission_number_baked` (:1320)/`_already_baked` (:1315), re-pin `test_no_dead_symbols.py` hashes in the same commit.

**Dependencies**: WP01.

**Risks**: (1) Must not re-pollute the mission-branch tree by resolving into `.worktrees/` (keep `path_is_under_worktrees`). (2) The surfacing path must be observable by `doctor` and the merge summary, not just a logger warning. (3) FOLD 4 — must not take the cheap surface-only escape when the primary tree was reachable. (4) FOLD 4/paula — a hash-pinned dead-symbol body change without a re-pin reds the architectural battery.

**Estimated prompt size**: ~270 lines.

---

## WP04 — Post-merge backstop resume-coherence

**Prompt**: [tasks/WP04-post-merge-backstop-resume-coherence.md](tasks/WP04-post-merge-backstop-resume-coherence.md)

**Summary**
- **Goal**: Ensure the post-merge validation-failure path in `done_bookkeeping.py` cooperates with WP02's rollback so committed coordination `done` markers (`_durable_done_wps_on_coordination_ref` :595) stay coherent with worktree bytes after a reset. Delivers FR-008.
- **Priority**: P1 (High FR); defense-in-depth for the rollback (US3-1).
- **Independent test**: A `--resume` after a rolled-back merge reads coherent state (no split-brain between committed coordination `done` markers and worktree bytes).

**Included subtasks**: T013 resume-coherence RED test (WP04) · T014 backstop cooperates with rollback (WP04)

**Implementation sketch**: The post-merge backstop (`_assert_merged_wps_reached_done` :444, driven from the run at :743) reads durable done markers off the coordination ref. After WP02 resets the coord ref/worktree on a post-mutation failure, the durable-done reader must observe a coherent state. Verify/adjust the backstop's read path so a rolled-back merge does not leave `done` markers that disagree with worktree bytes.

**Dependencies**: WP02 (consumes the checkpoint/reset primitive).

**Risks**: The seam between WP02's reset and WP04's durable-done reader is the split-brain surface — the two WPs must agree on ordering (reset BEFORE the durable-done reader would otherwise commit). Coordinate through the shared checkpoint primitive, not a second read path.

**Estimated prompt size**: ~230 lines.

---

## WP05 — Direct-on-target completion affordance `merge --skip-lanes` (#2745)

**Prompt**: [tasks/WP05-merge-skip-lanes-affordance.md](tasks/WP05-merge-skip-lanes-affordance.md)

**Summary**
- **Goal**: Add the `--skip-lanes`/`--no-lanes` **CLI option** on `merge` and wire it to WP02's executor skip-lanes capability (T021), so a merge-ready direct-on-target mission with no lane branch completes transactionally, still enforcing the WP02 merge-ready precondition (no bypass). Keep the fixed error-translation chain (`merge.py` :541-554). Delivers the CLI half of FR-012 (co-owned with WP02). **FOLD 1**: this WP owns `merge.py` ONLY — the executor plumbing is WP02's T021 (verified: `require_lanes_json` is unconditional, no existing no-lane path).
- **Priority**: P2 (additive affordance; makes the safe path non-stuck, US5).
- **Independent test (FOLD 1)**: a direct-on-target mission GENUINELY completes via the option (merge baseline recorded AND target ref advanced to include the WP commit — not merely exit-0/no-hard-fail), with a transactional-rollback assertion; the option on a not-merge-ready mission still refuses (precondition not bypassed).

**Included subtasks**: T015 #2745 genuine-completion + rollback RED test (WP05) · T016 add the `--skip-lanes`/`--no-lanes` CLI option + wire to WP02 capability (WP05)

**Implementation sketch**: Add the option on the `merge` command (`merge.py:574`) and thread it into the executor entry call so it reaches WP02's skip-lanes capability. Do NOT implement the absent-lane tolerance here (that is WP02's T021 in `executor.py`, which this WP does not own). Preserve the fixed except-chain at :541-554; add no new escaping error type (C-003). Terminology canon — canonical `lanes` vocabulary, never `feature`.

**Dependencies**: WP02 (the CLI option wires onto WP02's T021 executor capability; sequence after WP02).

**Risks**: (1) The option must NOT become a precondition bypass — WP02's capability runs the merge-ready gate on the skip-lanes path; assert US5-2 end-to-end. (2) FOLD 1 — do not implement the tolerance in `executor.py` here; that is WP02's T021. (3) Vacuous US5-1 — assert genuine completion (baseline + target-ref advance), not exit-0/no-hard-fail. (4) Terminology canon.

**Estimated prompt size**: ~320 lines.

---

## WP06 — Mission close safety + orphan robustness (#4765 + #2745 facet 3)

**Prompt**: [tasks/WP06-mission-close-safety-orphan-robustness.md](tasks/WP06-mission-close-safety-orphan-robustness.md)

**Summary**
- **Goal**: Add a fail-closed `is_mission_merged(feature_dir)` guard at the TOP of `close_cmd`'s non-discard `else` (`mission_type.py:639`, before `_teardown_coordination_worktree` :644), Exit(1) via `_emit_mission_error` pointing at `--discard`; tolerate an orphaned `coordination_branch` marker (no traceback), fix the doubled-slug render, honor `--json`. Delivers FR-004, FR-005, FR-013.
- **Priority**: P1 (High FRs 004/005; Medium 013).
- **Independent test**: An unmerged mission close (non-discard) exits non-zero, commits NO retrospective, leaves the coord worktree intact, points at `--discard`; an orphan-branch close succeeds with `--json`.

**Included subtasks**: T017 #4765 + orphan RED tests (WP06) · T018 is_mission_merged guard (WP06) · T019 orphan tolerance + doubled-slug + --json (WP06)

**Implementation sketch**: Import `is_mission_merged` via the `specify_cli.status` facade (C-002). Guard the non-discard branch before `_teardown_coordination_worktree` (:644); on not-merged, `_emit_mission_error(..., code=..., json_output=json)` (:1270) and Exit(1) — mirrors the `reopen_cmd` guard. Tolerate an orphaned `coordination_branch` marker (no traceback), render the slug once, honor `--json`. The merged path (D4: `is_mission_merged`, NOT `is_mission_completed`) is unchanged.

**Dependencies**: WP01.

**Risks**: (1) **Harness caveat** — drive the app/error-hook seam (not a bare `CliRunner`) for hook-routed errors; a plain `Exit(1)` is fine via `CliRunner`. (2) D4 — guard on `is_mission_merged`, NOT `is_mission_completed` (an all-cancelled-unmerged mission must go via `--discard`). (3) Do not regress the existing `--discard` path (`test_mission_close_discard_coord_teardown.py`, `test_issue_3716_discard_transactional_close_guard.py`).

**Estimated prompt size**: ~340 lines.

---

## WP07 — Accept guidance liveness (#2745 facet 2)

**Prompt**: [tasks/WP07-accept-guidance-liveness.md](tasks/WP07-accept-guidance-liveness.md)

**Summary**
- **Goal**: Confirm `accept` gives followable guidance (names the real escape hatch), not impossible "materialize-then-retry" — the protected-primary hard-reject appears already removed (`accept.py:1007`). Delivers FR-014 (a liveness confirmation).
- **Priority**: P3 (Low FR; small WP).
- **Independent test**: A probe that expects GREEN on current main ⇒ document as verified-already-fixed (do NOT fabricate a red); if genuinely reproducible, fix.

**Included subtasks**: T020 accept guidance liveness probe — substantive assertion + pasted green-run evidence (WP07, FOLD 5)

**Implementation sketch**: Write a SUBSTANTIVE probe through the `accept` entry point for a mission with no lane branch, asserting the output NAMES the real followable escape hatch (concrete command/flag) and omits the impossible "materialize-then-retry" instruction — not a tautological exit-0/no-exception check (FOLD 5). Per FR-014 and research.md, the protected-primary hard reject was already removed at `accept.py:1007` — if the probe is green on current main, document it as verified-already-fixed rather than fabricating a red, and PASTE the actual green probe run (command + pass count) into the WP notes/PR as evidence (FOLD 5). Keep this WP small.

**Dependencies**: WP01.

**Risks**: (1) Anti-fabrication — a genuinely-green probe must be documented as verified-already-fixed, not padded into a fake red-then-green cycle (C-004; SC-004). (2) FOLD 5 — a tautological probe proves nothing; assert substantively and paste the green run.

**Estimated prompt size**: ~210 lines.

---

## Traceability

| FR | WP | Contract |
|----|----|----------|
| FR-001, FR-002, FR-003, FR-006 | WP02 | C-MERGE |
| FR-007, FR-008 | WP02 (+WP04 for FR-008 backstop) | C-ROLLBACK |
| FR-010 | WP02 | C-DIRECT-ON-TARGET (SAFE) |
| FR-009 | WP01 | C-SHARED-AUTHORITY |
| FR-011 | WP03 | C-MERGE (BAKE) |
| FR-012 | WP02 (executor plumbing, T021) + WP05 (CLI option) | C-DIRECT-ON-TARGET (COMPLETE) |
| FR-004, FR-005, FR-013 | WP06 | C-CLOSE |
| FR-014 | WP07 | C-ACCEPT-GUIDANCE |

All FR-001..FR-014 are covered. NFR-001..NFR-004 and C-001..C-006 apply across WPs (see each WP's Definition of Done).
