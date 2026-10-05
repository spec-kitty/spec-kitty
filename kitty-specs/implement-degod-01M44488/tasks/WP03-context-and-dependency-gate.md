---
work_package_id: WP03
title: Context and dependency gate into their seams
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-006
- FR-012
- NFR-002
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 1 - Seam extraction
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/specify_cli/core/test_claim_preconditions.py
- tests/specify_cli/workspace/test_context_implement_reads.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/workspace/context.py
- src/specify_cli/core/dependency_graph.py
- tests/specify_cli/core/test_claim_preconditions.py
- tests/specify_cli/workspace/test_context_implement_reads.py
- tests/specify_cli/core/test_dependency_graph_canceled.py
- tests/specify_cli/acceptance/test_trio_read_seam_migration.py
- tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/cli/commands/test_resolve_lanes_dir.py
- tests/agent/test_implement_command.py
- tests/cli/commands/test_implement_base_flag.py
- tests/cli/test_implement_bulk_edit_planning.py
- tests/integration/test_status_emit_on_alloc_failure.py
- tests/specify_cli/cli/commands/test_implement_vcs_lock_claim.py
- tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py
- tests/specify_cli/lanes/test_lane_base_honoring.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_trio_seam_only.py
- tests/specify_cli/test_meta_fail_closed_full_census_contract.py
- tests/coordination/test_commit_router_layering.py
- tests/architectural/test_layer_rules.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Context and dependency gate into their seams

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

- **FR-006.** Move the context reads that implement owns today into
  `src/specify_cli/workspace/context.py`:
  - `find_wp_file` (implement.py ~L243);
  - `_resolve_lanes_dir` (~L377), which becomes the public `resolve_lane_state_dir`. The name must
    be distinct: `lanes.persistence.resolve_lanes_dir(feature_dir)` already exists with different
    semantics, and `workspace/context.py` already imports it locally (~L1198). Note the twin in the
    docstring;
  - `resolve_feature_target_branch` (~L279), which becomes `resolve_mission_target_branch`. The
    terminology canon forbids a new `feature` name; keep the old name nowhere.
- **FR-003.** Move the claim-precondition decision from `_ensure_wp_claim_preconditions` (~L1503)
  into `src/specify_cli/core/dependency_graph.py` as a pure
  `ensure_wp_claim_preconditions(wp_id, declared_deps, work_packages)`.
  - It takes the reduced snapshot's `work_packages` mapping.
  - It raises exactly today's `WorkPackageStartRejected` / `ValueError` with today's texts.
  - The event read and reduce (`read_events` + `reduce`) stay in the implement caller.
- Seam unit tests exercise both seams without the CLI and without patching implement (SC-005, for
  the context and dependency-gate phases).
- The characterization suite stays green **unedited** (the dispatch map may change).

## Context & Constraints

- Contract: `kitty-specs/implement-degod-01M44488/contracts/seam-decisions.md` (sections
  `core/dependency_graph.py`, `workspace/context.py`).
- `core/dependency_graph.py` already imports the `specify_cli.status` facade at module scope (~L15–18).
  `tests/architectural/test_cold_import_status_boundary.py` requires `task_utils.support` and
  `core.owned_mission` not to load status/workspace on cold import. Verify that your import changes
  keep it green.
- `tests/architectural/test_owned_checkout_single_authority.py` pins `resolve_workspace_for_wp` in
  `workspace/context.py`. Adding functions there is fine.
- **Lane-map derivation (pin, do not dedupe).** Today the lane map is
  `{wp: state.get("lane", Lane.GENESIS)}`. `status/dependency_verdict.wp_lanes_from_snapshot` uses
  `str(state.get("lane") or GENESIS.value)`. Keep implement's form byte-for-byte, and add a unit test
  pinning the present-but-falsy case.
- `workspace/context.py` already has a private `_find_wp_file(tasks_dir, wp_id)` (~L597) with
  different arguments. Keep both and name the relationship in the docstring; deduplicating them is
  out of scope.
- `find_wp_file` is in `implement.__all__` and has a `category_b_grandfathered_legacy` row in
  `tests/architectural/dead_symbol_allowlist.yaml` (~L652–657). Re-key that row to the new module,
  or delete it if the moved symbol now has a src caller. Then run `test_no_dead_symbols.py`.
- **Production importers.** Find every production caller of the moved names
  (`grep -rn "find_wp_file\|resolve_feature_target_branch\|_resolve_lanes_dir" src`) and re-point
  each one. Production importers of `implement.find_wp_file`, if any, switch to the new home.

## Subtasks & Detailed Guidance

### Subtask T010 – Move the context reads (verbatim move commit)

- Cut `find_wp_file`, `_resolve_lanes_dir` and `resolve_feature_target_branch` (with their
  docstrings and `_WP_ID_RE`) out of `implement.py` and paste them into `workspace/context.py`
  **unchanged, names included**. The renames to `resolve_lane_state_dir` and
  `resolve_mission_target_branch` happen in the T012 adjust commit (change-function-declaration).
- Add the minimal imports.
- `implement.py` imports them from the new home in the same commit, so the tree imports cleanly;
  the commit is allowed to be transiently test-red only on patch targets.
- `git diff --color-moved=zebra HEAD~1` must show moved blocks plus import lines only.

### Subtask T011 – Move the claim-precondition decision (verbatim, then reshape)

- **Move commit**: move `_ensure_wp_claim_preconditions` into `dependency_graph.py` unchanged.
- **Adjust commit**:
  - Split the event I/O out: the implement caller keeps
    `snapshot = reduce(read_events(status_feature_dir))` and passes `snapshot.work_packages`.
  - The seam function `ensure_wp_claim_preconditions(wp_id, declared_deps, work_packages)` keeps the
    genesis check, the lane map, `dependency_readiness_for_wp(..., provenance=work_packages)` and
    the `ValueError` text byte-identical.
  - Keep `WorkPackageStartRejected` from the status facade.
- Fix the two pre-existing `mypy --strict` errors in `dependency_graph.py` (~L90, ~L123, both
  `no-any-return`) with typing-only changes (boy-scout rule, NFR-002).

### Subtask T012 – Adjust commit: callers, re-exports, `__all__`, allow-list, typing

- Delete the moved names from `implement.py`, including their re-exports (research R-3). Keep a
  re-export only if **production** code imports the name from `implement`.
- `implement.__all__` drops `find_wp_file`. Add `find_wp_file` (and the other new public names) to
  `workspace/context.py`'s `__all__` if that module declares one.
- Update the dispatch map (`tests/specify_cli/cli/commands/_implement_dispatch.py`) if any entry
  pointed at a moved name.
- Apply the renames (`_resolve_lanes_dir` → `resolve_lane_state_dir`, `resolve_feature_target_branch` →
  `resolve_mission_target_branch`) and update every caller.
- Fix strict typing on the moved functions (for example `resolve_feature_target_branch`'s
  no-any-return, implement.py ~L288).

### Subtask T013 – Seam unit tests

- `tests/specify_cli/core/test_claim_preconditions.py` (fast, unit, no git). Cases:
  - genesis WP raises `WorkPackageStartRejected` with the exact text;
  - an unmet dependency raises `ValueError` with the exact `dependencies_not_satisfied:` text;
  - all dependencies approved or done passes;
  - an operator-canceled dependency counts as satisfied, while a synthetic-canceled one blocks
    (move these from `test_dependency_graph_canceled.py::TestImplementClaimGateThreadsProvenance`
    if they test the same decision);
  - the present-but-falsy lane pin.
- `tests/specify_cli/workspace/test_context_implement_reads.py`:
  - `find_wp_file` (valid, invalid id, missing dir, multiple matches → first sorted);
  - `resolve_lane_state_dir` returns the PRIMARY dir on a coord fixture (absorb
    `tests/cli/commands/test_resolve_lanes_dir.py` cases if they test the same thing);
  - `resolve_mission_target_branch` on a meta fixture.

### Subtask T014 – Re-point tests and gates, prove the scans

- `test_dependency_graph_canceled.py` imports `_ensure_wp_claim_preconditions` from implement:
  re-point it to the seam.
- `test_trio_read_seam_migration.py`'s `find_wp_file` case: re-point it.
- `test_issue_1615…` (fixed in WP01): make sure it still holds.
- The tests that patch `implement.resolve_feature_target_branch` (14 sites), `implement.find_wp_file`
  and `implement._resolve_lanes_dir` re-point to the owner module (common call-style rule).
  `implement.py` calls `workspace_context.<fn>(...)` through a module alias. The list is in
  `count_patch_sites.py --json` `string_by_file`.
- `_WRITE_DIR_CONSUMER_MODULES` (`test_no_write_side_rederivation.py`): add `workspace/context.py`
  and `core/dependency_graph.py` **if** the moved code matches its grammars. The moved
  target-branch read is a meta read, so check `test_meta_fail_closed_full_census_contract.py`'s file
  list too, and add the module or record why it is out of scope.
- **No-CLI import guard** (common rule): cover `workspace/context.py` and `core/dependency_graph.py`,
  and prove it with a plant.
- Run the gate files: `test_cold_import_status_boundary`, `test_status_module_boundary`,
  `test_owned_checkout_single_authority`, `test_trio_seam_only`, `test_no_write_side_rederivation`,
  `test_no_dead_symbols`, `test_layer_rules`, and the liveness gate.
  - If a gate scans a fixed file list that included `implement.py` and the moved code is in scope
    for it (for example `_TRIO_FILES` for the read-seam `placement_seam(...).read_dir(...)` calls),
    add `workspace/context.py`.
  - If it is already covered by another rule, record why no widening is needed.
- Run the planted-violation proofs.

## Definition of Done

- [ ] The two move commits are pure moves; the adjust commit is separate.
- [ ] Seam tests green; the characterization suite unedited and green.
- [ ] `mypy --strict` clean on `workspace/context.py` and `core/dependency_graph.py` (the 2 pre-existing errors fixed).
- [ ] Gates green; widened scans proven by planted violations.
- [ ] Counter before and after recorded.

## Risks & Mitigations

- **Import cycle**: `mission_runtime` imports `workspace.context` lazily (resolution.py ~L3096).
  Keep `placement_seam` usage in `workspace/context.py` cycle-free, and verify by importing the
  module cold.

## Review Guidance

- `git diff --color-moved=zebra` on the move commits.
- Exact-text equality of both precondition errors.
- No new status import that breaks the cold-import gate.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP03 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP03 --mission implement-degod-01M44488`), and work in the path it prints.

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
