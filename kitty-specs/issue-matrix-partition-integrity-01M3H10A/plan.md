# Implementation Plan: Issue-Matrix Partition Read Integrity & Merge Verdict-Terminality

**Branch**: `claude/spec-kitty-ci-failures-r0xui3` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/issue-matrix-partition-integrity-01M3H10A/spec.md`

## Summary

Every issue-matrix consumer must resolve the artifact's owning partition before reading it,
and merge must enforce the terminal-verdict rule. The placement seam
(`src/mission_runtime/resolution.py` — `PlacementSeam.read_dir`, `resolve_artifact_surface`,
`coord_read_dir_for`) is the canonical resolver and is already correctly adopted by
`src/specify_cli/status/doctor.py::check_issue_matrix` (discovery from PRIMARY, verdicts from
COORD). This mission (a) adopts that same two-partition split at the two straggler consumers —
the mission-review issue-matrix gate and the merge issue-matrix completeness gate; (b) adds a
NEW coordination-branch-ref read primitive so authored verdicts remain readable after the coord
worktree is consolidated away (branch retained); and (c) makes merge apply the
`in-mission -> done` terminal-verdict rule that today lives only in `move-task`. Approach and
call sites were confirmed against live code by the pre-spec analysis squad.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer + rich (CLI), ruamel.yaml (frontmatter), `git` via subprocess (branch-ref reads: `git rev-parse --verify`, `git show <ref>:<path>` / `cat-file`), the placement seam in `src/mission_runtime/`, `spec_kitty_events` / `spec_kitty_tracker` (public imports only)
**Storage**: git — coordination branch refs, `status.events.jsonl`, and `issue-matrix.json`/`.md` on the primary and coordination partitions; no database
**Testing**: pytest (fast/unit + integration + architectural). ATDD red-first through the real production entry points (mission-review gate, merge gate, rendered doctrine); every refusal/absence assertion paired with a same-fixture positive control; coord-vs-flat topology fixtures; compound fixes proven half-by-half
**Target Platform**: cross-platform CLI (Linux, macOS, Windows 10+)
**Project Type**: single project (this repository)
**Performance Goals**: mission-review and merge gate evaluation < 2s on the NFR-003 fixture (10 gating issues / 25 matrix rows); branch-ref read adds no measurable overhead vs the worktree read on the same fixture
**Constraints**: single canonical authority (reuse the seam; the new branch-ref primitive lives in `src/mission_runtime/`, never in the CLI adapter); respect the enforced import chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` (no new outbound edges); fail-closed on ambiguity/probe error; terminology canon (Mission, canonical verdict vocabulary); complexity ceiling 15 (extract helpers)
**Scale/Scope**: bounded bug-fix touching ~6 source modules + one doctrine SKILL (+ regenerated agent copies) + a new architectural guard + targeted tests

## Charter Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **Single canonical authority (PASS)**: No second partition-resolution authority is introduced.
  FR-001–FR-004 adopt the existing `PlacementSeam`/`coord_read_dir_for`; the new branch-ref read
  (FR-005) is added *inside* the seam's owning module (`src/mission_runtime/resolution.py`) as a
  layered primitive, not a parallel resolver in `specify_cli`.
- **Architectural alignment / layer rules (PASS)**: Consumers in `specify_cli` already import the
  seam from `mission_runtime` (a permitted edge). No new outbound module edges; the
  `landscape`/`LayerRule` fixtures stay satisfied. Verified by `tests/architectural/test_layer_rules.py`.
- **ATDD-first (PASS, enforced in tasks)**: Each WP ships a failing-first test committed before the
  fix; reviewer verifies RED on base / GREEN on final. C-003 in the spec binds this.
- **Terminology canon (PASS)**: New prose/doctrine uses "Mission" and the canonical verdict set.
  Run `pytest tests/architectural/test_no_legacy_terminology.py` before pushing doctrine/prose.
- **Boy-Scout vs locality (PASS)**: Scope is bounded to the issue-matrix kind and its named
  consumers; opportunistic cleanup limited to the touched functions (e.g. keeping `merge_gates.py`
  functions ≤ complexity 15 when the signature changes force a touch).
- **Test policy (PASS)**: Blast radius targeted (see Project Structure → Tests); no whole-repo run.

No charter violations requiring Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-matrix-partition-integrity-01M3H10A/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (behavioral contracts, not HTTP)
├── traces/              # tooling-friction / approach / design-decisions tracers
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/mission_runtime/
├── resolution.py         # PlacementSeam.read_dir, resolve_artifact_surface, coord_read_dir_for
│                         #   + NEW: coordination-branch-ref read authority (FR-005/FR-007)
└── artifacts.py          # ISSUE_MATRIX kind classification (reference only; unchanged)

src/specify_cli/
├── status/doctor.py                      # check_issue_matrix — REFERENCE two-partition split pattern
├── cli/commands/review/__init__.py       # _evaluate_issue_matrix — separate discovery/matrix reads (FR-001)
├── cli/commands/review/_issue_matrix.py  # validate_issue_matrix / matrix load (FR-001 read side)
├── policy/merge_gates.py                 # _evaluate_issue_matrix_completeness_gate (FR-003/FR-004/FR-006)
├── merge/executor.py                     # threads repo_root/mission_slug into evaluate_merge_gates (FR-003)
├── merge/done_bookkeeping.py             # _mark_wp_merged_done / _record_merged_wps_done_for_merge (FR-006)
├── tasks/issue_reference_discovery.py    # gating_issue_numbers — PRIMARY discovery (reference)
├── tasks/issue_matrix_migration.py       # load_issue_matrix / issue_matrix_artifact_present (read side; gain a coord-ref content source)
├── cli/commands/agent/tasks_parsing_validation.py # _issue_matrix_approval_blocker (DEFINED here, :206) — REFERENCE terminal-verdict rule (FR-006)
└── cli/commands/agent/tasks_move_task.py # imports/calls _issue_matrix_approval_blocker (:1109); NOT its defining module

src/charter/offering/skills/spec-kitty-mission-review/SKILL.md   # Gate-4 doctrine (:593 raw cat): resolver-backed read (FR-002)
# NOTE: this repo's own working tree has NO materialized .claude/ or .agents/skills/ copies — the
# "regenerated agent copies via `spec-kitty upgrade`" is the consumer-side mechanism only; the fix
# edits the SOURCE SKILL.md and is tested against SKILL.md directly (cf. tests/doctrine/test_mission_review_skill_gate3_floor.py)

tests/
├── architectural/        # NEW guard: no raw issue-matrix path reads in review/merge consumers (FR-008); layer rules
├── policy/               # merge_gates coord-vs-flat fixtures (FR-003/FR-004/FR-006)
├── specify_cli/cli/commands/review/  # mission-review gate partition + doctrine-render tests (FR-001/FR-002)
├── mission_runtime/ (or tests/unit/) # branch-ref read authority unit + fail-closed tests (FR-005/FR-007)
└── integration/          # post-consolidation e2e: coord worktree torn down, branch retained (FR-005/FR-006)
```

**Structure Decision**: Single-project layout. The new primitive lands in `src/mission_runtime/`
(seam owner); all consumer edits are in `src/specify_cli/`; the doctrine fix is in
`src/charter/offering/skills/` with agent copies regenerated by `spec-kitty upgrade`.

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs.

> **Sequencing (post-plan squad):** IC-01a → IC-01b → {IC-02, IC-03} → IC-04 → IC-05. The
> IC-01b → IC-02/IC-03 edge is load-bearing (the gate consumers cannot read post-consolidation
> content until the readers accept a ref-content source), not incidental.
>
> **MAJOR-3 resolved (read surface = lifecycle-phase authority, matching the write).** The write
> surface is chosen by `resolve_lifecycle_phase` (`src/mission_runtime/lifecycle_phase.py:220-273`),
> NOT by coord-worktree materialization. The E2 consolidated-primary routing
> (`_E2_CONSOLIDATED_ELIGIBLE_KINDS` / `_resolve_consolidated_e2_target`, resolution.py:154-208)
> fires ONLY in `PUBLISHED` phase, which requires the **Target Ref (`meta.target_branch`, the
> planning branch — distinct from `meta.coordination_branch`) to be DELETED** + baseline +
> completion evidence. In `CONSOLIDATED`/`PRE_CONSOLIDATION` phase on a coord topology, writes route
> to the coordination branch ref (`destination_ref`, resolution.py:1442-1443,1674) — this is #5171's
> case (write reported `surface=kitty/mission-<slug>`). **Therefore IC-01a MUST resolve the read
> surface through the SAME authority as the write** (`resolve_lifecycle_phase` /
> `resolve_placement_only` via `PlacementSeam`/`resolve_artifact_surface`), never hardcoding coord or
> primary: PUBLISHED ⇒ read consolidated-primary ref; CONSOLIDATED/PRE_CONSOLIDATION coord ⇒ read the
> coordination branch ref. Reading the wrong one is the inverse read/write-divergence bug.
>
> **Caveat (durable-trunk missions):** because the phase reader probes `meta.target_branch` (often a
> durable trunk like `main`, never deleted), PUBLISHED/E2 may never fire for such missions ⇒ phase
> stays `CONSOLIDATED` ⇒ post-merge verdicts always route to the retained coordination branch. IC-01a
> must not assume E2 fires simply because a mission is "merged"; the trigger is Target Ref deletion.

### IC-01a — Coordination-branch-ref content read primitive (the deep primitive)

- **Purpose**: Add a NEW function in the seam that returns ISSUE_MATRIX **content** (bytes/text) read
  from a git ref (`git show <ref>:<path>`) when the artifact has no on-disk worktree, resolving the
  **ref via the same lifecycle-phase authority the write path uses** (`resolve_lifecycle_phase` →
  PUBLISHED: consolidated-primary ref; CONSOLIDATED/PRE_CONSOLIDATION coord: coordination branch ref).
  Never hardcode coord or primary. Fail closed on a deleted ref, a probe error, or an empty authored
  set while gating references exist.
- **Relevant requirements**: FR-005, FR-007, NFR-002, NFR-003.
- **Affected surfaces**: `src/mission_runtime/resolution.py` — a NEW ref-content read that drives off
  `resolve_lifecycle_phase`/`resolve_placement_only` (the write authority), so read and write can
  never diverge; **do not** mutate `coord_read_dir_for`/`resolve_artifact_surface`'s existing
  `Path`/dir semantics (7+ consumers depend on them — MINOR-7). Reuse `coord_branch_has_committed_artifact`
  (`coordination/surface_resolver.py:717`) for existence-on-ref rather than a new `git ls-tree`.
- **Standalone read, not a `_classify` content change (post-tasks MAJOR-2)**: the ref-content read is a
  NEW standalone function; it does NOT edit `_classify_artifact_surface` to return content and does NOT
  change `coord_read_dir_for`/`resolve_artifact_surface`'s `Path | None` contract.
  `CoordinationWorktreeUnmaterialized` subclasses `StatusReadPathNotFound`, so `coord_read_dir_for`
  absorbs it to `None` → `feature_dir` → residue (the live bug); routing content through that path would
  re-introduce it. The WP02 helper dispatches to the standalone read when the dir is unmaterialized.
- **#4959 non-regression**: `_classify` keeps raising `CoordinationWorktreeUnmaterialized` for **all**
  coord kinds (TRACER_FILE, REVIEW_CYCLE, ACCEPTANCE_MATRIX, STATUS_STATE) unchanged; the standalone read
  serves ISSUE_MATRIX post-consolidation. A guarding test proves the raise still fires for the other kinds
  AND that the ISSUE_MATRIX post-consolidation read is served by the standalone path (non-vacuous carve-out).
- **In-layer git plumbing**: reuse `lifecycle_phase.py`'s `_rev_is_valid` / `_path_present_at_rev` /
  `_git_object_present` / `_GIT_PROBE_TIMEOUT` / `LifecyclePhaseProbeError` (no `specify_cli` import).
- **Sequencing/depends-on**: none (foundational).
- **Risks**: `git show <ref>:<path>` returns content, not a dir — the return shape is bytes/text, not
  a `Path` (drives IC-01b); deterministic deleted-vs-unmaterialized signal (`git rev-parse --verify`);
  fail-closed without swallowing probe errors; must NOT import `specify_cli.*` (would trip the
  shrink-only `tests/architectural/test_layer_rules.py::TestMissionRuntimeBoundary` ledger) — use
  kernel/mission_runtime-local git plumbing; git-probe latency (NFR-003); #4959 non-regression.

### IC-01b — Reader content-source adoption

- **Purpose**: Extend the dir-based readers to accept a coordination-ref content source so consumers
  can read post-consolidation content that has no on-disk directory.
- **Relevant requirements**: FR-005 (consumer side), FR-001/FR-003/FR-004 (post-consolidation legs).
- **Affected surfaces**: `src/specify_cli/tasks/issue_matrix_migration.py`
  (`load_issue_matrix`/`issue_matrix_artifact_present`), `src/specify_cli/cli/commands/review/_issue_matrix.py`
  (`validate_issue_matrix`), `src/specify_cli/status/doctor.py` (`check_issue_matrix`) — each today does
  `dir / issue-matrix.{json,md}` + `.exists()`; give them a content/bytes source path.
- **Sequencing/depends-on**: IC-01a.
- **Risks**: the read contract's dir-vs-content shape must be resolved (see contract note below);
  keep the change minimal and shared so the split isn't re-authored per consumer.

### IC-shared — Two-partition split helper (DRY, MINOR-6)

- **Purpose**: Factor the `(primary_discovery_dir, coord_matrix_source)` resolution into ONE helper
  that review (IC-02), merge-completeness (IC-03), and merge-terminal-verdict (IC-04) all call, so the
  split (discovery=PRIMARY, matrix=COORD/ref) is not re-authored 3×. `status/doctor.py::check_issue_matrix`
  is the reference shape.
- **Relevant requirements**: FR-001/FR-003/FR-004 (shared), NFR-001, C-001.
- **Affected surfaces**: a shared resolver (in `mission_runtime`, or a review/merge-shared module that
  imports the seam — never a second authority).
- **Sequencing/depends-on**: IC-01b.
- **Risks**: keep it a thin composition of the seam, not a new authority.

### IC-02 — Mission-review issue-matrix gate partition split (#5171)

- **Purpose**: Make the mission-review Gate 4 read gating references from PRIMARY and authored
  verdicts from COORD/ref (via IC-shared), and replace the doctrine's raw `cat` with a resolver-backed read.
- **Relevant requirements**: FR-001, FR-002, FR-008.
- **Affected surfaces**: `src/specify_cli/cli/commands/review/__init__.py` (`_evaluate_issue_matrix` —
  the current `coord_read_dir_for(...) or feature_dir` at :428-434 feeds ONE dir into both
  `gating_issue_numbers` (:309) and the matrix read — separate them), `review/_issue_matrix.py`,
  `src/charter/offering/skills/spec-kitty-mission-review/SKILL.md:593` (Gate-4 step).
- **Sequencing/depends-on**: IC-01b, IC-shared.
- **Risks**: fully separate discovery vs matrix (not one "more correct" dir); the doctrine change must
  be a POSITIVE read (rendered Gate-4 references the resolver), not a deletion (FR-002 positive control,
  tested against SKILL.md directly).

### IC-03 — Merge issue-matrix completeness gate partition split (#4943 leg 1)

- **Purpose**: Give `_evaluate_issue_matrix_completeness_gate` `repo_root`/`mission_slug` (the caller
  `evaluate_merge_gates` already threads them to the risk/dependency gates; `executor.py:559` already
  passes both), discover references from PRIMARY via the seam (mirroring `_evaluate_risk_gate`:237 /
  `_evaluate_dependency_gate`:301, #3439), and read verdicts from COORD/ref (via IC-shared).
- **Relevant requirements**: FR-003, FR-004.
- **Affected surfaces**: `src/specify_cli/policy/merge_gates.py:360`; caller wiring at `merge_gates.py:140-142`.
- **Sequencing/depends-on**: IC-01b, IC-shared.
- **Risks**: fail-open is the worse mode — a missing row must FAIL; keep the function ≤ complexity 15
  when the signature grows (extract a helper).

### IC-04 — Merge terminal-verdict enforcement (#4943 leg 2)

- **Purpose**: Make merge apply the `in-mission`/`unknown` -> `done` rejection: refuse in `block`
  mode (naming rows) before the target advances; warn with the same list in `warn` mode (which still
  advances/records done).
- **Relevant requirements**: FR-006.
- **Affected surfaces**: `src/specify_cli/policy/merge_gates.py` as a sibling gate to
  `_evaluate_issue_matrix_completeness_gate` — the existing gate mechanism already delivers
  block-before-advance and warn-prints-list (`executor.py:559-571`: block aborts via `overall_pass`
  before `_phase_merge_lanes`; warn prints `gate.details`), so **`done_bookkeeping.py` likely needs NO
  change** (de-scoped, MINOR-5).
- **REUSE, do not re-implement (MINOR-4)**: call/factor the existing rule
  `_issue_matrix_approval_blocker` (DEFINED in `cli/commands/agent/tasks_parsing_validation.py:206`)
  with `target_lane=Lane.DONE` and the resolved `coord_matrix` + `primary_feature_dir`. Note the
  `unknown` half is enforced by a DIFFERENT (schema-validity) gate, not the in-mission lever — reuse
  both checks so `unknown` is not missed. A hand-rolled "reject in-mission set" would be a second
  authority and would miss `unknown`.
- **Make the reused rule content-aware (post-tasks MAJOR-1)**: `_issue_matrix_approval_blocker` and
  `_issue_matrix_evaluation` (`tasks_parsing_validation.py:120`) are DIR-based, so post-consolidation
  (US3.1: no worktree) pure reuse cannot go green. WP04 owns `tasks_parsing_validation.py` and threads an
  OPTIONAL coord matrix content-source through both, defaulting to current dir-behavior so the `move-task`
  caller (`tasks_move_task.py:1109`) is unaffected (backward-compatible). Function-local import into
  `merge_gates.py`; hoist the new gate_name (S1192).
- **Sequencing/depends-on**: IC-01b, IC-03, IC-shared (shares the coord verdict read).
- **Risks**: warn vs block semantics must match existing `merge_gates.mode`; read verdicts from the
  correct partition (else re-introduces the bug it fixes).

### IC-05 — Regression guard + test-remediation

- **Purpose**: A non-vacuous architectural guard that trips if any review/merge consumer reconstructs
  a topology-dependent `issue-matrix` path by hand OR bypasses the IC-shared split; re-judge and
  correct any existing test that pins the husk/residue read. Include a #4959 non-regression guard
  (other coord kinds still raise on UNMATERIALIZED — MAJOR-2).
- **Relevant requirements**: FR-008, NFR-001, C-005.
- **Affected surfaces**: `tests/architectural/` (new guard + self-mutation check), `tests/policy/`,
  `tests/specify_cli/cli/commands/review/` (re-judge buggy-behavior pins).
- **Sequencing/depends-on**: IC-01a/b, IC-02, IC-03, IC-04.
- **Risks**: guard must be non-vacuous (injecting a raw read must trip it); do not green-wash a test
  that asserts the old wrong-partition behavior — correct it.
