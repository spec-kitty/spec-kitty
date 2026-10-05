---
work_package_id: WP03
title: 'Track A: consolidation consumers and one directory on the target'
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- FR-018
- FR-019
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T06:57:39.700736+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
- T017
phase: Phase 1 - Track A (bare-slug consolidation)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_bare_slug_alias_consumers.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/phase_bookkeeping.py
- src/specify_cli/consolidation/bookkeeping_projection.py
- tests/consolidation/test_reconciliation.py
- tests/consolidation/test_bookkeeping_projection_seam.py
- tests/consolidation/test_bare_slug_alias_consumers.py
- tests/integration/test_merge_lane_planning_data_loss.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP03 – Track A: consolidation consumers and one directory on the target

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then read `.kittify/charter/charter.md` (sections "Quality & Tech-Debt Standing Orders" and "ATDD-First Discipline") and run `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission nightly-suites-green-01M44FEP` or the Activity Log below).
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

Layers 2 and 3 of the red, plus the end state the operator ruled on.

- `spec-kitty consolidate` lands a bare-slug coordination Mission on a protected target with exit 0 and a full coordination teardown (FR-001).
- The target ends with exactly one Mission directory, the primary one, holding the complete status event log; no composed-name directory sits beside it (FR-019). Mechanism: the composed directory's two status files are removed in the existing bookkeeping commit, after their events are proven present in the primary log.
- Under `--strategy merge` the same Mission consolidates too. If, and only if, that needs it, the reconciliation gate treats the composed directory's status pair as bookkeeping and nothing else under that name; a different Mission's directory still fails the gate (FR-004).
- The reproduction runs the real bookkeeping door and asserts the end state; it is the proof for the partition fix, the teardown fix and the fold.
- A Mission whose primary directory carries the composed name is unchanged (FR-005).
- A consumer is converted only when a test proves it: reverting that consumer alone turns a test red (FR-003).
- The #5651 reproduction keeps its `regression` marker and its docstring says what it now pins and that it runs the real bookkeeping door (FR-018).

**STOP conditions, verbatim.** A fold that needs a new destructive git operation, or an edit outside owned files / in a do-not-touch path → stop and report to the orchestrator.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 1, FR-001 to FR-006, FR-018, FR-019, C-001, C-002, C-005), `plan.md` (section "Design notes / Track A" and the Implementation Concern Map), `research.md` (D1 to D3), `research/code-grounding.md` (sections 3, 6 and 9.1 to 9.4).

**The defect (#5651, tracked by #5611).** A coordination Mission whose primary directory is the bare slug (`kitty-specs/<slug>`) while its coordination branch and coordination directory use the composed `<slug>-<mid8>` name cannot consolidate onto a protected target. It regressed with `5b5699e500`. The red has three layers, each proven by an in-memory probe:

1. The seed commit groups the composed-directory status files to the PRIMARY partition, is refused on the protected branch and leaves them untracked.
2. With layer 1 fixed, the reconciliation gate fails on `kitty-specs/<slug>-<mid8>/status.events.jsonl` because `_is_bookkeeping` anchors on the bare slug.
3. With layers 1 and 2 fixed, teardown reads `meta.json` from the status directory, which has none, so `mid8` is empty and the coordination worktree is never destroyed.

**Operator rulings (2026-10-05).** (a) Alias authority: keep the composed coordination directory and add one exact alias set `{primary directory name, composed <slug>-<mid8> name}`, with `mid8` read from recorded identity and never prefix-matched. (b) One directory on the target: the consolidated Mission leaves exactly one Mission directory on the target, the primary one, with the complete event log.

**Track A work packages.** WP01 enablers, WP02 alias authority and partition classification, WP03 consolidation consumers and the one-directory end state, WP04 refused-seed backstop. Tracks B and C share no file with Track A.

**Fix at the seam (C-002).** Fix on the callee side. Do not change a fixture to make a test pass; the sibling test `test_explicit_delete_override_still_reachable` is green today only because `c5f1280aeb` re-keyed its fixture.

**Operator steer on the reproduction's mocks (2026-10-05).** "changing a mock is allowed and not considered 'tampering' with a test." Spec C-002 now reads: the reproduction's fixture data and assertions are not weakened to make it pass; replacing a mock of in-repository product code with the real code path is allowed. This overrides the sentence above about not changing a fixture as far as mocks are concerned: fixture DATA stays, mocks of product code may go.

**Test-design scrutiny (measured on `9adc68803f`, `research/code-grounding.md` section 11).** `_real_merge_external_mocks` patches 11 names plus 2 per-test extras, all in-process product code: it removes the `done` record, the bookkeeping commit door, the porcelain invariant and, per test, both durability asserts. A real-door helper exists in the same file: `_real_bookkeeping_commit_external_mocks` (`:911`). With the partition and teardown fixes plus the fold, and no `_is_bookkeeping` change, the bare-slug reproduction on the real door passes under squash with one directory, 1 `done` event (9 log lines) and a clean checkout. Under `--strategy merge` it fails without the alias leg, with three commits flagged.

**The one permitted edit in a do-not-touch file (only if T012 proves it is needed).** `src/specify_cli/consolidation/reconciliation.py` belongs to the running mission #5668 (the approved-claim bound). By operator ruling you may change the body of the module-level function `_is_bookkeeping` (defined at `:1166`, body to `:1243`) and nothing else in that file: not its signature, not its three call sites (`:1163` in `MergeOutcomeVerifier._is_bookkeeping_path`, `:1651` and `:1876` as `functools.partial`), not `_commit_is_content` (`:1137`), not `_planning_prefix` (`:2055`), not the claim dataclass. Keep the diff inside that body as small as possible so a later rebase against #5668 stays trivial.

**Imports.** `reconciliation.py` imports nothing from `mission_runtime` or `coordination.coherence` at module top (`:44-79`: only `core.constants`, `lanes`, and sibling `consolidation` modules). A top-level import is a hunk outside the permitted body. Any import the `_is_bookkeeping` body needs is therefore function-local, inside the body (or inside the one adjacent private helper), with a one-line comment saying why.

**Verified code facts for this work package (base `9adc68803f`).**

- `_is_bookkeeping(path, mission_slug, planning_prefix)`: the first leg (`:1237-1238`) returns True for any path containing the segment pair `kitty-specs/<mission_slug>`; it exempts a whole subtree, so `spec.md` under the Mission directory is exempt today. The second leg (`:1239`) exempts `planning_prefix` as an exact path prefix. `planning_prefix` comes from `_planning_prefix(repo_root, feature_dir)` (`:2055`, called at `:1398` in `build_approved_wp_set`): the status directory relative to the repository, which under coordination topology is the nested coordination-worktree path whose final segment is the coordination directory name.
- `src/specify_cli/consolidation/executor.py`: `_run_lane_based_consolidation` at `:430` resolves `feature_dir = _resolve_run_status_dir(seam)` at `:487`; `_run_lane_based_consolidation_locked` at `:191` fills `target_feature_dir` at `:227` and passes it into `_MergeRunState` at `:289`.
- `src/specify_cli/consolidation/run_state.py`: `_MergeRunState` fields `mission_slug` (`:179`), `feature_dir` (`:182`), `target_feature_dir` (`:183`).
- `src/specify_cli/consolidation/bookkeeping_projection.py`: `_target_bookkeeping_status_paths` at `:68` already derives the target directory through `placement_seam(main_repo, slug).read_dir(...)` when the status directory is under `.worktrees`; `_project_status_bookkeeping_to_target` at `:282`; `_post_checkpoint_mission_paths` at `:407` scopes the diff with `mission_prefix = f"{KITTY_SPECS_DIR}/{mission_slug}/"` (`:427`) and classifies with `kind_for_mission_file(candidate, mission_slug=mission_slug)` (`:467`); `project_post_checkpoint_commits_to_target` at `:474` rebuilds the same prefix at `:506`. For a bare-slug Mission the coordination ref holds its records under the composed name, so a prefix built from the bare slug matches nothing (hypothesis from the grounding; prove it red before converting).
- `src/specify_cli/consolidation/phase_bookkeeping.py`: the projection call at `:323`; the post-merge invariant's residue predicate at `:567` is `is_toolchain_generated_churn(path_part, mission_slug=run.mission_slug)`.
- `src/specify_cli/consolidation/phase_gate.py:179 _rollback_target_after_failed_reconciliation` and `rollback.py::rollback_to_snapshot` are the rollback authority; you call nothing new there.
- **Phase order of one consolidation** (`executor.py:362-384`):
  1. `_resolve_run_status_dir` (`executor.py:487`) seeds `kitty-specs/<slug>-<mid8>/{status.events.jsonl,status.json}` and commits them on the coordination branch, which is the mission branch.
  2. `_phase_merge_lanes`, `_phase_baseline_and_surface`, `_phase_bake_and_pre_target_done` (`phase_advance.py:335`; `done` events go to the composed log).
  3. `_phase_mission_to_target` (`phase_advance.py:535`) fixes the landed tree: the mission-branch tip, squashed in `lanes/consolidation.py` (a do-not-touch file). The composed directory rides along here.
  4. `_phase_capture_and_baseline`, `_phase_record_done_and_project` (the union into the primary directory, working tree only; `bookkeeping_projection.py:309-353` already does it), `_phase_porcelain_invariant`, `_phase_commit_and_assert` (`phase_bookkeeping.py:602`, the bookkeeping commit on the target).
  5. `_phase_reconcile_before_teardown`, then teardown. The squash gate reads the NET diff `window_base..target` after step 4 (`reconciliation.py:1083`, `:1122`).
- **Design probe (2026-10-05, `research/code-grounding.md` section 10)**: fold on with squash: passed, one directory, 8 event lines. Fold off: reconciliation FAILED and rolled back. Fold on with `--strategy merge`: FAILED without the alias leg, passed with it.
- On the base the reproduction mocks `commit_merge_bookkeeping` (`patch_executor_family("commit_merge_bookkeeping")`, `tests/integration/test_merge_lane_planning_data_loss.py:410`), so the bookkeeping commit never runs inside it; T011 switches it to the real-door helper.
- Measured end state with a three-layer probe patch (grounding 9.2): two directories on the target, `retention-override/` with all six files and 8 event-log lines, and `retention-override-01KX0000/` with `status.events.jsonl` and `status.json` and 6 lines (a strict subset). The canonical sibling ends with one directory and 8 lines. `coordination_branch == mission_branch` is the real shape, so a composed directory committed on that branch rides to the target with the Mission's content.
- The reproduction: `tests/integration/test_merge_lane_planning_data_loss.py:1886-1982`, constants `_BARE_SLUG` and `_COMPOSED_BRANCH` at `:1882-1883`, helpers `_invoke_merge_cli` (`:1473`), `_real_merge_external_mocks` (`:400`), `_write_coord_retaining_meta` (`:1450`). On the base it also patches `_assert_merged_wps_done_on_target` and `_assert_baseline_merge_commit_on_target` inline; T011 drops both.

### Paths owned by running missions (do not edit)

Copied from `research/code-grounding.md` section 6. Paths are relative to `src/specify_cli/` unless they start with `tests/` or are a root file.

| Running mission | Paths |
|---|---|
| #5635 | `cli/commands/implement*.py`, `agent/workflow_executor.py`, `coordination/planning_commit.py`, `core/dependency_graph.py`, `lanes/implement_support.py`, `status/emit.py`, `status/__init__.py`, `workspace/context.py`, `pyproject.toml`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_wp_integrity_partition_call_shape.py`, `tests/architectural/dead_symbol_allowlist.yaml` |
| #5634 | `core/mission_creation*.py`, `tests/core/test_mission_create_coord_status_*.py` |
| #5573 | `lanes/compute.py`, `lanes/compute_and_persist.py`, `lanes/frozen_membership.py`, `lanes/lane_tip.py`, `lanes/models.py`, `cli/commands/agent/mission_finalize*.py`, `tests/specify_cli/cli/commands/agent/**` |
| #5457 | `upgrade/runner.py`, `lanes/consolidation.py`, `lanes/auto_rebase.py`, `lanes/stale_check.py`, `lanes/worktree_allocator.py`, `state/contract.py`, `tests/architectural/test_destructive_op_routing.py` |
| #4925 (PR #5709) | `cli/commands/upgrade.py`, `upgrade/finalize.py`, `upgrade/outcome.py`, `skills/manifest_store.py`, `tool_surface/repair.py` |
| #5668 | `consolidation/reconciliation.py`: the approved-claim bound. Only the body of `_is_bookkeeping` may change, and only in WP03. |
| #3931 | `cli/commands/agent/tasks_move_task*.py`, `cli/commands/_git_remedies.py`, `cli/commands/agent/tasks_parsing_validation.py` |

Also off limits for every work package of this mission: `src/mission_runtime/artifacts.py`, any `.github/workflows/*.yml`, `.github/ci-module-registry.yml`, and `kitty-specs/**`.

**Rule.** An edit outside this work package's `owned_files` needs a one-line rationale in your hand-back. An edit in a path listed above is a STOP: make no such edit, and report to the orchestrator what you found and why the listed path seems to need a change.

### Commit order and commit hygiene (charter C-011, spec C-005)

1. Tidy-first enabler commit(s): behaviour-preserving, with their focused tests.
2. Failing-test commit: the test goes through the pre-existing entry point and is red on this work package's base for the reason named in the subtask. Record the red output (test id plus the failing assertion line) in your hand-back.
3. Fix commit(s): the failing test turns green; new branches are covered by tests in the same commit.

Marker convention (ADR `docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md`, amendment at line 70): `p0_repro(issue=N)` is only for a reproduction of an OPEN P0 that must stay off the per-pull-request path; `regression` is the marker for an issue-pinned guard of a bug that is fixed, and it runs per pull request. Tests added here guard bugs fixed in the same pull request, so they never carry `p0_repro`.

Every commit message ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No commit message, code comment, docstring or document names an AI tool or a model.

### Quality bar (spec NFR-005)

- Cyclomatic complexity at most 15 per function (`ruff` C901). Extract a helper before a function reaches 16.
- `mypy --strict` clean for every changed source file; no new `# type: ignore`, no new `# noqa`.
- A string literal used three or more times in one module becomes a named module constant.
- Every new branch and helper has a test in the same commit.
- No empty or effect-free `except` block.

### Tracer files

Do not edit anything under `kitty-specs/`, including `kitty-specs/nightly-suites-green-01M44FEP/traces/`. Put tooling friction, approach changes and design choices in your hand-back as three short lists; the orchestrator appends them to the tracer files.

## Branch Strategy

- **Strategy**: lane worktree per computed lane (`lanes.json`); this mission's topology is `lanes`.
- **Planning base branch**: `issue-5611-5419-nightly-green`
- **Merge target branch**: `issue-5611-5419-nightly-green`
- **Dependencies**: WP02

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start with `spec-kitty agent action implement WP03 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

**Execution order: T011, T013, T014, T012, T015, T016, T017.** The `_is_bookkeeping` leg (T012) comes after the fold (T014), because under the default squash strategy the fold alone is sufficient (measured) and the leg's only proof is the `--strategy merge` variant.

### Subtask T011 – The reproduction runs the real bookkeeping door (red test)

- **Purpose**: Make the reproduction prove the contract. As written it asserts only exit 0, and with its mocks it would go green with two status homes, zero `done` events and a dirty root checkout. Operator ruling (2026-10-05): replacing a mock of in-repository product code with the real code path is allowed and is not tampering with the test.
- **Steps**:
  1. In `test_bare_slug_coord_mission_consolidates_onto_a_protected_target` (`:1886`), replace `_real_merge_external_mocks(tmp_path)` with `_real_bookkeeping_commit_external_mocks(tmp_path)` (`:911`, the helper added for #2934 that leaves `commit_merge_bookkeeping`, `_mark_wp_merged_done` and the durability asserts real), and drop the test's two inline patches of `_assert_merged_wps_done_on_target` and `_assert_baseline_merge_commit_on_target`. The real bookkeeping commit, the real `done` marking and the real durability asserts now run.
  2. Keep the fixture DATA unchanged: bare primary directory, composed coordination branch, the meta edits, protected target, one approved code work package.
  3. Strengthen the assertions; never loosen one. Read from the target ref (`git ls-tree`, `git show main:...`), not from the working tree alone:
     - exit code 0;
     - exactly one Mission directory on the target: `kitty-specs/<slug>/` exists, no `kitty-specs/<slug>-<mid8>/`;
     - the primary `status.events.jsonl` on the target holds the complete event log including the `done` event(s): assert the event SET (by `event_id`, and by `wp_id` / `to_lane` for the `done` transition), equal to the fixture's events plus the run's. Do not assert a bare line count;
     - the coordination branch and the coordination worktree are gone;
     - the root checkout is clean: `git status --porcelain` prints nothing.
  4. Note what the real-door helper still stubs: `_classify_porcelain_lines` is short-circuited in it too (`:931`), so the product's porcelain invariant is not exercised by this helper; the test's own `git status --porcelain` assertion covers the end state. Do not edit either shared helper.
  5. Leave `_real_merge_external_mocks` (`:400-446`) and every other test that uses it untouched.
  6. Commit the test alone, red. It is red on your base and stays red until T014. Record what is red: on the base, the consolidate exit (the reconciliation gate FAILS on the composed status files and rolls back).
- **Files**: `tests/integration/test_merge_lane_planning_data_loss.py`.
- **Parallel?**: No; first.
- **Notes**: Keep the `regression` marker; no `p0_repro`. There is no separate sibling test.

### Subtask T013 – No run-state field unless a red proof needs one

- **Purpose**: FR-003's rule applied to plumbing: neither the fold of T014 nor the leg of T012 (it reads `planning_prefix`) (it reads `run.feature_dir`, the status directory) needs a resolved alias set on the run.
- **Steps**:
  1. Add nothing to `src/specify_cli/consolidation/run_state.py` or `executor.py` unless a consumer with a red proof needs it. Expected outcome: no edit to either file.
  2. Say in the hand-back which it was. If you did add something, name the consumer and the test that goes red without it.
- **Files**: none expected. The two files stay in `owned_files` in case T015 produces a proof.
- **Parallel?**: No.

### Subtask T014 – Fold in the existing bookkeeping commit

- **Purpose**: FR-019. The composed directory's status pair rides the squash onto the target; the union of its events into the primary log already happens. What is missing is that the pair is removed from the target tree, in the bookkeeping commit that already exists.
- **Steps**:
  1. Add a helper to `bookkeeping_projection.py` (suggested: `coordination_alias_status_paths(*, main_repo, mission_slug, status_feature_dir) -> tuple[Path, ...]`). It returns `()` unless `status_feature_dir` is under `.worktrees` (`coordination/surface_resolver.py:488 is_under_worktrees_segment`) AND its directory name differs from the primary directory name; otherwise it returns the files that exist among `main_repo/kitty-specs/<status_feature_dir.name>/status.events.jsonl` and `.../status.json`. The name and exact signature are yours to adjust; the constraints are not.
  2. In `phase_bookkeeping.py::_phase_commit_and_assert` (`:602`), after the `path.exists()` filter (`:637`):
     - collect the helper's paths;
     - capture them into `run.final_bookkeeping_snapshots` with `_capture_merge_snapshots`, as the phase's other paths are (`:238-253`);
     - BEFORE unlinking, assert that every `event_id` in the target-side composed log is present in the unioned primary log (`run.target_events_path`). If one is missing, raise: fail closed, delete nothing. This must cover the real `done` event: unmocked, it is written to the composed log first (a `chore(spec-kitty): status transition <WP>` commit) and reaches the primary log only through the union;
     - `Path.unlink` the two files;
     - append them to `files_to_commit`, so the existing door commits the deletion in the SAME bookkeeping commit: `commit_merge_bookkeeping` (`:642`) reaches `safe_commit`, whose `git add --force -- <path>` followed by `git commit --only` stages a tracked-but-missing file as a deletion.
  3. Update the NOTE at `:633-636` ("It is NOT deletion-safe ... inert today"): the filter still drops absent paths, and the alias status pair is appended after it on purpose. Also re-read the comment above it (`:622-624`, "hard-fails if one is missing"): it describes a never-tracked path; make the two statements consistent with what you observe.
  4. Constraints: no new git argv; no run-state field; no edit to `lanes/consolidation.py`, `phase_advance.py` or `rollback.py`. Only those two files are removed: any other file under the composed name stays on the target and still fails the gate (FR-004).
  5. Tests, red first:
     - the reproduction (T011, real bookkeeping door, squash) turns green: one directory, complete event set including `done`, clean root checkout. It is this subtask's red proof;
     - canonical Mission: the helper returns `()` and the target tree is byte-identical to base behaviour;
     - a non-status file under the composed name is neither removed nor exempted: the gate FAILS and the target is rolled back;
     - the event-preservation assert fires when the composed log holds an event the union lacks, and no file is deleted;
     - `--resume` after an interruption between the unlink and the commit is idempotent, IF cheaply testable; otherwise record it as an unverified residual in the hand-back;
     - unit tests for the helper in `tests/consolidation/test_bookkeeping_projection_seam.py` (not under `.worktrees`; same name; both files; one file; none).
     Focused non-integration cases go in `tests/consolidation/test_bare_slug_alias_consumers.py`.
  6. Check and report each of these unverified hypotheses:
     - the composed paths are accepted by `_capture_merge_snapshots`' trusted roots;
     - real, unmocked `done` events take the same path (composed log, then union, then fold): measured once in the scrutiny probe (1 `done` event, 9 log lines); confirm with the reproduction's event-set assertion;
     - the real porcelain invariant is unaffected (the unlink happens after `_phase_porcelain_invariant`). The real-door helper still stubs `_classify_porcelain_lines`, so check this once with that patch lifted locally and report the result;
     - other coordination-kind files under the composed name would still ride the squash to the target (none exists in the fixture). If one exists in practice, STOP and report; do not widen the deletion.
- **Files**: `src/specify_cli/consolidation/bookkeeping_projection.py` (one helper), `src/specify_cli/consolidation/phase_bookkeeping.py` (`_phase_commit_and_assert` and the NOTE), `tests/consolidation/test_bookkeeping_projection_seam.py`, `tests/consolidation/test_bare_slug_alias_consumers.py`, `tests/integration/test_merge_lane_planning_data_loss.py`.
- **Parallel?**: No.
- **Notes**: Rollback is already covered: the phase is decorated `@_records_post_mutation_tips` (`:601`), and the design probe observed `main` restored when the gate failed after the deletion commit. `orchestrator-api consolidate-mission` inherits the fold through `orchestrator_api/consolidation.py:185`; `--dry-run` needs no change. `Path.unlink` of the Mission's own two status files in the target checkout, committed through the existing door, is the mechanism the orchestrator approved. **STOP conditions, verbatim: a fold that needs a new destructive git operation, or an edit outside owned files / in a do-not-touch path → stop and report to the orchestrator.** Anything beyond the approved unlink of those two files (a `git rm`, `git reset`, `git checkout --`, `git clean`, `git add -u` or `-A`, a ref deletion, `rmtree`, or unlinking any other path) is such an operation. `tests/architectural/test_destructive_op_routing.py` is a do-not-touch gate file: run it, never edit it; if it objects to the unlink, stop and report.

### Subtask T012 – `_is_bookkeeping` nested-alias leg: only if `--strategy merge` proves it

- **Purpose**: Under squash with the fold the leg is unnecessary (measured: real door, real `done`, fold, no `_is_bookkeeping` change: PASS). Under `--strategy merge` the per-commit axis (`_commit_is_content`, `:1137`) flagged THREE commits in the probe: the seed commit, the fold commit, and `chore(spec-kitty): status transition WP01` (the real `done` event written to the composed directory). The leg exists only for that.
- **Steps**:
  1. After T014, add a `--strategy merge` variant of the reproduction to the integration file: same real-door helper, same fixture data, same end-state assertions. Run it.
  2. **If it is already green without the leg: do NOT edit `reconciliation.py` at all.** Commit the variant as a guard, say so in the hand-back, and skip steps 3 to 6. A zero diff in `reconciliation.py` is the preferred outcome.
  3. If it is red, commit it red and record the flagged commits and paths. Then write unit tests in `tests/consolidation/test_reconciliation.py`, calling `_is_bookkeeping(path, mission_slug, planning_prefix)` directly with `mission_slug = "<slug>"` and the nested prefix a bare-slug coordination claim really has (measured: `.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>`). Call `<slug>-<mid8>` the alias. Positive: `kitty-specs/<alias>/status.events.jsonl` and `kitty-specs/<alias>/status.json`. Negative controls, each must stay content:
     - `kitty-specs/<alias>/spec.md`
     - `kitty-specs/<alias>/src/x.py`
     - `kitty-specs/<alias>/sub/status.json` (four segments)
     - `kitty-specs/<other>-<mid8>/status.json`
     - `kitty-specs/<slug>-<different mid8>/status.json`
     - `x/kitty-specs/<alias>/status.json` (not root-anchored)
     - with a ROOT-form prefix (`kitty-specs/<alias>`), the new leg is not applied and every verdict is byte-identical to the base.
     Unchanged: every existing primary-name case.
  4. Append ONE leg to the body, immediately before the final `return` (`:1243`); the existing legs stay byte-identical and in order. `alias` = the last segment of `planning_prefix`; the leg applies only when the prefix is NESTED (`<something>/kitty-specs/<alias>`, non-empty `<something>`) and `alias != mission_slug`; it returns True only for a root-anchored path of exactly three segments, `kitty-specs/<alias>/<file>`, whose `kind_for_mission_file(path, mission_slug=alias)` is `MissionArtifactKind.STATUS_STATE`.
  5. Imports are function-local, inside the body. Run `tests/architectural/test_merge_reconciliation_class_guard.py`; if a function-local import does not pass it, STOP and report.
  6. Nothing else in the file changes: not the signature, not the call sites (`:1163`, `:1651`, `:1876`), not `_commit_is_content`, not `_planning_prefix` (`:2055`). Extend the docstring with the leg's rule.
- **STOP conditions**: if the narrow leg does not make the merge-strategy variant pass (for example the third commit touches a path the leg does not cover), or if it can only pass by changing `_planning_prefix` or any other part of `reconciliation.py`, STOP and report with the flagged commit and path list. Do not widen the leg.
- **Files**: `tests/integration/test_merge_lane_planning_data_loss.py` (the variant); only if red: `src/specify_cli/consolidation/reconciliation.py` (one leg in `_is_bookkeeping`, at most one adjacent private helper), `tests/consolidation/test_reconciliation.py`.
- **Parallel?**: No; after T014.
- **Notes**: Known and NOT to be changed here: `_planning_prefix` returns a `.worktrees/...-coord/kitty-specs/<slug>-<mid8>` path that no commit can contain, so the existing prefix leg (`:1239`) is dead under coordination topology (see the comment at `:1227-1236`). Fixing it would exempt the whole composed subtree and touches more than `_is_bookkeeping`. List it as a follow-up.

### Subtask T015 – `phase_bookkeeping.py:567`: convert only with a red proof

- **Purpose**: FR-003's rule that a consumer is converted only when a test proves it.
- **Steps**:
  1. After T012 to T014, run the reproduction and its merge-strategy variant. If both are green with `:567` untouched, try to construct a failing case for the post-merge invariant: a bare-slug run in which a composed-directory status file is modified or untracked in the primary checkout at that point. If you cannot make a test red, leave `:567` unchanged and say so in the hand-back; the orchestrator lists it in the follow-up issue.
  2. If a test is red, convert the predicate to pass the resolved names. `is_toolchain_generated_churn` lives in `coordination/coherence.py:278`, owned by WP02 (already in your base). A one-line pass-through parameter there is an out-of-map edit: allowed, with a one-line rationale in the hand-back.
  3. Either way, add the mutation note to the test's docstring: which single consumer, when reverted, turns it red.
- **Files**: `src/specify_cli/consolidation/phase_bookkeeping.py` (only with proof).
- **Parallel?**: No.

### Subtask T016 – The reproduction becomes a fixed-bug regression test

- **Purpose**: FR-018.
- **Steps**:
  1. Rewrite the docstring of `test_bare_slug_coord_mission_consolidates_onto_a_protected_target`: remove "OPEN, red on purpose" and the exit rule; state the contract it pins (exit 0, teardown, one directory, complete event set, clean checkout), that it runs the real bookkeeping door and why (with the door mocked it could pass with two status homes and no `done` event), the layers that were fixed, and the issue number as the origin.
  2. Keep `@pytest.mark.regression`. Do not add `p0_repro`.
  3. Confirm the sibling `test_explicit_delete_override_still_reachable` (`:1623`) and the rest of the file are green and unedited.
  4. Revert each consumer alone in a scratch state and confirm a test goes red. Record the consumer-to-test table in the hand-back with these rows, naming the test node id for each:
     - partition classifier (WP02) → the reproduction;
     - teardown identity (WP01) → its own test and the reproduction;
     - fold → the reproduction (squash);
     - `_is_bookkeeping` leg → the merge-strategy variant only (omit the row if `reconciliation.py` was not edited);
     - `phase_bookkeeping.py:567`, only if converted.
     Do not commit the reverts.
- **Files**: `tests/integration/test_merge_lane_planning_data_loss.py`.
- **Parallel?**: No.

### Subtask T017 – Gates, lint and hand-back

- **Purpose**: Close with evidence.
- **Steps**:
  1. Run every command in the Test Strategy section.
  2. `git diff <base> -- src/specify_cli/consolidation/reconciliation.py` must be empty, or show changes only inside `_is_bookkeeping` (and one adjacent helper, if extracted). Paste the hunk headers into the hand-back.
  3. Hand-back: commits, counts, the consumer-to-test table, the four hypothesis checks of T014 step 6, the T012 outcome (leg added, or zero diff), the T013 outcome, the `--resume` result or residual, tracer notes.
  4. List these follow-ups in the hand-back; do not fix them: (a) the shared helper `_real_merge_external_mocks` mocks in-repository product code (the `done` record, the bookkeeping door, the porcelain invariant) and carries a vacuous patch (`post_merge.stale_assertions.run_check`, 0 calls); (b) `test_malformed_retention_value_is_treated_as_retaining` is green only through that mock (unmocked: `DESTINATION_REF_NOT_FOUND`), and at least 9 tests in `tests/consolidation/test_merge_divergent_end_to_end.py` depend on it; (c) the dead `planning_prefix` leg under coordination topology (`reconciliation.py:1239`, `:2055`).
- **Files**: none.
- **Parallel?**: No.

## Test Strategy

### Validation commands

Run from the root of your lane worktree. Use the repository root checkout's environment, never a bare `uv run` (it re-syncs the environment) and never the globally installed `spec-kitty` binary for product behaviour (it is a different build).

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python
export PYTHONPATH=$(pwd)/src

# behavioural tests (named files only)
$PY -m pytest \
  tests/integration/test_merge_lane_planning_data_loss.py \
  tests/consolidation/test_reconciliation.py \
  tests/consolidation/test_bookkeeping_projection_seam.py \
  tests/consolidation/test_bare_slug_alias_consumers.py \
  tests/consolidation/test_issue_2709_projection_union.py \
  tests/consolidation/test_coord_teardown_order_3926.py \
  tests/consolidation/test_coordination_flatten_on_branch_delete.py \
  tests/coordination/test_projection_teardown.py \
  tests/coordination/test_commit_router.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_merge_reconciliation_class_guard.py \
  tests/architectural/test_status_events_writes_gate.py \
  tests/architectural/test_write_surface_placement_guard.py \
  tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_coord_read_residuals_closeout.py \
  tests/architectural/test_mission_runtime_surface.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_git_path_listing_owner.py \
  tests/architectural/test_guard_capability_call_sites.py \
  tests/architectural/test_merge_pipeline_ratchets.py \
  tests/consolidation/test_single_rollback_authority.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/run_state.py src/specify_cli/consolidation/executor.py src/specify_cli/consolidation/phase_bookkeeping.py src/specify_cli/consolidation/bookkeeping_projection.py tests/consolidation/test_reconciliation.py tests/consolidation/test_bookkeeping_projection_seam.py tests/consolidation/test_bare_slug_alias_consumers.py tests/integration/test_merge_lane_planning_data_loss.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/run_state.py src/specify_cli/consolidation/executor.py src/specify_cli/consolidation/phase_bookkeeping.py src/specify_cli/consolidation/bookkeeping_projection.py tests/consolidation/test_reconciliation.py tests/consolidation/test_bookkeeping_projection_seam.py tests/consolidation/test_bare_slug_alias_consumers.py tests/integration/test_merge_lane_planning_data_loss.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/run_state.py src/specify_cli/consolidation/executor.py src/specify_cli/consolidation/phase_bookkeeping.py src/specify_cli/consolidation/bookkeeping_projection.py
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

`tests/integration/test_merge_lane_planning_data_loss.py` is a 1,982-line file with real git repositories; run it with `-n 4 --dist loadfile` and, for the reproduction alone, `-n0` with the node id from `quickstart.md`.

### Non-vacuity controls (as test cases)

- FR-004: if the leg is added, the seven negative controls of T012 step 3 against `_is_bookkeeping`, on the same inputs as the positive pair.
- FR-004, fold level: a non-status file under the composed name is neither removed nor exempted; the gate FAILS and rolls back.
- FR-001: the `--strategy merge` variant (red without the leg in the probe; if it is green without it on your tree, no leg is added).
- Event preservation: the assert fires and nothing is deleted when the composed log holds an event the union lacks.
- FR-004, gate level (required, unconditional, whether or not the leg is added): a new gate-level test in `tests/consolidation/test_reconciliation.py` in which the target carries status files under a directory name that belongs to a different Mission; the reconciliation gate FAILS on that content (User Story 1, scenario 4). It uses a bare-slug claim whose `planning_prefix` ends in the composed name.
- FR-019 and FR-003: the reproduction with the real bookkeeping door asserts the directory listing on the target ref, the event set including `done`, and a clean root checkout. A test that only checks exit code 0, or one that mocks the bookkeeping door, is not sufficient.
- FR-005: the canonical sibling is byte-identical before and after (same directory listing, same event count).
- FR-003: the consumer-to-test table of T016 step 4.

## Definition of Done

- The reproduction runs on `_real_bookkeeping_commit_external_mocks` with no inline durability patches, its fixture data unchanged, its assertions strengthened (one directory, event set with `done`, no composed directory, teardown, clean checkout), its `regression` marker kept and its docstring rewritten. It was committed red and is green.
- The `--strategy merge` variant is green.
- `reconciliation.py` has a zero diff, or changed only inside `_is_bookkeeping`: one appended leg (plus at most one adjacent private helper), function-local import, existing legs byte-identical, signature and call sites untouched, with the variant recorded red before it.
- `_real_merge_external_mocks` and the other tests using it are untouched; the three follow-ups are listed in the hand-back.
- The fold removes only the composed directory's two status files, in the existing bookkeeping commit, after the event-preservation assert; no new git argv; no edit to `lanes/consolidation.py`, `phase_advance.py`, `rollback.py`; `run_state.py` and `executor.py` unedited unless a red proof is named.
- The four hypotheses of T014 step 6 are checked and reported.
- Every converted consumer has a test that goes red when that consumer alone is reverted; unconverted candidates are named in the hand-back.
- No new destructive git operation; no do-not-touch edit; any out-of-map edit has a rationale.
- All Test Strategy commands pass with counts recorded.
- Subtasks T011 to T017 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **Adjacency to #5668.** Any change outside the `_is_bookkeeping` body creates a rebase conflict with a running mission. Keep the hunk minimal and report its headers.
- **Exempting too much.** The primary leg exempts a subtree; copying it for the alias would exempt planning artifacts and source under the composed name. The alias leg checks the record kind.
- **Other tests share the over-mocked helper.** Making `_real_merge_external_mocks` real breaks `test_malformed_retention_value_is_treated_as_retaining` and at least 9 tests in `tests/consolidation/test_merge_divergent_end_to_end.py`. Do not edit the shared helper; switch only the reproduction.
- **The leg added without need.** Zero diff in `reconciliation.py` is preferred; the merge-strategy variant decides.
- **The fold needs more than the approved unlink.** That is a STOP, not a judgement call.
- **Events lost in the fold.** The preservation assert runs before the unlink and fails closed.
- **Other coordination-kind files under the composed name.** Not in the fixture; if one exists in practice, STOP and report rather than widening the deletion.
- **`safe_commit` and a missing path.** The comment at `phase_bookkeeping.py:622-624` says the door hard-fails on a missing path; the design probe saw a tracked-but-missing file committed as a deletion. Confirm on your tree before relying on it.
- **A hand-built `_MergeRunState` in other tests.** New fields are defaulted.
- **Rollback interplay.** A gate REFUSE or FAIL restores through `rollback_to_snapshot`; the fold must not leave state that the rollback cannot restore. Run `tests/consolidation/test_single_rollback_authority.py`.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **Fixture re-key.** The reproduction's fixture data (slug, branch, meta edits, protected target) must be unchanged.
- **Reverting to the mocked helper, weakening an end-state assertion, or asserting a line count instead of the event set.** The reproduction must use `_real_bookkeeping_commit_external_mocks`, carry no inline durability patch, and assert the event set by id and the `done` transition.
- **An edit to the shared helper `_real_merge_external_mocks` or to another test using it.**
- **A leg added although the merge-strategy variant was green without it, or added without the variant recorded red first.** Check the commit order; revert the leg locally and run the variant.
- **The fold widened.** It may unlink exactly the two status files of the composed directory. Any glob, directory removal or third file is a defect.
- **No preservation assert, or an assert after the unlink.** Read the order in `_phase_commit_and_assert`; run the test where the composed log holds an extra event.
- **A second commit for the deletion.** The deletion must be in the existing bookkeeping commit; `git log --stat` on the test repository shows one.
- **A leg wider than specified.** The new leg must require a nested prefix, `alias != mission_slug`, a root-anchored three-segment path and `STATUS_STATE`. Run the seven negative controls.
- **Edits to `run_state.py` / `executor.py` without a named red proof.**
- **Whole-directory exemption.** `_is_bookkeeping` returning True for `kitty-specs/<slug>-<mid8>/spec.md` or `/src/x.py`. Run the negative controls and read the body.
- **Prefix-matched alias.** Any `startswith`/`endswith`/regex on the slug in the new code. The alias name comes from `planning_prefix`'s final segment under `kitty-specs`, or from the resolved set.
- **Signature or call-site change in `reconciliation.py`.** Check hunk headers.
- **Exit-code-only proof.** The end-state assertions must read the target ref.
- **Unconverted or over-converted consumer.** Ask for the consumer-to-test table (partition and teardown and fold against the reproduction; the leg against the merge-strategy variant only) and re-run at least two reverts yourself, including the fold.
- **The composed directory hidden rather than folded.** The event log on the target must be the union, with the exact count; a fold that drops the composed directory's events passes a listing check and fails the count.
- **A new destructive call.** Grep the diff for `git rm`, `reset`, `clean`, `checkout --`, `update-ref -d`, `branch -D`, `git add -u`, `git add -A`, `unlink`, `rmtree`. Exactly one `unlink` site is expected: the approved fold.
- **A top-level import added to `reconciliation.py`.** The hunk headers must all sit inside `_is_bookkeeping` (or its adjacent helper); imports are function-local.
- **The foreign-directory gate test missing or built on a canonical claim.** It must exist and use a bare-slug claim.

Confirm red then green from the commit sequence, the trailer on every commit, and no AI or model identifier.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Append the new entry at the END of this section; never prepend or insert in the middle.
2. Use the format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>`.
3. The timestamp is the current UTC time (`date -u "+%Y-%m-%dT%H:%M:%SZ"`), never a future one.

The acceptance system reads the LAST entry as the current state, so order matters.

**Initial entry**:

- 2026-10-05T04:58:23Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done` to record a finished subtask.
