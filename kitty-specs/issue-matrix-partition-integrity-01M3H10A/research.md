# Research: Issue-Matrix Partition Read Integrity & Merge Verdict-Terminality

**Phase 0** — all decisions grounded in live-code findings from the pre-spec analysis squad
(root-cause, architecture-alignment, foldable-issues lenses) and the operator's recorded
architecture decisions. No open `NEEDS CLARIFICATION` markers.

## D1 — Reuse the placement seam; do not add a second resolver

- **Decision**: Adopt the existing `PlacementSeam.read_dir` / `resolve_artifact_surface` /
  `coord_read_dir_for` (`src/mission_runtime/resolution.py`) at the two straggler consumers,
  mirroring the healthy pattern in `src/specify_cli/status/doctor.py::check_issue_matrix`
  (discovery from PRIMARY `feature_dir`, verdicts from the COORD dir).
- **Rationale**: Charter single-canonical-authority; `test_read_surface_placement_guard.py`
  declares `read_dir` the one blessed read entry point (~40+ call sites). A second helper would
  breach DIRECTIVE_044 and re-institutionalize the parallel-surface split the bug represents.
- **Alternatives considered**: a bespoke per-gate resolver (rejected — second authority); a
  narrow #5171-only wiring fix (rejected by operator — leaves #4943 live and divergent).

## D2 — Post-consolidation read is a NEW primitive resolved via the write's phase authority (the deep fix)

- **Decision**: Add a read authority in `src/mission_runtime/resolution.py` that reads ISSUE_MATRIX
  **content** from a git ref (`git show <ref>:<path>`) when there is no on-disk worktree, resolving the
  ref via the SAME lifecycle-phase authority the write path uses (`resolve_lifecycle_phase` →
  `resolve_placement_only`): PUBLISHED ⇒ consolidated-primary ref; CONSOLIDATED / PRE_CONSOLIDATION on
  coord topology ⇒ coordination branch ref. Never hardcode a surface.
- **Rationale**: The MAJOR-3 investigation confirmed the write surface is a function of **lifecycle
  phase**, not coord-worktree materialization. E2 consolidated-primary routing
  (`_E2_CONSOLIDATED_ELIGIBLE_KINDS` / `_resolve_consolidated_e2_target`) fires only in PUBLISHED phase
  (Target Ref `meta.target_branch` DELETED + baseline + completion). #5171's verdict landed on
  `kitty/mission-<slug>` ⇒ phase was CONSOLIDATED ⇒ the coordination branch ref is the correct read
  source. `coord_read_dir_for` fail-softs to `None` when the worktree is gone, so the current review CLI
  reproduces #5171's residue read. No existing primitive reads blob content off a ref (grep of
  `mission_runtime` found only branch-name/topology resolution). This is `[build]`, not adoption.
- **Read/write co-authority (critical)**: driving the read off `resolve_lifecycle_phase` guarantees the
  read targets exactly where the write landed — hardcoding the coord branch (or primary) would create
  an inverse divergence bug in the opposite phase.
- **Caveat**: because the phase reader probes `meta.target_branch` (often a durable trunk like `main`,
  never deleted), PUBLISHED/E2 may never fire for such missions ⇒ phase stays CONSOLIDATED ⇒ post-merge
  verdicts always route to the coordination branch. IC-01a must not assume E2 fires on "merged".
- **Alternatives considered**: require `--retain-worktrees` (rejected — changes workflow, doesn't close
  the class); materialize a throwaway worktree at read time (rejected — slow, side-effecting, violates
  the <2s bar); hardcode the coordination branch ref (rejected — diverges from the write in PUBLISHED
  phase).

## D3 — Merge mirrors move-task's terminal-verdict rule

- **Decision**: Merge applies the `in-mission`/`unknown` -> `done` rejection that
  `tasks_move_task.py::_issue_matrix_approval_blocker` already implements: `block` refuses before
  the target advances (naming rows); `warn` advances/records `done` but prints the same list.
- **Rationale**: #4943 leg 2 — merge records `done` directly via
  `merge/done_bookkeeping.py::_mark_wp_merged_done`, bypassing the only enforcement point. Reuse the
  existing rule (single authority), do not re-define verdict semantics.
- **Alternatives considered**: route merge's done-recording through `move-task` (rejected — large
  behavioral coupling, out of scope); block on `warn` too (rejected — contradicts existing
  `merge_gates.mode` conventions).

## D4 — Fail-closed on the resolved ref; #4959 carve-out

- **Decision**: After the phase authority (D2) selects the surface, check existence via
  `git rev-parse --verify` / `coord_branch_has_committed_artifact`: resolved ref present ⇒ read content;
  ref absent ⇒ fail closed (deleted leg); content probe errors ⇒ fail closed on a distinct path; empty
  authored set with live references ⇒ fail closed (never "nothing to enforce"). The UNMATERIALIZED
  ref-read is carved for ISSUE_MATRIX **only** — the deliberate #4959 `CoordinationWorktreeUnmaterialized`
  raise in `_classify_artifact_surface` MUST still fire for the other coord kinds (TRACER_FILE,
  REVIEW_CYCLE, ACCEPTANCE_MATRIX, STATUS_STATE), with a non-regression guard.
- **Rationale**: Avoids conflating "deleted" with a transient probe error (both refuse, separately
  tested). Fail-open is the worse mode (vacuous PASS), so every ambiguity refuses (NFR-002). The #4959
  carve-out prevents the deep read from regressing the tracer-clobber fix for other kinds.
- **Alternatives considered**: catch-all exception → "deleted" (rejected — hides probe errors);
  removing the UNMATERIALIZED raise for all kinds (rejected — regresses #4959).

## D5 — Non-vacuous regression guard

- **Decision**: A `tests/architectural/` guard asserts no mission-review doctrine step or review/merge
  gate consumer reconstructs a topology-dependent `issue-matrix` path by hand; it carries a
  self-mutation check (inject a raw read → guard trips).
- **Rationale**: DIRECTIVE_043 close-defect-class-by-construction; NFR-001 count = 0. Prevents the
  improvised-path regression re-entering doctrine or code.

## Adversarial evidence (post-spec squad dispositions)

Per `contracts/adversarial-evidence-contract.md`, no contested finding silently dropped:

| Finding | Disposition |
|---------|-------------|
| Testability M1 — merge fixture not partition-discriminating | **changed** — US2 seeded with divergent primary/coord + inverted mirror |
| Testability M2 — FR-007 refusal legs not decomposed / unpaired | **changed** — US4 scenarios 4/5 add empty-set + probe-error, each same-fixture paired |
| Testability M3 — deep read/terminality witnessed only via review | **changed** — US4 scenario 2 + US3 bound to coord post-consolidation exercise the merge path |
| Testability M4 — FR-002 witnessed only by absence guard | **changed** — FR-002 gains a positive control (rendered doctrine references the resolver) |
| Testability m5 — corrected-behavior FRs mislabeled `[ratchet]` | **changed** — relabelled `[build]` (FR-001/003/004, SC-001/002) |
| Testability m6 — NFR-003 threshold unmeasurable | **changed** — pinned fixture (10 issues / 25 rows) |
| Scope M1 — "not a new-primitive" over-broad | **changed** — Assumptions scoped; FR-005 called out as new |
| Scope M2 — deleted-vs-unmaterialized signal unnamed | **changed** — `git rev-parse --verify` named (D4) |
| Scope M3 — warn-vs-block semantics ambiguous | **changed** — US3 scenario 2 states warn still records done |
| Scope m1 — "husk" not in Key Entities | **changed** — added to Coordination partition entity |

## Supply-chain security (advisory)

No new third-party dependencies are added. The branch-ref read uses `git` via subprocess, the same
mechanism already used across the merge/lanes code; no new registry, lifecycle scripts, or package
pins are introduced. No supply-chain surface to review for this mission.
