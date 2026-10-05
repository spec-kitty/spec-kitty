---
work_package_id: WP04
title: Planning-commit decisions into the coordination seam
dependencies:
- WP03
requirement_refs:
- FR-004
- FR-012
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
phase: Phase 1 - Seam extraction
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- src/specify_cli/coordination/planning_commit.py
- tests/specify_cli/coordination/test_planning_commit.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/coordination/planning_commit.py
- tests/specify_cli/coordination/test_planning_commit.py
- tests/coordination/test_commit_router_layering.py
- tests/specify_cli/cli/commands/test_commit_recipes.py
- tests/specify_cli/cli/commands/test_implement_bookkeeping_identifiers.py
- tests/specify_cli/cli/commands/test_implement_demotion_guard_4979.py
- tests/specify_cli/cli/commands/test_meta_bypass_diagnosability.py
- tests/specify_cli/coordination/test_partition_authority_characterization.py
- tests/architectural/test_exemption_registry_ratchet.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/specify_cli/test_mid8_contract_sensitive_routing.py
- tests/specify_cli/test_meta_fail_closed_full_census_contract.py
- tests/specify_cli/status/test_cutover_byte_stability.py
- tests/contract/test_terminology_guards.py
- tests/contract/test_feature_alias_scope.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Planning-commit decisions into the coordination seam

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

Move the **pure** planning-artifact commit decisions verbatim out of `implement.py` into a new
sibling of the existing `coordination` package, `src/specify_cli/coordination/planning_commit.py`.
It must not import `specify_cli.cli`, `typer` or the console. The adapter, meaning everything that
prints, exits or runs `BookkeepingTransaction`, stays in `implement.py` for now; WP05 moves it.

Move these:
- `_partition_files_for_commit` (~L910);
- `_guard_planning_commit_partition` (~L933), which raises
  `coordination.commit_router.PrimaryKindReachedCoordStagingError` with texts unchanged;
- the demotion verdict: `_read_json_at_ref`, `_meta_json_demotion_refusal`,
  `_meta_json_repo_relative_path`, `_DEMOTION_REFUSAL_MSG`, `_DEMOTION_CORRUPT_MSG` and
  `_META_JSON_FILENAME` (~L659–748). The `str | None` verdict shape is kept;
  `_refuse_if_meta_json_demotion`, which prints and exits, stays with the adapter;
- the identifier cascade (~L435–581): `_load_primary_anchored_mission_meta`,
  `_load_fallback_mission_meta`, `_extract_mission_identifiers_from_meta`,
  `_compute_effective_bookkeeping_ids`, `_BookkeepingTransactionIdentifiers` (C-006 five-tuple:
  arity and order unchanged) and `_resolve_bookkeeping_transaction_identifiers`;
- `_feature_dir_file_paths` and `_planning_artifact_source_dir` (~L584–639).

Public names drop the leading underscore **in the adjust commit** (contracts/seam-decisions.md).

Done when:
- seam unit tests are green;
- the characterization suite is unedited and green;
- `implement.py` calls these through `coordination_planning_commit.<fn>(...)` (common call-style rule);
- every gate widening is proven with a plant.

## Context & Constraints

- **Lazy imports.** The identifier helpers lazily import `core.paths` and `lanes.branch_naming`.
  Keep them lazy (cold-import boundary).
- **Placement code stays put.** The placement and `None` logic (`placement_ref`,
  `_placement_coord_filter`, `_resolve_placement_ref`) and the C-004 arms are **not** touched here.
  WP06 owns them.
- **#5699 trap (HIGH).** `tests/specify_cli/cli/commands/test_commit_recipes.py:~64–73`
  `_ALLOWED_GIT_COMMIT_HITS` keys `("cli/commands/implement.py", "silently demotes")`. Moving
  `_DEMOTION_REFUSAL_MSG` makes that hit unallowed inside a test that is already red for #5699.
  - Re-key the entry to `coordination/planning_commit.py` (a mechanical re-point).
  - Prove that the test's failing set is exactly the #5699 entry, both before and after.
- **The C-004 no-cli guard.** `tests/coordination/test_commit_router_layering.py` covers
  `commit_router.py` only. Extend it, or `test_layer_rules.py`, to cover
  `coordination/planning_commit.py`, and prove it with a plant.

## Subtasks & Detailed Guidance

### Subtask T015 – Verbatim move commit

Move the listed definitions byte-for-byte into `coordination/planning_commit.py`, with their
docstrings and comments and the minimal imports. `implement.py` imports the module and calls
through it. `git diff --color-moved=zebra` must show moved blocks only.

### Subtask T016 – Adjust commit

- Apply the public renames from the contract.
- Delete the moved names from `implement.py`, including re-exports (research R-3).
- Bring `mypy --strict`, ruff, format and C901 to clean on the new module.
- Re-point test imports and patches of the moved names to `specify_cli.coordination.planning_commit`.
  This covers `test_implement_bookkeeping_identifiers.py`, `test_implement_demotion_guard_4979.py`,
  `test_meta_bypass_diagnosability.py`, `test_partition_authority_characterization.py` and the
  importers of `_load_fallback_mission_meta` / `_feature_dir_file_paths`; use `grep -rln` over
  `tests` for each moved name.

### Subtask T017 – Gates (each widened list proven with a plant)

- `CHURN_SURFACE_MODULES` (`test_exemption_registry_ratchet.py:~79`): add the module.
- `_WRITE_DIR_CONSUMER_MODULES` (`test_no_write_side_rederivation.py:~126`): add it.
- `test_mid8_contract_sensitive_routing.py:~59`, `test_meta_fail_closed_full_census_contract.py:~86`,
  `test_cutover_byte_stability.py:~63`, `tests/contract/test_terminology_guards.py:~53` and
  `test_feature_alias_scope.py:~60`: add it where the moved code is in that scan's subject.
- `_TRIO_FILES` / `_CORE_FILES` (`test_trio_seam_only.py`): add it to `_TRIO_FILES` if it carries
  read-seam calls (`placement_seam(...).read_dir`; `_planning_artifact_source_dir` and
  `_load_primary_anchored_mission_meta` do). It is **not** a pure `_CORE_FILES` member (it runs git
  subprocesses and file reads); record why.
- The no-CLI import guard as described above.
- The `test_commit_recipes.py` re-key as described above.

### Subtask T018 – Seam unit tests

`tests/specify_cli/coordination/test_planning_commit.py`:
- partition: PRIMARY vs residue, `meta.json` defaults to PRIMARY;
- guard: both directions raise with the exact texts, and self-bookkeeping is exempt;
- demotion verdict, with a tiny git repo:
  - no baseline → `None`;
  - HEAD has the branch and the working copy drops it → the exact refusal;
  - corrupt HEAD or working copy → the corrupt text;
- identifier cascade: primary meta first, fallback second, `legacy-<slug>`, a declared mid8 wins;
- candidate enumeration: the `.worktrees/` guard raises `SafeCommitPathPolicyError`.

### Subtask T019 – Evidence

Record the counter before and after, the planted-break logs, the `test_commit_recipes` failing-set
comparison and the regression-subset timing.

## Definition of Done

- [ ] Move commit pure; adjust separate; `coordination/planning_commit.py` imports no CLI (guard proven).
- [ ] Characterization unedited and green; seam tests green; #5699 failing set unchanged.
- [ ] Gates widened with plants.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP04 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP04 --mission implement-degod-01M44488`), and work in the path it prints.

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
