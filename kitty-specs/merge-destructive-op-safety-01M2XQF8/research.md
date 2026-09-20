# Phase 0 Research — Merge/Git Destructive-Operation Safety

Consolidated from the pre-spec grounding squad (research/alignment + similar-surface
lenses) and the post-spec adversarial lens. Every claim traces to a file:line at
current main `ba4e590142`.

## Decision 1 — Unify one guard, do not patch three sites

- **Decision**: Introduce a single pre-mutation *refuse-before-destroy* guard and
  route the three destructive sites through it.
- **Rationale**: The alignment lens found dirty-state/branch safety **forked across
  ~9 independent predicates** (`git/ref_advance._dirty_entries`,
  `lanes/worktree_allocator._validate_worktree_clean`,
  `review/dirty_classifier.classify_dirty_paths`,
  `charter_runtime/preflight/runner._detect_dirty_artifacts`,
  `git/sparse_checkout_remediation._is_dirty`,
  `cli/commands/agent/mission_repair._is_worktree_dirty`,
  `cli/commands/accept._*_dirty_paths`, `acceptance._porcelain_dirty_path`,
  `merge/git_probes._paths_have_status_changes`), 41+ files parsing
  `git status --porcelain`, with a documented history (#2795/FR-012) of three of
  them giving opposite verdicts on the same file. No canonical owner exists — a
  file-lock-authority-gap-shaped defect. Patch-3 would mint a 10th predicate and
  guarantee the next whack-a-field.
- **Alternatives rejected**: Per-site bespoke checks (rejected — perpetuates the
  fork); overloading `advance_branch_ref` (rejected — it only inspects
  target-branch worktrees, `ref_advance.py:366`, not the primary checkout #4752
  resets).

## Decision 2 — Reuse `_dirty_entries`; new typed refusal; inject the churn classifier

- **Decision**: The guard reuses `git/ref_advance._dirty_entries` (`ref_advance.py:240`)
  as the residue-aware dirty predicate and raises a NEW typed refusal modeled on
  `RefAdvanceDirtyWorktreeError` (`ref_advance.py:82`, error_code +
  resume-remediation text). Do NOT overload `SafeCommitHeadMismatch`.
- **Rationale**: `_dirty_entries` already handles `--ignored`, tree-obstruction,
  the meta-lock exemption, and an **injectable** `is_residue` classifier
  (`coordination.coherence.is_toolchain_generated_churn`) that the merge paths
  already pass at `merge/ordering.py`. `SafeCommitHeadMismatch`
  (`commit_helpers.py:138`) has ≥6 downstream catchers
  (`cli/commands/implement.py`, `core/mission_creation.py`,
  `cli/commands/agent/workflow_executor.py`, `git/bookkeeping_commit.py`,
  `merge/executor.py`) whose semantics must not shift.
- **Alternatives rejected**: A second, blanket porcelain check like
  `_validate_worktree_clean` (rejected — no residue exemption → false-positive
  blocks on toolchain churn, the #2795/FR-012 trap in reverse). Two classifier
  layers (rejected — C-005: inject one classifier as the mechanism).

## Decision 3 — `remove_workspace` is the worktree-removal chokepoint

- **Decision**: Route lane + coord worktree force-removal through
  `core/vcs/git.py remove_workspace` (`git.py:222`) and add the guard there.
- **Rationale**: The surface lens found the same "force-remove worktree, no dirty
  check" defect at `merge/executor.py:1607` (#4753),
  `coordination/workspace.py:300` (coord teardown), and
  `orchestrator_api/commands.py:869` (cleanup mirror). A patch-N approach WILL miss
  the orchestrator mirror (not named in the issues). One chokepoint covers all
  three + future callers.
- **Out of scope (explicitly)**: scratch merge workspace (`merge/workspace.py`,
  `cleanup_merge_workspace`) — detached, no user work, always unconditional (C-006);
  all detached temp worktrees (ordering.py, lanes/merge.py, review/baseline.py);
  `mission close --discard` (intentional destruction); doctrine git-source reset.

## Decision 4 — Pre-mutation preflight (governing atomicity model)

- **Decision**: All dirty/branch detection happens in the merge **preflight**,
  before `_phase_mission_to_target` advances the ref (`merge/executor.py` phase 6,
  `lanes/merge.py:899/946`); on any unsafe condition the merge refuses fail-closed
  before mutating anything.
- **Rationale**: The post-spec lens proved NFR-001 "byte-identical to
  pre-invocation" is unsatisfiable if the lane-worktree guard fires at the cleanup
  phase (phase 13, after the ref advance and bookkeeping commit). Moving detection
  to preflight makes atomicity uniform across US1/US2/US3, removes the coord
  half-tear risk, and lets NFR-001 be enforced by asserting the destructive call
  site is unreachable on the refusal path (a spy/ordering test, not a
  post-hoc-restore observable).

## Pipeline anchors (for the implementers)

Lane-based merge phase order (`merge/executor.py:1815-1828`): gates → merge lanes →
baseline/surface → bake+pre-target-done → capture-pre-target → **`_phase_mission_to_target`
(REF ADVANCE)** → **`_phase_capture_and_baseline` (#4752 reset at :920)** →
record-done → porcelain-invariant → commit-and-assert → dossier/stale → push →
**`_phase_cleanup_worktrees_and_branches` (#4753 remove --force at :1606)** →
finalize. #4754 is on the separate `_dispatch_abort` path
(`cli/commands/merge.py:420` → `merge/state.py:455`).

## Red-first harness

`tests/integration/test_merge_lane_planning_data_loss.py` Layer 2
(`_real_merge_external_mocks`, ~:346) drives real git and mocks only out-of-git
side effects — the template for #4752 (do not mock
`_refresh_primary_checkout_after_merge`; seed the primary checkout dirty/off-target)
and #4753 (do not mock the cleanup loop; seed a dirty lane worktree). #4754 needs a
new `_dispatch_abort` harness (seed `MERGE_HEAD` in `repo_root`, no spec-kitty merge
state).

## Adversarial evidence (post-spec squad dispositions)

Per `contracts/adversarial-evidence-contract.md` — every contested finding's
disposition (no finding silently dropped):

| Finding | Severity | Disposition |
|---------|----------|-------------|
| Coord-triple coupled teardown unspecified | BLOCKING | **changed** — FR-004 + US2 AC4 (atomic triple retention) |
| NFR-001 atomicity unsatisfiable on cleanup path | BLOCKING | **changed** — adopted pre-mutation preflight model (Decision 4); NFR-001 rewritten |
| `--resume` guard honoring prose-only | SHOULD-FIX | **changed** — US1 AC4 + NFR-002 resume parity |
| Scratch workspace not excluded | SHOULD-FIX | **changed** — C-006 + Edge Case |
| SC-004/FR-007 unification not tested | SHOULD-FIX | **changed** — NFR-006 arch gate + IC-5 |
| US2 AC1 disjunction exit-code undecidable | SHOULD-FIX | **changed** — US2 AC1/AC2 exit + retain-path success-line contract, FR-006 |
| NFR-001 mutate-then-restore reading | SHOULD-FIX | **changed** — NFR-001 now asserts call-site unreachable (ordering spy) |
| C-001/C-005 classifier reconciliation | SHOULD-FIX | **changed** — C-005 reworded: injection is the mechanism; NFR-003 fixture = meta.json VCS-lock stamp |
| US priority headings off-by-one | SHOULD-FIX | **changed** — corrected to P0/P0/P1 |
| C-004 could license unguarded coord `branch -D` | caveat | **changed** — C-004 reworded (coupled coord-branch deletion in scope) |
| `mission close --discard` over-guard risk | NICE | **accepted** — Edge Case "explicit discard excluded" |
| Deferring standalone `branch -D` | OK | **accepted** — kept as C-004 follow-up |

No supply-chain dependency decision in this mission → DIRECTIVE_051 N/A.
