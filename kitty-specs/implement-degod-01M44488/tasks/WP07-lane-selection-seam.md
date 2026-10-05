---
work_package_id: WP07
title: Lane selection and allocation preflight into the lanes seam
dependencies:
- WP06
requirement_refs:
- FR-005
- FR-012
- C-006
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T034
phase: Phase 1 - Seam extraction
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_implement_support_lane_selection.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/lanes/implement_support.py
- tests/lanes/test_implement_support_lane_selection.py
- tests/cli/commands/test_implement_base_flag.py
- tests/specify_cli/cli/commands/test_implement_base_ref.py
- tests/specify_cli/cli/commands/test_implement_vcs_lock_claim.py
- tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py
- tests/specify_cli/lanes/test_lane_base_honoring.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_exemption_registry_ratchet.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Lane selection and allocation preflight into the lanes seam

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

Move these decisions into `src/specify_cli/lanes/implement_support.py`, which already owns
`create_lane_workspace`, `_ensure_repo_root_checkout_available` and `guard_repo_root_claim`. Use
typed errors; the command keeps every printed text byte-identical. Contract:
`contracts/seam-decisions.md` §lanes.
- **Base-ref family (#4969 origin-preferred):** `_rev_parse_ref`, `_is_ancestor` and
  `_resolve_base_ref` move. They use `git_stdout`, which WP05 already moved to this module.
- **`_validate_base_ref` and `_raise_base_ref_unresolved` stay CLI-side**, in the command package.
  - `_validate_base_ref` has no src caller, but `test_implement_base_ref.py:~97` and
    `test_implement_base_flag.py:~163/186/221` pin `pytest.raises(typer.Exit)` and patch
    `console.print`.
  - Keep both as thin CLI translators: call the seam, and on `BaseRefUnresolved` print
    `_BASE_REF_UNRESOLVED_MSG` and raise `typer.Exit(1)`.
  - Their tests then need only mechanical re-points, never assertion edits.
- `_resolve_execution_lane` (without the tracker: the seam returns the manifest and lane, and the
  command completes the tracker step with today's text).
- `_resolve_active_lanes_manifest`, which becomes `resolve_effective_base`. It returns
  `(effective_base, ignored_on_planning_lane)` and raises `BaseRefUnresolved`.
  - The command prints `Warning: --base is ignored for repository-root planning work` and
    `_BASE_REF_UNRESOLVED_MSG` exactly as today.
  - **Critical:** today the unresolved-base path prints the message and raises `typer.Exit(1)`
    **inside the create `try`** (implement.py ~L2176). `except typer.Exit` then renders the tracker
    and re-raises.
  - If `BaseRefUnresolved` escaped to `except Exception` instead, the tracker would show
    `workspace allocation failed: <str(exc)>` plus `Workspace allocation failed:`, which is a text
    change.
  - So the command catches `BaseRefUnresolved` **inline at the call site inside that try**, prints
    the message, and raises `typer.Exit(1)`. The WP02 characterization pins the output.
- `_refuse_repo_root_checkout_if_unavailable` (it already delegates to
  `_ensure_repo_root_checkout_available`).
- **VCS lock:** `_ensure_vcs_in_meta`'s decision becomes `ensure_vcs_locked(feature_dir)` with
  typed errors for a missing or invalid `meta.json`. The command keeps `_ensure_vcs_in_meta` as the
  printing adapter, or replaces it with an equivalent one, while keeping its three console lines,
  their order, and exit 1. `_ensure_vcs_in_meta` is in `implement.__all__` and in the dead-symbol
  allow-list; keep both consistent.
- The WRITE_CHECKOUT_* raise sites in `implement_support.py` are **not** touched (C-006).

## Context & Constraints

- Pinned order: the write-checkout refusals run **before** the VCS lock is written
  (`test_single_branch_implement_refusals.py:~480,488` asserts no `vcs` key after a refusal), and
  the WP02 characterization pins it too.
- `lanes/` must not import `specify_cli.cli` (C-004). `implement_support.py:~400` already lazily
  imports `cli.console`; that is pre-existing. Do not add more, and do not route new printing
  through it.
- `test_no_write_side_rederivation.py` scans `_WRITE_DIR_CONSUMER_MODULES`; `lanes/implement_support.py`
  is not in it today. If the moved base-ref code matches one of its grammars (HEAD-selector,
  root-walk, mid8 recompute), add the module and prove it with a plant. Otherwise record that it is
  not in scope.
- The `--base` success line `→ Using explicit base ref: …` prints after allocation succeeds (#3571).
  Leave its placement in the command.

## Subtasks & Detailed Guidance

### Subtask T030 – Verbatim move commit

Move the listed functions and constants byte-for-byte into `implement_support.py`. `implement.py`
calls them in attribute style (`implement_support.<fn>(...)`). Check `--color-moved`.

### Subtask T031 – Adjust commit: typed errors, renames, typing

- Introduce `class BaseRefUnresolved(StructuredError)`, following the `WriteCheckout*Error` pattern
  in the same module (error code, message, `base_ref` attribute). `_raise_base_ref_unresolved`'s
  `typer.Exit` moves to the command, which catches the typed error and prints the identical message.
- `_resolve_execution_lane` drops the `tracker` parameter. The command does
  `tracker.complete("validate", "Execution: repository root planning workspace")` or
  `f"Lane: {lane.lane_id}"` exactly as today.
- Drop leading underscores on the public seam names per the contract, and fix strict typing (for
  example `_refuse_repo_root_checkout_if_unavailable`'s no-any-return, implement.py ~L1902).

### Subtask T032 – VCS-lock decision

- `ensure_vcs_locked(feature_dir) -> bool` (the contract already says `-> bool`) returns whether it wrote the lock, and raises
  `MissionMetaMissing` / `MissionMetaInvalid` (typed; reuse existing types from `core.paths` if they
  fit).
- The command prints these lines and exits 1:
  - `Error: Invalid JSON in meta.json: <exc>`;
  - `Error: meta.json not found in <dir>` plus the `/spec-kitty.specify` hint line;
  - `→ VCS locked to git in meta.json`.

  The text and order are identical to today.

### Subtask T033 – Seam unit tests and re-pointed tests

- `tests/lanes/test_implement_support_lane_selection.py`. Cases:
  - `resolve_execution_lane` on a repo-root planning workspace returns `(None, None)`;
  - a WP not in the lanes manifest raises `ValueError` with the exact text;
  - a missing `lanes.json` raises `MissingLanesError`;
  - `resolve_base_ref`: origin preferred when local is absent or behind, local kept when ahead,
    `None` when unresolvable (tiny git repo);
  - `resolve_effective_base`: the planning lane is ignored, and an unresolvable ref raises
    `BaseRefUnresolved`;
  - `ensure_vcs_locked`: writes once, then is a no-op; missing and invalid meta raise the typed
    errors.
- Re-point `test_implement_base_flag.py`, `test_implement_base_ref.py` and `test_lane_base_honoring.py`
  imports and patches to the new home (mechanical only). `test_resolve_lanes_dir.py` belongs to
  WP03. Update the dispatch map.

### Subtask T034 – Gates

- `dead_symbol_allowlist.yaml` `_ensure_vcs_in_meta` row (~L652–657): keep it if the symbol stays
  in `implement`; re-key or delete it if it moved or now has a src caller. Run `test_no_dead_symbols.py`.
- `CHURN_SURFACE_MODULES` (`test_exemption_registry_ratchet.py`): add `lanes/implement_support.py`
  if moved code contains a dirty-state or churn predicate. Otherwise record why not.
- Run the liveness gate, `test_layer_rules`, `test_safe_commit_import_boundary` and
  `test_lane_context_single_writer`; `save_context` must only be called from `worktree_allocator`.
- Planted-violation proof for each list you widened.

## Definition of Done

- [ ] Move and adjust commits separate; printed texts and order identical (characterization suite unedited and green).
- [ ] `lanes/implement_support.py` gains no `specify_cli.cli` import.
- [ ] Seam tests green; re-pointed tests green; gates green.
- [ ] `mypy --strict` clean on `implement_support.py`.

## Review Guidance

- Diff the printed messages: base-ref unresolved, planning-lane warning, VCS-lock lines.
- Confirm the refusals-before-VCS-lock order.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP07 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP07 --mission implement-degod-01M44488`), and work in the path it prints.

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
