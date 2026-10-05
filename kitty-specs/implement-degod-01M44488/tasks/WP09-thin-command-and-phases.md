---
work_package_id: WP09
title: Thin command and phase sequence
dependencies:
- WP08
requirement_refs:
- FR-001
- FR-002
- FR-014
- NFR-001
- NFR-002
- SC-001
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T040
- T041
- T042
- T043
- T044
phase: Phase 3 - Thin command
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/implement_phases.py
- src/specify_cli/cli/commands/implement_recover.py
- tests/specify_cli/cli/commands/test_implement_phases.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/implement_phases.py
- src/specify_cli/cli/commands/implement_recover.py
- pyproject.toml
- tests/specify_cli/cli/commands/test_implement_phases.py
- tests/specify_cli/cli/commands/test_implement_placement_routing.py
- tests/specify_cli/cli/commands/test_implement_json_safe_output.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/specify_cli/test_operational_context_wiring.py
- tests/agent/test_implement_programmatic_call.py
- tests/agent/cli/commands/test_implement_preflight.py
- tests/architectural/test_trio_seam_only.py
- tests/architectural/test_exemption_registry_ratchet.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/contract/test_terminology_guards.py
- tests/contract/test_feature_alias_scope.py
- tests/integration/test_wp_integrity_checkout_identity.py
- tests/specify_cli/test_change_mode_read_boundaries.py
- tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py
- tests/agent/test_implement_command.py
- tests/agent/test_mission_handle_json_errors.py
- tests/cli/test_implement_bulk_edit_planning.py
- tests/integration/test_status_emit_on_alloc_failure.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Thin command and phase sequence

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

- **`implement.py` becomes thin (FR-001, SC-001: at most 800 lines by `wc -l`).** It keeps:
  - the Typer `implement` command, with signature, option defaults and decorators byte-identical
    (FR-014);
  - `_json_safe_output` and its `_json_wrapper_*` helpers;
  - **not** `detect_feature_context`. Its only callers (`_detect_wp_context` and
    `_recover_resolve_context`) move to `implement_phases` and `implement_recover`, so leaving it
    in `implement.py` would create an import cycle (`implement` imports them at module top). It
    moves to `implement_phases.py`, and `implement_recover` imports it from there;
  - presentation: `_report_workspace_created`, `_print_workspace_ready_banner`,
    `_build_implement_json_payload`, `_BANNER_*`;
  - the tracker steps;
  - the call into the phase sequence.
- **`implement_phases.py` holds the ordered phase functions (FR-002).** Each is a named function
  that consumes and produces the immutable phase values from data-model.md (`ImplementContext`,
  `ClaimPreflight`, `WorkspaceSelection`, `AllocationResult`):
  `detect_context` → `claim_preflight` (target branch, protected check, status surface, lanes dir,
  dependency gate) → `commit_planning_artifacts` → `run_bulk_edit_gate` + `build_operational_context`
  → `select_workspace` → `allocate` → `record_claim` (status start) → `commit_claim`.
  - Bodies move **verbatim** from today's `implement()` blocks.
  - **Parameters, not lookups (SC-002 honesty).** Phase functions receive `repo_root`, and the
    values earlier phases produced, as parameters. `implement()` calls `find_repo_root()` once
    and passes the result. Tests can then call phase functions with `tmp_path` and real values
    instead of patching `find_repo_root` / `detect_feature_context` (about 40 patch sites today).
    This is the test-remediation §5 "orchestrator takes `repo_root`" principle.
  - `_detect_wp_context` and `_run_bulk_edit_gate_and_inference` move here.
- **`implement_recover.py` holds `--recover`.** Move `_run_recover_mode` and the `_recover_*`
  helpers verbatim; the output is unchanged.
- **Tracker step boundaries and per-step exception handling are byte-identical**:
  - detect: catch the fixed tuple → exit 1;
  - validate: catch `Exception` → tracker error + exit 1;
  - create: catch `Exit` → render + raise; catch `Exception` → the `workspace_created`-aware
    message, plus `next_step` for the three allocator errors;
  - outer claim-commit try: propagate three types, soften the rest.

  The tracker and its exception handling stay in `implement()`, or in a CLI-layer helper in
  `implement.py`. The phase functions raise; they do not render.
- `implement()` complexity drops below 15 (NFR-001).
- `mypy --strict`: remove `implement.py`'s quarantine entry (`pyproject.toml` ~L2675, an
  `ignore_errors` override) if the thin module is strict-clean. Otherwise keep it unchanged and list
  the remaining errors in the activity log. The two known ones are `_json_wrapper_handle_typer_exit`
  (~L175) and the untyped decorator on `implement` (~L1976); fix them if typing-only.

## Context & Constraints

- **Source-text pins to re-point (never loosen):**
  - `tests/specify_cli/cli/commands/test_implement_placement_routing.py:~97,125`: the except-order
    pin on `inspect.getsource(implement)`. If the outer claim-commit try stays in `implement()`, it
    keeps working; if it moves into a helper, re-point the pin to that helper.
  - The same file, ~L307: a forbidden-ternary scan over the module text. Widen it to the implement
    family (all `implement*.py`), so the moved code stays scanned.
  - `tests/integration/test_wp_integrity_checkout_identity.py:~299–304`: pins the text
    `resolve_workspace_for_wp(repo_root, mission_slug, wp_id, write_intent=True)` in
    `implement.py`, plus a write-intent assertion. Re-point both to `implement_phases.py`'s
    `select_workspace`.
  - If WP01 made `test_issue_1615…` an AST assertion on `implement`, re-point it to the phase that
    now calls `resolve_status_surface_with_anchor`.
  - `tests/specify_cli/test_operational_context_wiring.py:~254`: requires
    `build_operational_context_for_claim` and `require_active_role` in `implement`'s source.
    Re-point it to the phase function that now calls them.
- **Programmatic call.** `agent/workflow.py:~83,1620` imports `implement` and calls it with kwargs.
  Do not touch workflow.py. `tests/agent/test_implement_programmatic_call.py` and the WP01
  characterization must stay green.
- **Console singleton.** Every print uses `specify_cli.cli.console.console`; never cache
  `console.file`. `--json` error text = the last 20 captured lines, so print order matters.
- The lazy imports inside `implement()` (charter preflight, `surface_resolver`, `runtime_bridge`,
  `is_planning_lane`) move with their blocks. Keep them lazy.
- Gate lists: add `implement_phases.py` and `implement_recover.py` to `_TRIO_FILES`,
  `CHURN_SURFACE_MODULES`, `_WRITE_DIR_CONSUMER_MODULES` and the terminology/alias scans wherever
  they carry moved code. Prove each with a plant.

## Subtasks & Detailed Guidance

### Subtask T040 – `implement_phases.py` (verbatim move of the phase blocks)
- Create the frozen phase-value types first, in one small commit.
- Then the move commit: each `implement()` block between tracker calls becomes a phase function,
  with its body byte-identical apart from returning the value it used to bind locally.

### Subtask T041 – `implement_recover.py`
Verbatim move of the recover family. `implement()` calls `implement_recover.run_recover_mode(...)`
after the `--mission` guard, which still exits 2 first.

### Subtask T042 – Thin `implement()`
Rebuild `implement()` as: guard → recover → tracker steps calling the phase functions inside the
same try/except shapes → claim-commit outer try → present. Run ruff C901 and confirm < 15.

### Subtask T043 – Phase-order test and pin re-pointing
- `tests/specify_cli/cli/commands/test_implement_phases.py`:
  - on a healthy fixture, spy each phase function (patched at `implement_phases.<fn>`) and assert
    the call order;
  - **mandatory direct tests (SC-005)** for the phases no earlier WP gave a seam test:
    - `run_bulk_edit_gate` (verdicts: pass / informational panel / blocking panel + `Exit`);
    - `build_operational_context` (the `require_active_role` path);
    - presentation: `_build_implement_json_payload` golden dict on a fixture result,
      `_print_workspace_ready_banner` captured output for the repo-root, single_branch and lane
      variants, and `_report_workspace_created`.
  - Each test calls the function directly with real values and patches nothing in the implement
    family.
- Re-point the three source pins above.

### Subtask T044 – Quarantine, gates, size
Handle the mypy quarantine entry, widen the gate lists with proofs, check `wc -l` (implement.py
≤ 800, every new sibling ≤ 800), and record the counter.

## Definition of Done

- [ ] `wc -l src/specify_cli/cli/commands/implement.py` ≤ 800; no new module > 800.
- [ ] `implement()` C901 < 15; the Typer signature, defaults and decorators unchanged (FR-014 test green).
- [ ] Characterization suite unedited and green; phase-order test green.
- [ ] Source pins re-pointed, not loosened; gate lists widened with plant proofs.
- [ ] Quarantine decision recorded.

## Review Guidance

- Compare `implement()` before and after for the exception shapes.
- Run `--json` success and error manually on a fixture.
- Run `spec-kitty agent action implement` once on a scratch mission if feasible.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP09 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP09 --mission implement-degod-01M44488`), and work in the path it prints.

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
