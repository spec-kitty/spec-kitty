---
work_package_id: WP08
title: Claim recording seam
dependencies:
- WP07
requirement_refs:
- FR-007
- FR-012
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T035
- T036
- T037
- T038
- T039
phase: Phase 1 - Seam extraction
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/implement_claim.py
- tests/specify_cli/cli/commands/test_implement_claim.py
- tests/status/test_claim_policy_metadata.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/implement_claim.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/status/__init__.py
- src/specify_cli/status/emit.py
- tests/specify_cli/cli/commands/test_implement_claim.py
- tests/status/test_claim_policy_metadata.py
- tests/specify_cli/cli/commands/test_issue_610_head_mismatch_not_swallowed.py
- tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py
- tests/specify_cli/cli/commands/test_implement_placement_routing.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_trio_seam_only.py
- tests/architectural/test_exemption_registry_ratchet.py
- tests/git/test_guard_capability_regression.py
- tests/git/test_protection_policy_mission_scope.py
- tests/integration/test_issue_3784_coord_tasks_md_primary_bundle_guard.py
- tests/agent/test_implement_command.py
- tests/integration/test_status_emit_on_alloc_failure.py
- tests/specify_cli/cli/commands/test_implement_vcs_lock_claim.py
- tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py
- tests/specify_cli/lanes/test_lane_base_honoring.py
- tests/specify_cli/test_specify_topology_flag.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Claim recording seam

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

- **Move claim recording into `src/specify_cli/cli/commands/implement_claim.py`.** It stays in the
  command package because `_commit_wp_claim_status` imports
  `cli.commands.agent.tasks._collect_status_artifacts` (C-004). The functions to move:
  - claim preflight: `_protected_branch_status_commit_error`, `_status_commit_destination_branch`,
    `_raise_if_status_commit_protected`;
  - status start: `_claim_policy_metadata`, `_start_wp_implementation_status`;
  - claim commit: `_primary_surface_status_paths`, `_commit_wp_claim_status`.
- **Extract `claim_commit_paths(...)`** (contract §implement_claim). This pure function returns the
  exact ordered path list the claim commit stages today:
  1. `wp_file.resolve()`;
  2. the filtered status artifacts;
  3. `meta.json` if it exists;
  4. `.kittify/config.yaml` if it exists.

  This shapes #5673: the future fix becomes a one-line change here plus a test. **Do not fix #5673
  in this WP** (C-005); the bundle stays byte-identical.
- **Dedupe the claim policy metadata.** One `claim_policy_metadata(shell_pid, agent)` exported by
  the status facade next to `build_claim_policy_metadata`, importing `core.process_liveness`
  lazily. Both `implement_claim` and `agent/workflow_executor.py` (~L92–117) call it, and both old
  copies are deleted.
  - The two bodies are semantically identical. Confirm this first, and keep workflow_executor's
    `dict[str, Any]` local annotation trick if mypy needs it.
  - In-matrix tests in `tests/status/test_claim_policy_metadata.py` keep the diff-cover gate on the
    `status/*` critical path.
- The propagate/soften contract of the claim commit stays exactly as today:
  - **inner** (`_commit_wp_claim_status`): re-raise `SafeCommitPathPolicyError` and
    `SafeCommitHeadMismatch`; soften others with `Warning: Could not auto-commit lane change:`;
  - **outer** (in `implement()`): re-raise `SafeCommitPathPolicyError`, `SafeCommitHeadMismatch`
    and `PlacementResolutionRequired`; soften others with `Warning: Could not update WP status:`.

## Context & Constraints

- `tests/specify_cli/cli/commands/test_implement_placement_routing.py:~97,125` uses
  `inspect.getsource(implement)` and requires the `except PlacementResolutionRequired:` /
  `except SafeCommitHeadMismatch:` clauses before the soft-warning print.
  - The **outer** try stays in `implement()` in this WP, so that pin keeps working.
  - `_commit_wp_claim_status`'s own docstring references the pin.
  - WP09 moves the outer try (T042/T043) and re-points the pin there. Do not re-point it here unless your change moves it.
- **WS#3 allow-list.** `tests/architectural/test_no_write_side_rederivation.py:~259–268` pins
  `implement.py::_status_commit_destination_branch` by rel_path+qualname, and its twin guard at
  ~L484 pins the literal path. Re-point both to `implement_claim.py`, with a one-line rationale
  (precedent: the workflow → workflow_cores re-point). Add `implement_claim.py` to
  `_WRITE_DIR_CONSUMER_MODULES`.
- `test_issue_610_head_mismatch_not_swallowed.py` patches `_commit_wp_claim_status` /
  `get_current_branch` / `ProtectionPolicy` on implement: re-point it.
  `test_implement_compact_identity_4665.py` imports `_start_wp_implementation_status`: re-point it.
- Strict typing: `_claim_policy_metadata` had a no-any-return (implement.py ~L1830); the shared
  helper fixes it.

## Subtasks & Detailed Guidance

### Subtask T035 – Verbatim move commit
Move the listed functions byte-for-byte into `implement_claim.py`. `implement.py` calls them through
the module (`implement_claim.<fn>`), so a single patch on the sibling intercepts. Check `--color-moved`.

### Subtask T036 – `claim_commit_paths`
Extract the bundle computation from `_commit_wp_claim_status` into the pure function. The caller
passes the collected status artifacts and `routes_through_coord`. The returned order matches
today's list exactly.

### Subtask T037 – Shared `claim_policy_metadata`
- Add the helper to the status facade module that exports `build_claim_policy_metadata` (check
  `src/specify_cli/status/__init__.py` and `status/emit.py`).
- Delete both copies and re-point both callers.
- **UnboundLocalError trap (HIGH).** `agent/workflow_executor.py:~1734` binds a *local* named
  `claim_policy_metadata = _claim_policy_metadata(...)`, reused at ~L1737 and ~L1780. A module-level
  `from specify_cli.status import claim_policy_metadata` would make that function raise
  UnboundLocalError (ruff F823).
  - Import the helper under an alias (`from specify_cli.status import claim_policy_metadata as build_claim_policy_metadata_for_shell`),
    or call it as `status.claim_policy_metadata(...)`.
  - Do not rename the local. Run ruff F823 and `tests/specify_cli/cli/commands/agent/` workflow
    tests (targeted files).
- Run `tests/architectural/test_status_module_boundary.py` and `test_cold_import_status_boundary.py`.
- Add `tests/status/test_claim_policy_metadata.py`: baseline captured → full triple; no baseline →
  `{"shell_pid", "agent"}` only (monkeypatch `capture_creation_time_baseline` at its owner module).

### Subtask T038 – Re-point pins, tests and the dispatch map
Do the WS#3 + twin, the 610 and 4665 tests, and the dispatch map (`claim_commit`, `start_status`
entries). Run the characterization suite: unedited and green.

### Subtask T039 – Seam tests
`tests/specify_cli/cli/commands/test_implement_claim.py`:
- `claim_commit_paths`: on flat, the paths include the status artifacts; on coord they drop
  `.worktrees/` paths; `meta.json` and `config.yaml` are included when present (pin today's #5673
  behaviour explicitly, naming #5673 in the test docstring);
- the protected-branch error text;
- the propagate/soften table at the `_commit_wp_claim_status` level;
- `_start_wp_implementation_status` error translation (`WorkPackageClaimConflict` → `Error: <exc>`;
  `TransitionError` → `Error: Could not start implementation status: <exc>`).

## Definition of Done

- [ ] Move and adjust commits separate; the characterization suite unedited and green.
- [ ] One `claim_policy_metadata` definition; workflow_executor uses it; status tests in-matrix and green.
- [ ] WS#3 allow-list and twin re-pointed (and proven by plant); gate lists widened.
- [ ] `mypy --strict` clean on `implement_claim.py` and the touched status module.

## Review Guidance

- Byte-compare the bundle order.
- Confirm #5673 behaviour unchanged (`config.yaml` still included).
- Confirm the outer try still lives where the source pin expects it.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP08 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP08 --mission implement-degod-01M44488`), and work in the path it prints.

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
