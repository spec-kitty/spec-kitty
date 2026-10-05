---
work_package_id: WP05
title: Planning-commit adapter out of the command module
dependencies:
- WP04
requirement_refs:
- FR-004
- FR-012
- NFR-005
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
- T024
phase: Phase 1 - Seam extraction
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/implement_planning_commit.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/implement_planning_commit.py
- src/specify_cli/lanes/implement_support.py
- tests/specify_cli/cli/commands/test_implement_*.py
- tests/specify_cli/cli/commands/test_implement.py
- tests/specify_cli/cli/commands/test_precondition_ref_unification.py
- tests/specify_cli/cli/commands/test_cli_git_paths.py
- tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py
- tests/coordination/test_ledger_topology_less_callers.py
- tests/specify_cli/test_worktrees_index.py
- tests/specify_cli/test_meta_read_permission_denied_regression.py
- tests/lanes/test_issue_2993_lane_planning_ancestry.py
- tests/integration/test_wp_integrity_*.py
- tests/integration/test_issue_3784_coord_tasks_md_primary_bundle_guard.py
- tests/agent/test_implement_command.py
- tests/cli/commands/test_implement_base_flag.py
- tests/cli/test_implement_bulk_edit_planning.py
- tests/integration/test_status_emit_on_alloc_failure.py
- tests/specify_cli/lanes/test_lane_base_honoring.py
- tests/architectural/test_wp_integrity_partition_call_shape.py
- tests/architectural/test_exemption_registry_ratchet.py
- tests/architectural/test_trio_seam_only.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/contract/test_terminology_guards.py
- tests/contract/test_feature_alias_scope.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Planning-commit adapter out of the command module

## ⚡ Do This First: Load Agent Profile

Load the agent profile named in the frontmatter through the canonical path, and work according to
its guidance before you read the rest of this prompt:

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --json
```

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

State, in your first activity-log entry, which directives and tactics of the profile you applied.

---

## ⚠️ IMPORTANT: Review Feedback

Before you start, read the `review_ref` in the event log (`spec-kitty agent tasks status --mission implement-degod-01M44488`)
and the Activity Log below. Treat any review feedback as your TODO list.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Binding rules for this mission (read once, apply throughout)

- **Behaviour preserved (C-001).** Refusal texts, error codes, exit codes, console and `--json`
  output (including print order), commits and state files stay byte-identical.
- **Move, then adjust (C-002 / NFR-005).**
  - Commit 1 of each extraction is a verbatim move: `git diff --color-moved=zebra` must show only
    moved blocks plus the minimal import lines.
  - Commit 2 adjusts callers and imports, deletes the moved names' re-exports from `implement.py`
    (research R-3: keep a re-export only where *production* imports it from there), and applies
    typing-only fixes.
  - Never edit logic inside the move commit.
- **Existing packages only (C-004).** Lower packages (`lanes`, `workspace`, `coordination`,
  `status`, `core`) never import `specify_cli.cli`, `typer` or the console. They return typed
  results or raise typed errors; only the command package prints.
- **Gates follow the code (FR-012).**
  - Every census or scan list that names `implement.py` gains the module the code moved to; pins
    are re-pointed and never loosened.
  - Prove each widened scan by planting a violation in the new module, running the gate red, then
    removing the plant (never committed).
  - Record the commands and the red output in your activity log.
  - Record every local out-of-matrix test run (NFR-006) with its command and counts.
  - Checklist: research/code-grounding.md §1.5 and research/test-remediation.md §5 ("Gate/census edits").
- **Tests (charter SO 4, brief).**
  - Never edit an assertion to make a move pass.
  - Re-point imports and patches to the module that now *looks the name up*.
  - Add seam unit tests before trimming any end-to-end test, and keep at least one smoke test per
    behaviour family.
  - The characterization suite (`test_implement_characterization.py`) must stay green **unedited**.
    Only its dispatch-map fixture may change, when a collaborator's dispatch site moves.
- **Call style for moved collaborators (one rule, every WP).** Code in the command package calls a
  moved collaborator as an attribute of its owner module (`implement_claim.commit_wp_claim_status(...)`,
  `implement_support.resolve_base_ref(...)`), not through a `from … import name` binding.
  - One patch on the owner module then intercepts.
  - The widened liveness gate (WP01) treats `<alias-of-M>.<name>` reads as live.
  - Tests patch the owner module.
- **Ownership leeway for mechanical re-points.** A moving WP may edit any test or gate file only to
  re-point an import path, a patch target, a dispatch-map entry or a gate scan list for the names
  it moves (charter: ownership-map leeway; the no-overlap rule is the real guard, and this chain is
  sequential).
  - List every such out-of-map file in the activity log.
  - Assertion changes are never "mechanical".
- **Dispatch map scope.** `tests/specify_cli/cli/commands/_implement_dispatch.py` may only be used by
  the characterization suite and the F-50 alloc-failure test. Every `patch_collaborator(...)` call
  counts as a patch site in the SC-002 counter.
  - Never build an implement-family patch target dynamically (f-strings, concatenation) to evade
    the counter or the liveness gate.
- **Characterization suite immutability (SC-003).** At every review,
  `git diff <WP02 tip>..HEAD -- tests/specify_cli/cli/commands/test_implement_characterization.py`
  must be empty. Only `_implement_dispatch.py` may change.
- **Known red #5699.** Run `tests/specify_cli/cli/commands/test_commit_recipes.py` in every WP and
  compare its failing set with the base commit. It must be exactly
  `test_no_unallowed_git_commit_recipe_strings_in_src`, failing only on `_commit_message.py`.
  Any new entry is yours (for example the `silently demotes` allow-list row when that message moves).
- **No-CLI import guard for seams (C-004).** Every lower-package module that receives moved code
  (`coordination/planning_commit.py`, `lanes/implement_support.py`, `workspace/context.py`,
  `core/dependency_graph.py`) must be covered by an import gate forbidding `specify_cli.cli` /
  `typer` imports.
  - Extend `tests/coordination/test_commit_router_layering.py`, or the `test_layer_rules.py` rule,
    in the WP that first moves code into that module.
  - Prove it with a plant.
  - `lanes/implement_support.py`'s pre-existing lazy `cli.console` import (~L400) is the one
    recorded exception. Name it in the gate with the same carve-out `test_layer_rules.py` already
    grants consolidation for `cli.console`, plus a pointer to the follow-up issue the orchestrator
    files to drain it (charter SO 5).
- **NFR-003 per WP.** Time the regression subset (quickstart.md §2 plus the seam and phase unit
  tests) in every WP; the budget is ≤ 30 s. The characterization and reachability suites are timed
  separately (≤ 60 s each).
- **Quality (NFR-001/002/004).**
  - Complexity ≤ 15.
  - `mypy --strict` clean on new and receiving modules; nothing added to the mypy quarantine.
  - `ruff check` + `ruff format --check --force-exclude` clean on changed files.
  - No new `noqa` or `type: ignore` without an inline rationale.
- **Commits.** Every commit message ends with
  `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier anywhere
  (C-008).
- **Tracer files.** Append dated 1–3 sentence entries for friction, approach changes or design
  decisions to `kitty-specs/implement-degod-01M44488/traces/` (via the orchestrator, if your
  worktree cannot write the mission dir).
- **No heavy suites.** Never run `make test-full` or a whole `tests/architectural/` sweep. Run the
  targeted files and the specific gate files (quickstart.md §2–§3).


## Objectives & Success Criteria

Move the planning-commit **adapter** verbatim out of `implement.py` into
`src/specify_cli/cli/commands/implement_planning_commit.py`. The adapter is the code that prints,
exits, or runs `BookkeepingTransaction`:
- `_ensure_planning_artifacts_committed_git`, `_commit_planning_artifacts_transaction`,
  `_run_planning_artifact_commit`;
- `_print_uncommitted_planning_artifacts`, `_print_planning_artifact_commit_instructions`,
  `_print_structural_planning_refusal`;
- `_refuse_if_meta_json_demotion`, `_refuse_on_unreadable_planning_status`;
- `_planning_commit_branch` (~L1906), `_RED_ERROR_PREFIX`.

**`_git_stdout` (~L362) moves in this WP**, because the adapter needs it at ~L817. Without the move,
the adapter would have to import it back from `implement.py`, which is a circular import.
- Move it to `src/specify_cli/lanes/implement_support.py` as a public `git_stdout(repo_root, args)`.
  It is the leaf both the adapter and WP07's base-ref code can import.
- First check `lanes/lifecycle_sync.py:~55` `_git_stdout`. It has a different signature and
  returns `None` on failure, so it is **not** equivalent. Do not merge the two; name the twin in
  the docstring.
- `lanes/implement_support.py` is now under the no-CLI import guard (common rule); cover it and
  prove it with a plant, naming the pre-existing `cli.console` lazy import as the exception.

The placement / C-004 arms move **unchanged** (WP06 changes them). Done when the characterization
suite (unedited), the coord-partition smokes and `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence`
(#3371 lesson) are green.

## Subtasks & Detailed Guidance

### Subtask T020 – Verbatim move commit

Move the adapter (and `git_stdout`) byte-for-byte. `implement.py` keeps one call path in the
validate block, `implement_planning_commit._ensure_planning_artifacts_committed_git(...)` plus
`implement_planning_commit._planning_commit_branch(...)`, in attribute style. Check
`--color-moved`.

### Subtask T021 – Adjust commit

- Delete the moved names from `implement.py`.
- Delete the now-unused `implement_cores` shim re-exports (~L69–91) whose names `implement.py`
  itself no longer uses. Tests that imported those via `implement` re-point to `implement_cores`.
- Bring both modules to strict typing, ruff, format and C901 clean.

### Subtask T022 – Re-point tests (mechanical)

- `_ensure_planning_artifacts_committed_git` is patched 12× (string) and imported in about 8 files.
  The private helpers are imported in `test_implement.py`, `test_cli_git_paths.py`,
  `test_wp06_sc2_paused_mission_blockers.py`, `tests/coordination/test_ledger_topology_less_callers.py`,
  `test_worktrees_index.py`, `test_meta_read_permission_denied_regression.py`,
  `test_implement_writeside.py`, `test_implement_coord_idempotency.py`,
  `test_precondition_ref_unification.py`, `test_flat_legacy_none_seam_success_arms.py`,
  `test_issue_2993…` and the integration files. Use `grep -rln` per name.
- Re-point every import and patch to `implement_planning_commit`. The string patches in
  `test_implement_command.py`, `test_implement_base_flag.py`, `test_implement_bulk_edit_planning.py`,
  `test_status_emit_on_alloc_failure.py` and `test_lane_base_honoring.py` become
  `…implement_planning_commit._ensure_planning_artifacts_committed_git`. That keeps the family
  count unchanged, which is honest; WP10/WP11 reduce it.
- Update the dispatch map if needed.
- Never edit an assertion.

### Subtask T023 – Gates

- `test_wp_integrity_partition_call_shape.py` `_IMPLEMENT` (~L47) re-points to
  `implement_planning_commit.py`. The floor of at least 3 `_run_planning_artifact_commit` calls
  (~L157) is unchanged; 5 calls are still present. Prove it with a plant that drops calls below 3.
- `CHURN_SURFACE_MODULES`, `_TRIO_FILES` and `_WRITE_DIR_CONSUMER_MODULES`: add
  `implement_planning_commit.py`.
- The terminology and alias scans: add it if it carries user-facing strings (it does).
- Prove each with a plant.

### Subtask T024 – Smokes and evidence

- Run `uv run --frozen pytest -p no:randomly tests/e2e/test_cli_smoke.py::test_full_workflow_sequence`
  and `tests/integration/test_wp_integrity_*.py`.
- Record the counter, the plants and the timing.

## Definition of Done

- [ ] Move pure, adjust separate; no circular import (`python -c "import specify_cli.cli.commands.implement"` cold).
- [ ] Characterization unedited and green; e2e smoke green; gates widened with plants.
- [ ] `lanes/implement_support.py` no-CLI guard in place.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP05 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP05 --mission implement-degod-01M44488`), and work in the path it prints.

## Validation (run and record in the activity log: command + pass/fail counts)

1. `make test-fast`
2. The implement-direct regression subset (quickstart.md §2), plus every new or touched test file.
3. The owning subsystem directories of every source module you touched (CLAUDE.md blast radius),
   targeted files only.
4. The specific gate files you widened or re-pointed (quickstart.md §3).
5. `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`,
   `uv run --frozen mypy --strict <new/receiving src modules>`, and the C901 check.
6. The counter: `uv run --frozen python kitty-specs/implement-degod-01M44488/tools/count_patch_sites.py`
   (before/after numbers in the activity log).
7. Classify every red against the base commit (CLAUDE.md baseline-red gotcha). Charter rule:
   a pre-existing failure other than #5699 must get a GitHub issue. Record the command and the
   failure in the activity log and hand it to the orchestrator, who files it.
   `test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src` is a known
   pre-existing red (#5699); do not chase it.

## Activity Log

- 2026-10-04T20:45:00Z – system – Prompt created via /spec-kitty.tasks.
