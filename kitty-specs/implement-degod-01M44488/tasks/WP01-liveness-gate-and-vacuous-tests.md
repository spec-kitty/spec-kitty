---
work_package_id: WP01
title: Patch-liveness gate for the implement family and vacuous-test repair
dependencies: []
requirement_refs:
- FR-010
- FR-013
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-degod-01M44488
base_commit: aee10130a11c19d2f3ed59a481785068181b4e07
created_at: '2026-10-04T20:31:44.096028+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 0 - Safety net
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py
- tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py
- tests/agent/test_implement_command.py
- tests/specify_cli/cli/commands/test_implement.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Patch-liveness gate for the implement family and vacuous-test repair

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

No `src/` file changes in this WP.
- **FR-010.** `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py` also covers
  the **implement family**: every `src/specify_cli/cli/commands/implement*.py` whose stem is
  `implement` or starts with `implement_`, derived by glob, so the siblings later WPs add join
  automatically.
  - A planted dead implement patch turns it red.
  - A planted attribute-style use (`<alias>.<name>` read from another module) makes a patch on the
    owner module **live**.
  - `UNRESOLVABLE_BASELINE` is not raised, no implement allow-list entry is added, and dead
    implement patches found today are fixed.
- **FR-013.** The four vacuous tests named below are repaired or retired, each with its
  planted-break proof.
- The counter baseline is recorded (expected 119 on the base commit).

## Context & Constraints

- Read the gate end to end before changing it. Grounding (`research/code-grounding.md` §1.5) and
  the post-tasks squad found these facts:
  - `_PKG`, `_SRC_DIR`, `_MODULES` and `_MODULE_HINT` are hard-wired to `cli.commands.agent`
    (~L53–71).
  - `_scan_tests` **skips any test file that does not contain the text `"commands.agent"`**
    (~L570). A naive widening would therefore scan zero implement patches and pass without
    checking anything.
  - `_string` resolves constants and simple Name-bound strings. `_bind_assign` (~L378) ignores
    `ast.Dict`, and Subscript targets (`DISPATCH[key]`) are silently skipped.
  - Seam-module rule: a name is live for module M when M reads it as a plain `Name` load outside
    its own def, or when a call-time `from <pkg>.M import name` exists under `src/`.
  - Bridge rule (b) applies today only to `tasks`: a name is live when another module reads
    `<alias>.<name>` with `<alias>` bound to `tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Generalize the gate to per-family configuration

1. Introduce a small family descriptor and parametrize the scan by it. Each family has:
   - its package;
   - its module discovery (glob);
   - its test-file pre-filter hint, so the implement family pre-filters on `"commands.implement"`;
   - its bridge rule.

   The tasks family's behaviour and assertions stay byte-identical.
2. Implement family liveness has two parts:
   - the seam-module rule as today;
   - **plus the attribute rule.** Name `n` is live for family module M when any module under
     `src/` reads `<alias>.<n>`, where `<alias>` is bound to M by `import specify_cli.cli.commands.M as <alias>`,
     `from specify_cli.cli.commands import M [as <alias>]`, or a lazy in-function form of either.
   - This is what makes the mission's mandated call style (`implement_claim.fn(...)` called from
     `implement.py`) count as live.
3. Run the gate. Every implement patch it reports dead today is a real dead patch: re-point the
   test to where the name is looked up, and log each one. If an implement target is unresolvable,
   make it resolvable in the test (for example inline the constant); never raise the baseline.
4. Positive controls, run red and then removed, never committed:
   - a scratch test patching `specify_cli.cli.commands.implement.no_such_name`;
   - a scratch src reference proving the attribute rule (or a unit test of the rule function with
     a synthetic AST, which is better and can be committed).

### Subtask T002 – Dispatch-map liveness hook (ready for WP02)

WP02 will add `tests/specify_cli/cli/commands/_implement_dispatch.py`, a dict of logical
collaborator → dotted target. Add a parametrized gate case now. It imports that module if it
exists, `pytest.skip`s if it does not (WP02 removes the skip by creating it), and asserts that
every value's `(module, name)` is in the family's live set. Unit-test the case logic with a
synthetic map, including a planted dead entry, so it is proven before WP02 relies on it.

### Subtask T003 – Repair the vacuous tests (FR-013)

For each repair: plant a break, run red, revert, and log the plant and the failing test id.
- `tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py::test_resolve_mission_read_path_used_in_implement`
  passes only because of a *comment* (implement.py ~L2066).
  - Replace the oracle with a behavioural one: on a coord-topology fixture where the WP is
    finalized on the coordination status surface, implement's dependency gate does **not** refuse
    with "not finalized".
  - If a fixture is too heavy here, use an AST assertion that `implement`'s module calls
    `resolve_status_surface_with_anchor`, and note that WP09 must re-point it.
  - Planted break: read the primary surface instead → red.
- `tests/agent/test_implement_command.py::test_implement_requires_lanes_json` (~L163) is vacuous: it
  exits on "Could not determine current branch".
  - Retire it. The covering guard is `test_implement_json_error_output_is_clean` (~L246, asserts
    `lanes.json is required`).
  - Planted break: make `require_lanes_json` return silently → the guard goes red.
- `tests/specify_cli/cli/commands/test_implement.py` `assert callable(implement)` (~L375) and
  `hasattr(implement, "safe_commit")` (~L363).
  - Retire both. The covering guard is any test that imports and calls `implement` (for example
    `tests/agent/test_implement_programmatic_call.py`).
  - Planted break: rename `implement` → those tests error at import.

### Subtask T004 – Evidence

Record in the activity log:
- the counter output (expected 119, minus any retired patch sites);
- the gate's family results (tasks unchanged; implement N live, 0 dead after fixes);
- every planted break;
- the run counts of the regression subset.

## Definition of Done

- [ ] Gate covers the implement family by glob, with a per-family pre-filter and the attribute rule. Tasks family unchanged.
- [ ] Dead-patch and attribute-rule positive controls proven; dispatch-map hook unit-tested.
- [ ] Four FR-013 tests repaired or retired with planted-break proofs.
- [ ] No `src/` change; validation recorded.

## Review Guidance

- Re-run the tasks-family gate cases: identical results.
- Plant one dead implement patch yourself.
- Confirm the pre-filter actually selects the implement test files (log the scanned-file count).

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP01 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP01 --mission implement-degod-01M44488`), and work in the path it prints.

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
