---
work_package_id: WP16
title: 'accept: both residual legs through the commit router'
dependencies:
- WP05
- WP12
- WP10
requirement_refs:
- FR-003
- FR-005
- FR-007
- FR-009
- SC-003
- FR-009b
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-02T02:57:19.568803+00:00'
subtasks:
- T085
- T086
- T087
- T088
- T089
phase: Phase 5 - Command consumers
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/accept.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/acceptance/__init__.py
- tests/specify_cli/cli/commands/test_accept_residual_partition.py
- tests/specify_cli/cli/commands/test_accept_clean_tree.py
- tests/specify_cli/cli/commands/test_accept_decomposition.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP16 – accept: both residual legs through the commit router

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`spec-kitty accept` cleans up its leftover ("residual") Mission files in two legs:
- **The repository-root-checkout leg** (`_commit_primary_residuals`) does a raw `git add` / `git commit` of every dirty Mission file onto the current branch. That is how COORD-partition records reach the target branch (#5440).
- **The coordination-worktree leg** (`_commit_coord_residuals`) joins coordination-relative paths onto the repository root checkout, then routes them through the write seam, where the router skips the status log. That is how coordination-only dirt is reported done while it stays uncommitted (#5513).

Accept's dirty-tree gate and its committer also classify paths differently.

After this WP, both legs go through ONE `commit_for_mission` call, which groups the files by partition (FR-005, C-001: remove a commit mechanism, add none).

Done means:
- **R7**: a COORD-partition record that is dirty in the repository root checkout is never committed to the target branch. It is reported as skipped with `COORD_RECORD_IN_ROOT_CHECKOUT`.
- **R8**: a COORD-partition record that is dirty only in the coordination worktree is committed on the coordination branch.
- **R9**: accept's dirty gate (`_filter_coordination_residue`) and its committer give the same partition answer for every path, through one shared classifier (US3.7).
- Uncommitted decision-ledger files (PRIMARY since WP12) are committed by accept on the target branch (FR-009, accept half). A positive control with an already-committed ledger is included.
- The birth cutover writes the status dir through `write_dir(STATUS_STATE)` (FR-003).
- `accept --json` adds `residual_commit: {"surfaces": [...]}`. Text renders through the shared renderer, and the exit-code rule applies.
- `lanes` and `single_branch` accept is unchanged (C-008).

## Context & Constraints

- **Spec**: FR-005 (both residual legs through the router; the raw commit is removed), FR-003 (accept's birth cutover is a writer family), FR-007 (per-surface outcome; accept's coordination residuals are a write-seam consumer today), FR-009 (accept commits uncommitted ledger files), US3.5, US3.6, US3.7, US4.7, SC-003.
- **Plan**: IC-08 (accept), IC-04 (row "Accept birth cutover" `accept.py:154/193`), IC-07 (consumers `accept.py:426`, `acceptance/__init__.py:1791, 1822`).
- **Research**: D9 (decision: one `commit_for_mission` over both legs; `COORD_RECORD_IN_ROOT_CHECKOUT`; fix the L425 join; forward `owned`; shared classifier), D7 (router owning-surface translation), D8 (consumer rendering and exit-code rule), D12 (the ledger reader flips at `acceptance/__init__.py:440`), R7, R8, R9.
- **Contract**: `contracts/commit-outcome.md` (`accept --json` adds `residual_commit.surfaces`; the `COORD_RECORD_IN_ROOT_CHECKOUT` skip reason).
- **Dependencies**:
  - WP05 (router translation, `surfaces`, named refusals, `commit_outcome.py`; via WP04, `write_dir`);
  - WP12 (the ledger is PRIMARY, so the accept gate treats ledger dirt as real work).
- **Accept test fixtures**: since #4891, accept fails closed without lanes plus a passing acceptance matrix. Reuse the existing fixtures in `tests/specify_cli/cli/commands/test_accept_residual_partition.py` (for example `test_residual_commit_handles_mixed_primary_and_coord_dirt`, ≈L293) and the "planning-lane no-op vs lane-a + passing-matrix" pattern (#5029/#5033).
- **Charter**: load `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`. Single canonical authority: one classifier, one committer.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`), review = opus.
- **Terminology**: say Mission, never feature. Name the sense of "primary": "repository root checkout", "target branch", "PRIMARY partition".
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP16` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`).
- Start with `spec-kitty agent action implement WP16 --agent claude`. Use the resolved workspace.
- **Lane-relevant sharing**: ownership is disjoint, so this WP runs in its own lane after WP05 and WP12 are approved. The plan's ordering "accept: 08 after 07 and 11" is satisfied by those dependencies.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T085 – Red-first R7, R8, R9

- **Purpose**: Prove each leg's defect separately (the post-spec squad's finding R3) and the gate/committer disagreement, through the CLI entry point. Commit these tests alone, before any fix.
- **Steps**:
  1. **R7** `test_accept_never_commits_coord_record_from_root_checkout_to_target`:
     - build a coordination-routed Mission ready for accept (lanes plus a passing matrix; reuse the file's existing fixture helpers);
     - make `status.events.jsonl` dirty in the **repository root checkout** copy;
     - run `spec-kitty accept --mission <M> --json`;
     - assert that `git log <pre-accept target tip>..<target> -- kitty-specs/<dir>/status.events.jsonl` is empty, and that JSON `residual_commit.surfaces` lists the path as skipped with `COORD_RECORD_IN_ROOT_CHECKOUT`.

     At the base, `_commit_primary_residuals` commits it.
  2. **R8** `test_accept_commits_coord_only_dirt_on_coordination_branch`:
     - make a COORD record (the status log, or `acceptance-matrix.json` when it is not rewritten by accept itself) dirty **only in the coordination worktree**;
     - run accept;
     - assert that the coordination branch tip carries the change and that the coordination worktree is clean.

     At the base it is skipped or overwritten by the L425 root-join plus the router's status-log skip.
  3. **R9** `test_accept_gate_and_committer_agree_per_path`:
     - build a mixed fixture with dirty `spec.md`, `decisions/index.json`, `decisions/DM-*.md`, `status.events.jsonl`, `traces/x.md` and `acceptance-matrix.json`;
     - for each path, assert that the gate's verdict (`_filter_coordination_residue` keeps or drops it) and the committer's partition grouping (which surface `commit_for_mission` puts it on, via `surfaces`) agree: dropped as residue ⇔ COORD on the committer, and kept ⇔ PRIMARY or real work.

     It is red at the base for `decisions/*` under `coord`.
  4. A ledger test `test_accept_commits_uncommitted_ledger_on_target` (FR-009): an uncommitted `DM-*.md` plus `index.json` in the repository root checkout is committed by accept on the target branch. The positive control `test_accept_with_committed_ledger_is_clean` exercises the same fixture with the ledger already committed and expects no residual commit for it.
- **Files**: `tests/specify_cli/cli/commands/test_accept_residual_partition.py`.
- **Validation**: R7, R8, R9 and the ledger test are red on the WP base, and the control is green. Paste the outputs into the activity log.
- **Edge cases**:
  - Accept itself rewrites `acceptance-matrix.json`. Pick fixture dirt that accept does not regenerate, or assert after the run on content you control.
  - Make the existing tests at ≈L163-293 keep passing. Some of them assert `_commit_primary_residuals` behaviour for PRIMARY kinds; those still hold through the router.
- **Re-derive red reasons on the actual lane base (post-tasks squad R-M6)**: this WP's base contains WP01–WP05, WP11 and WP12. Run each test there first and record the per-path red reason in the activity log, so the reviewer's red-on-base check predicts the right failure. Expected (verify; do not trust):
  - R7: `_commit_primary_residuals` still raw-commits the root-checkout `status.events.jsonl` onto the target (WP05 does not touch accept);
  - R8: the `_commit_coord_residuals` root-join (≈L425) hands non-existent root paths to the write seam, so the coordination-only row is skipped or `unchanged` despite WP05's translation;
  - R9: `decisions/*` already agree after WP12 (gate and router both say PRIMARY). Pick paths that still **disagree** on this base, e.g. `traces/*.md`, which the gate treats as coordination residue while the router stages it to the coordination branch. Assert per path;
  - the committed-ledger control: green on the base.

### Subtask T086 – Remove the raw commit; one router call over both legs

- **Purpose**: Remove the fifth commit mechanism (C-001; research D9).
- **Steps**:
  1. Delete `_commit_primary_residuals` (accept.py ≈L370-402, the raw `run_git(["add", ...])` / `run_git(["commit", ...])`).
  2. Rewrite `_commit_residual_acceptance_artifacts` (≈L445):
     - collect `primary_dirty = _primary_dirty_paths(...)` (≈L111) as **repository-root paths**;
     - collect `coord_dirty = _coord_dirty_paths(..., owned=owned)` (≈L196) as **coordination-worktree absolute paths**. Do NOT join coordination-relative paths onto `repo_root`: that is the L425 bug, `files = tuple(repo_root / path for path in dirty)`. Resolve them against the coordination worktree root (`_coord_worktree_root`, ≈L117) or `write_dir(...).path`.
  3. Make one call: `commit_for_mission(repo_root=..., mission_slug=..., files=<both lists>, message=f"Finalize acceptance artifacts for {mission_slug}", policy=ProtectionPolicy.resolve(repo_root), kind=MissionArtifactKind.ACCEPTANCE_MATRIX, owned=owned)`.
     - The router groups by partition: PRIMARY files go to the target branch, and COORD files go to the coordination branch as owning-surface copies (WP05's translation, D7).
     - `owned` is forwarded; today it is dropped.
  4. Replace `_commit_coord_residuals` (≈L405-442) with this single path, or keep it as a thin internal helper only if it carries no second commit mechanism. The `write_seam.write_artifact` call goes away for this caller (accept is listed under write-seam consumers in D8; after this change it consumes `CommitRouterResult` directly).
  5. Error mapping: if any surface is `refused` or `error`, raise `TaskCliError` naming the surface, branch and reason, rendered via `render_commit_outcome`. Otherwise return whether any surface committed.
- **Files**: `src/specify_cli/cli/commands/accept.py`.
- **Validation**:
  - R7 and R8 are green;
  - existing residual tests are green;
  - `grep -n 'run_git(\["commit"' src/specify_cli/cli/commands/accept.py` finds no residual raw commit.
- **Edge cases**:
  - A protected target branch: PRIMARY residuals are refused with `PROTECTED_BRANCH_REFUSED`, as the router decides. Previously the raw commit landed on HEAD regardless; that is a behaviour change for protected targets, so note it in the activity log. Check the `#2739` protected-primary tests.
  - Owned checkouts: `_coord_dirty_paths(..., owned=owned)` paths resolve under the owned coordination workspace.
- **One-time revert check (post-tasks squad R-m2)**: after GREEN, locally revert each half once and record the result in the activity log (do not commit the reverts):
  - restore the raw commit → R7 goes red;
  - restore the L425 root-join → R8 goes red.
  This proves each leg's fixture is load-bearing.

### Subtask T087 – Outcomes: root-checkout COORD residue skipped, ledger committed, JSON and text rendering

- **Purpose**: Honest reporting (FR-007), with the ledger as real work (FR-009).
- **Steps**:
  1. A COORD record dirty only in the repository root checkout surfaces in the router result as skipped with `COORD_RECORD_IN_ROOT_CHECKOUT` (WP05 T028 provides the fate). Accept reports it and never commits it to the target branch.
     - Do not "clean" the root copy silently. Report it with a remediation hint. The single-home rule makes the coordination copy authoritative, so a later seed or doctor run handles a stale root copy.
     - Confirm the expected operator action against spec US3.5 before deciding wording.
  2. Ledger files (`decisions/DM-*.md`, `decisions/index.json`): after WP12 they classify as PRIMARY, so the router groups them to the target branch. R9 and the ledger test from T085 turn green.
  3. JSON: the accept payload builder (`_summary_payload` ≈L572 or the final envelope; find where `--json` output is assembled) adds `residual_commit: {"surfaces": commit_outcome_payload(result)["surfaces"]}` when a residual commit ran, additively.
  4. Text: print `render_commit_outcome(result)` lines after the acceptance summary.
  5. Exit code: non-zero iff any surface is `refused` or `error` (shared helper). A `skipped` outcome exits 0 and is rendered.
- **Files**: `src/specify_cli/cli/commands/accept.py`.
- **Validation**: assert the JSON shape in R7 and R8; a text-output assertion; an exit-code test with a refused coordination surface (hold the status lock → `STATUS_LOCK_HELD`).
- **Edge cases**: accept's own commits (the acceptance meta commit through `commit_for_mission` at `acceptance/__init__.py` ≈L1791-1830) are separate. Do not merge them into the residual call.

### Subtask T088 – One shared classifier for the gate and the committer; render at acceptance commits

- **Purpose**: US3.7, where the gate and the committer must give the same partition answer for every path. Single canonical authority: no second classifier.
- **Steps**:
  1. `acceptance/__init__.py::_filter_coordination_residue` (≈L411; predicate at ≈L440) drops paths by `is_coord_residue_churn(path, mission_slug=feature)` (`coordination/coherence.py` ≈L159), gated by `_mission_routes_through_coordination`. The committer groups by `kind_for_mission_file` inside the router.
     - ~~(superseded by P-M5 / round 3: no `_is_coordination_owned`)~~ Make both consult the **same** decision: the gate calls WP05's public per-path partition predicate, defined in terms of `kind_for_mission_file` plus `is_coord_residue_churn` under the Mission's stored topology.
     - Use it from the gate. Accept's committer does not pre-classify (the router does), so add a test-level assertion (R9) that the router's grouping equals WP05's public partition predicate for every fixture path.
     - Do NOT add a classifier inside `accept.py`.
  2. Verify the gate treats `decisions/*` as real work after WP12. That flows from the taxonomy, so no special case is needed. A special case here would be a second authority.
  3. Render per-surface outcomes at `acceptance/__init__.py` ≈L1791 (the protected-primary acceptance commit through `commit_for_mission`, which reads the status) and ≈L1822 (the second commit, whose result is discarded today: warn only when a surface is not committed/unchanged, D8). Keep the existing `AcceptanceError` semantics for the first commit.
- **Files**: `src/specify_cli/acceptance/__init__.py`.
- **Validation**:
  - R9 is green;
  - existing acceptance tests are green (`tests/acceptance/`, `tests/specify_cli/acceptance/` if present; `grep -rl "_filter_coordination_residue" tests`);
  - C901 of the touched functions stays at or below 15.
- **Edge cases**:
  - `owned` must flow into the shared function so owned checkouts classify identically.
  - Flat or legacy Missions (`_mission_routes_through_coordination` false) keep today's "no residue filtering" behaviour (C-008).
- **No new classifier (post-tasks squad P-M5)**: do not add an `_is_coordination_owned()` (or similar) helper. The dirty gate calls WP05's public per-path partition predicate (`partition_for_mission_path` or the name WP05 chose), which is the same function the router's grouping uses. The agreement test then holds by construction, and still asserts per path.

### Subtask T089 – Birth cutover through `write_dir(STATUS_STATE)`; C-008 controls

- **Purpose**: Accept's birth cutover is an FR-003 writer. Today it derives its write dir from `read_dir`, and for an EMPTY or UNMATERIALIZED coordination surface it returns `None`, so `cutover_mission` collapses onto the PRIMARY `feature_dir`: a write into the repository root checkout.
- **Steps**:
  1. `_coord_status_feature_dir` (accept.py ≈L154-193):
     - keep the `assert_safe_path_segment` guard;
     - for a coordination-routed Mission, return `placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE).path`. This materializes, seeds or refuses per WP03/WP04: DELETED → `CoordinationBranchDeleted`; remote-only → `COORDINATION_WORKTREE_UNMATERIALIZED`; fork → `COORD_SEED_FORK_REFUSED`. Accept refuses with the actionable message;
     - return `None` only for non-coordination topologies (where `write_dir(...).surface == "primary"`), so the `cutover_mission` contract for flat Missions is unchanged;
     - update the docstring: no EMPTY/UNMATERIALIZED → `None` fallback for coordination-routed Missions any more.
  2. The call site (≈L238, `_stamp_birth_cutover_for_accept`) needs no change beyond handling the new refusals: render them as accept errors with the recovery hint.
  3. Tests:
     - a pre-fix Mission (WP02 `make_prefix_coord_mission`, worktree EMPTY) running accept seeds the coordination surface once, writes the cutover there, and restores the root-checkout copy;
     - a `lanes` and a `single_branch` Mission accept exactly as today (C-008 control: same files touched, same commits).
- **Files**: `src/specify_cli/cli/commands/accept.py`, `tests/specify_cli/cli/commands/test_accept_residual_partition.py`.
- **Validation**:
  - new tests are green;
  - `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py` and the accept CLI tests are green;
  - WP20's gate will scan `accept.py::_coord_status_feature_dir`. Keep that qualname, or record a rename in the activity log.
- **Edge cases**: `resolve_artifact_surface` is no longer needed for the write decision. Remove its import if it is unused (ruff will flag it).
- **`WriteLocation.checkout_root` (post-tasks squad P-M3):** take the checkout root from `write_dir(kind).checkout_root` (WP03/WP04). Never derive it as `.path.parent.parent` or by guessing a worktree name.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Keep `_commit_residual_acceptance_artifacts -> bool` (operator decision).** Callers and tests depend on it:
  - `tests/specify_cli/cli/commands/test_accept_decomposition.py:202` monkeypatches it, and L687 asserts `... is False`;
  - the CI-owned integration test `test_accept_matrix_coord_partition.py:361` asserts `created is True`.
  - Add a **private helper returning `CommitRouterResult | None`** for JSON/text rendering; the bool wrapper calls it.
- **Drop T088 step 1 (`_is_coordination_owned`)**: P-M5 wins. The gate calls WP05's public per-path partition predicate. This removes the contradiction.
- **`test_accept_clean_tree.py::test_residual_acceptance_commit_is_scoped_to_mission_paths` (L325; now owned)**: it has no `meta.json`, a root-level `acceptance-matrix.json` and a pre-staged unrelated file. Through the router it may fail topology resolution, or hit `SafeCommitBackstopError` (`git/commit_helpers.py:393-419`). **Run it first.** Then either re-pin it deliberately (with rationale) or make the router path tolerate the pre-staged foreign path. Decide, and record the decision in `design-decisions`.
- **`write_seam.py:55` docstring**: it names `_commit_coord_residuals` as the canonical write-seam consumer. Update it as a **declared out-of-map edit**; this WP now depends on WP10, which owns `write_seam.py`. Also tell WP20 that the consumer list entry is now this WP's helper.
- **Lines and qualnames**: the root-join is at **L427** (`files = tuple(repo_root / path for path in dirty)`), and the call site is L1079. Keep the qualname `_coord_status_feature_dir`, which is in WP20's census.
- **Protected target**: the raw commit becoming a router `PROTECTED_BRANCH_REFUSED` is a behaviour change. Run `#2739` tests and `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py` by name.
- **C3**: the accept help and output say accept now commits an uncommitted decision ledger on the target branch. Record the reference-doc delta for WP22.
- Red reasons were re-derived on this WP's lane base (R-M6, already folded); `traces/*.md` is the path that disagrees for R9.

## Targeted test surface

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_accept_residual_partition.py -q
uv run --frozen pytest $(grep -rl "cli.commands.accept\|commands/accept\|_filter_coordination_residue\|perform_acceptance" tests --include="test_*.py" | grep -v -e integration -e e2e -e architectural) -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py tests/coordination/test_commit_outcome.py -q
uv run --frozen pytest tests/acceptance/ -q
make test-fast
```

- Never run the bare `tests/architectural/`, any e2e or integration directory (for example `tests/integration/test_accept_matrix_coord_partition.py` is CI-owned; cite it in the PR), performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record the commands and counts in the activity log.
- **Baseline-red gotcha**: classify reds you did not cause as one of: known P0, CI environment (auth, `SPEC_KITTY_SKIP_PRE_REVIEW_GATE`), stale install, or stale venv.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004): `_commit_residual_acceptance_artifacts`, `_coord_status_feature_dir`, `_filter_coordination_residue`, and the acceptance commit functions.
- `ruff check` and `ruff format --check` on the changed files; `mypy --strict` on the changed files. No new suppressions (NFR-005).
- ≥ 90% coverage on new and changed lines, with a focused test per branch, including refused-surface and owned-checkout arms (NFR-003).
- No empty or effect-free exception handlers (Sonar).
- C901 watch list (post-tasks squad R-m7): `accept.py::_print_acceptance_result` is at C901 13 at the base. If the residual-commit rendering touches it, extract first and keep it ≤ 15.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5440 #5513 #5023

## Definition of Done

- R7, R8, R9 and the ledger test were red on the WP base and are green on the final commit. The committed-ledger control is green.
- `_commit_primary_residuals` is gone, and both legs make one `commit_for_mission` call with `owned` forwarded. The L425 root-join is gone.
- Root-checkout COORD residue is reported as `COORD_RECORD_IN_ROOT_CHECKOUT` and never lands on the target branch.
- The gate and the committer share one classifier, and the agreement is proven path for path.
- The birth cutover writes via `write_dir(STATUS_STATE)`, and the refusals are actionable.
- `residual_commit.surfaces` is in the JSON, text renders through the shared renderer, and the exit-code rule applies.
- C-008 controls are green. ruff, format and mypy are clean; coverage is at least 90%.

## Risks & Mitigations

- **Operator-visible behaviour change**: accept now commits uncommitted ledger files on the target branch, and refuses rather than raw-commits on a protected target. Mitigation: call it out in the PR; the tests pin both.
- **Accept fixture fragility** (lanes and matrix requirements after #4891). Mitigation: reuse the existing fixtures in the owned test file; never weaken accept's gates to make a fixture pass.
- **A hidden second classifier.** Mitigation: R9 compares the gate's answer with the router's grouping on a mixed fixture.

## Review Guidance

- The reviewer (opus, a different agent from the implementer) verifies red→green: R7, R8, R9 and the ledger test were RED on the WP base and are GREEN on the final commit.
- Revert each leg's fix in turn (mentally or on a scratch branch) and confirm its fixture would turn red. This is the post-spec squad's finding R3: two fixtures, each proving one leg.
- Confirm no raw `git commit` remains in accept.py, and no classification logic is duplicated outside the shared function.
- Confirm `owned` flows end to end.

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

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-02T14:48:28Z – cursor – shell_pid=1009208 – Cycle 3: primary_ref is accept-only; target_branch no longer retargets other PRIMARY callers. HEAD-mismatch, markup, and caller census pinned.
