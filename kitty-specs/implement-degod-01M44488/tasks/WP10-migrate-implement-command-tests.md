---
work_package_id: WP10
title: Migrate test_implement_command.py onto seams and phases
dependencies:
- WP09
requirement_refs:
- FR-011
- SC-002
- SC-005
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T045
- T046
- T047
phase: Phase 4 - Test migration
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/agent/
create_intent:
- tests/specify_cli/cli/commands/test_implement_phases.py
- tests/specify_cli/workspace/test_context_implement_reads.py
- tests/specify_cli/core/test_claim_preconditions.py
execution_mode: code_change
model: ''
owned_files:
- tests/agent/test_implement_command.py
- tests/specify_cli/cli/commands/test_implement_phases.py
- tests/specify_cli/workspace/test_context_implement_reads.py
- tests/specify_cli/core/test_claim_preconditions.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Migrate test_implement_command.py onto seams and phases

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

`tests/agent/test_implement_command.py` holds the largest share of the SC-002 coupling (54 string
targets at baseline; re-measure with `count_patch_sites.py --json` `string_by_file`). Migrate it so
its family patch sites drop to **≤ 5**, with every behaviour it owns still proven.
- `TestDetectFeatureContext` / `TestFindWpFile`: if WP03/WP09 have not already absorbed them, move
  them into the seam or phase tests (`test_context_implement_reads.py`, `test_implement_phases.py`).
- `TestImplementCommand` (7 tests stubbing 5–9 collaborators):
  1. For each test, write down the behaviour it owns in the activity log. The candidates are:
     - the JSON payload shape;
     - the dependency gate runs before allocation;
     - a protected-target coord commit is allowed;
     - execution_mode threading;
     - the planning-lane allowance;
     - the `_resolve_placement_ref` → unresolved path (re-pointed in WP06).
  2. Prove that behaviour with a phase-function test that passes real values and patches nothing in
     the family, or with a real-git fixture.
  3. Delete the MagicMock-graph version **only after** its replacement is green, and name the
     replacement in the log.
- Keep `test_implement_json_error_output_is_clean` (the lanes.json guard) and one CLI smoke per
  behaviour family this file owned.
- **Per-target reduction plan** (log it before starting): for each string target in the file
  (`find_repo_root`, `detect_feature_context`, `resolve_feature_target_branch` → its owner,
  `create_lane_workspace`, the planning-commit adapter, `_ensure_vcs_in_meta` → its owner,
  `start_implementation_status`), say which lever removes it. The levers are: phase parameters
  (WP09), a real fixture, a direct seam call, or keeping it, with the reason.

## Rules

- **Never edit an assertion to make a migration pass.** If a behaviour cannot be proven through the
  seams or phases, stop and report; the seam may be wrong.
- No dispatch-map use in this file (common rule: the map is limited to characterization and F-50).
- Re-measure the counter after each test class and log it.

## Subtasks & Detailed Guidance

### Subtask T045 – Reduction plan and detect/find classes
Log the per-target plan, then move or confirm the context classes.

### Subtask T046 – TestImplementCommand migration
Migrate one test at a time: write the replacement, run it green, delete the old test, run the file
and the counter.

### Subtask T047 – Evidence
Record the file's family patch count before and after, the replacement map, the regression-subset
timing and the characterization status (unedited and green).

## Definition of Done

- [ ] The file's family patch sites are ≤ 5; every retired test names a green replacement.
- [ ] No assertion edited; characterization unedited and green.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP10 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP10 --mission implement-degod-01M44488`), and work in the path it prints.

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


- 2026-10-05 — WP10 evidence (recorded by the orchestrator from the implementer's report).
  - **Reduction plan:**
    - `find_repo_root` ×8: a real fixture.
    - `detect_feature_context` ×8: phase parameters (`detect_context`).
    - `_ensure_planning_artifacts_committed_git` ×8: a real fixture.
    - `_ensure_vcs_in_meta` ×5: a real fixture.
    - `create_lane_workspace` ×7: a real allocation, with the arguments observed through `sys.setprofile`.
    - `resolve_workspace_for_wp` ×3: a real `select_workspace`.
    - `start_implementation_status` ×2: the persisted claim events.
    - `get_current_branch` and `ProtectionPolicy` ×1 each: a real checkout of a coordination branch.
    - None kept.
  - **Replacement map:** see the WP10 review prompt and commit 915e7eba6. Each retired MagicMock-graph test names its phase-level or characterization replacement. `test_implement_json_error_output_is_clean` and TestNFR003 are kept.
  - **Counter:** this file went from 43 to 0 family sites, and the total from 111 to 68 (string 32, object 19, dispatch 17).
  - **Characterization:** unedited, 44 passed. Eight plants turned all 8 new tests red.
