---
work_package_id: WP02
title: Characterization suite through public entry points
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-014
- SC-003
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 0 - Safety net
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_implement_characterization.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/commands/test_implement_characterization.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Characterization suite through public entry points

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

Pin today's `spec-kitty implement` behaviour before any source moves (FR-009, FR-014, SC-003). No
`src/` file changes.
- **Suite.** `tests/specify_cli/cli/commands/test_implement_characterization.py` (`git_repo`,
  `integration`) is green on the base commit.
  - It drives only `CliRunner` over the `implement` Typer command, the `implement` function called
    the way `agent/workflow.py` calls it, and real-git fixtures.
  - No assertion names an implement-family internal.
  - Every case has a planted-break proof in the activity log.
  - Runtime ≤ 60 s.
- **Dispatch map.** `tests/specify_cli/cli/commands/_implement_dispatch.py` holds the single
  logical-collaborator → dotted-target map plus `patch_collaborator(monkeypatch, logical, replacement)`.
  - It is used only where a failure cannot be produced by a real fixture.
  - WP01's dispatch-map gate hook now runs (remove its skip) and is green.
- After this WP, `test_implement_characterization.py` is **frozen** (common rule SC-003).

## Context & Constraints

- Fixture helpers to reuse, not re-invent:
  - `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py` (real-git
    single_branch, WRITE_CHECKOUT_*, no-`vcs`-after-refusal checks);
  - `tests/integration/test_wp_integrity_p0_repro.py` and `test_wp_integrity_checkout_identity.py`
    (coord topology; checkout-identity refusal);
  - `tests/lanes/test_destroyed_lane_guard_{helpers,lanes_topology,tip_rows}.py` (DESTROYED_LANE,
    LANE_WORK_TIP_UNKNOWN);
  - `tests/specify_cli/cli/commands/test_implement_demotion_guard_4979.py` (meta demotion);
  - `tests/agent/test_implement_command.py` `create_meta_json`;
  - `test_implement_json_safe_output.py`.
- **Exception visibility.** `_json_safe_output` (implement.py ~L201–205) turns every non-`Exit`
  exception into `typer.Exit(1) from exc`, so `CliRunner` shows only exit 1. For "propagates" rows,
  assert exit 1, the **absence** of the soft-warning text, and, on a direct function call, the
  `__cause__` type.
- **Programmatic call.** `json_output` and `recover` default to `typer.Option(...)`, and an
  `OptionInfo` object is truthy. Mirror `agent/workflow.py:~1620` **exactly**: pass
  `json_output=False, recover=False` and omit what it omits.
- **Text wrapping.** Rich wraps tracker output at the `CliRunner` width. Normalize whitespace in
  full-message assertions, or set a wide terminal (`COLUMNS=200` / `env=`).
- **Order quirk.** `--base <nonexistent>` fails **after** `_ensure_vcs_in_meta` wrote `vcs` and after
  the planning commit ran (implement.py ~L2168 vs ~L2176). Pin *that* state: `vcs` present, planning
  commit landed. Do not assert no-mutation for it.

## Subtasks & Detailed Guidance

### Subtask T005 – Dispatch map + fixture builders

- Create `_implement_dispatch.py`. The map **must** be a module-level dict named `DISPATCH`
  (`{logical: "specify_cli.cli.commands.<module>.<name>"}`), because WP01's liveness hook imports
  that name. Add the docstring rules: scope (this suite plus the F-50 test),
  counted by SC-002, only WP updates allowed.
- Initial entries:
  - `start_status` → `specify_cli.cli.commands.implement.start_implementation_status`;
  - `allocate` → `…implement.create_lane_workspace`;
  - `claim_commit` → `…implement._commit_wp_claim_status`;
  - `safe_commit` → `…implement.safe_commit`;
  - plus the spies T007 needs.
- Build module-scoped real-git fixture builders (flat, lanes, coord, single_branch) that reuse the
  existing helpers.

### Subtask T006 – Refusal families (exit code + text or code + no mutation)

For each case assert:
- the exit code;
- the text (token plus full message, whitespace-normalized; decide and note per case whether the
  full message is a contract);
- **no mutation**: no new `.worktrees/` entry, no `vcs` added to `meta.json`, no new
  `status.events.jsonl` line, and HEAD unchanged where the refusal precedes the planning commit.

Cases:
- `--mission` omitted → exit 2, `--mission <slug> is required`; also with `--recover`.
- WP not finalized (genesis) → exit 1, `is not finalized; run \`spec-kitty agent mission finalize-tasks\``. No test pins this today.
- Dependency not approved → exit 1, the full `dependencies_not_satisfied: … all dependencies must be approved or done before implementation can start`.
- Protected status-commit target with auto-commit → exit 1, `Refusing to start implementation status on protected branch`.
- `lanes.json` missing → `lanes.json is required`. `lanes.json` corrupt → the `CorruptLanesError` text.
- WP not in the lanes manifest → `is not assigned to any lane in lanes.json`.
- Bulk-edit inference un-acknowledged → exit 1 and the `Bulk Edit Inference Warning` panel.
  Occurrence gate failure → its render.
- Checkout-identity refusal (claiming from another mission's lane worktree) → today's text; reuse
  `test_wp_integrity_checkout_identity.py`.
- #1598 structural planning change (an uncommitted `git rm` of a planning file) → the
  `cannot be auto-committed to the coordination branch` refusal.
- Meta demotion (#4979) → the `silently demotes` refusal.
- single_branch WRITE_CHECKOUT_WRONG_BRANCH, WRITE_CHECKOUT_OCCUPIED and WRITE_CHECKOUT_DIRTY →
  today's text, and no `vcs`.
- **DESTROYED_LANE** and **LANE_WORK_TIP_UNKNOWN** through `implement()` (reuse the destroyed-lane
  fixtures) → exit 1, `Workspace allocation failed:`, and the code/message substring.
- An allocator conflict type that carries `next_step` (for example `DependencyLaneMergeConflictError`,
  via a real conflicting dependency lane if feasible, otherwise the dispatch map on `allocate`) →
  the `Next step:` line.
- `--base <nonexistent>` → exit 1, `Base ref '…' does not resolve. Try 'git fetch' or 'git branch -a' to see available refs.`, with the post-state pinned as noted above.
- `--base X` on a repository-root planning WP → the `Warning: --base is ignored for repository-root planning work` line, then success.

### Subtask T007 – Side-effect order, #4888, exception table

- **Order**: on a healthy lanes fixture, wrap collaborators in recording spies through the dispatch
  map, and assert the sequence: target branch → dependency gate → planning commit → bulk-edit gate
  → operational context → workspace resolve → VCS lock → allocate → status start → claim commit.
- **#4888**:
  - `start_status` raises `RuntimeError("boom")` → exit 1 and
    `Workspace was created but starting the WP status failed: boom.` +
    `The WP status transition may have already landed on the lane branch.`;
  - an exception carrying `commit_sha="abc"` → the `(sha=abc)` variant;
  - `allocate` raises → `Workspace allocation failed:`.
- **Claim-commit exception table**:
  - `SafeCommitPathPolicyError`, `SafeCommitHeadMismatch` and `PlacementResolutionRequired` from
    the claim commit propagate: exit 1, no soft warning, `__cause__` type on a direct call;
  - a generic `RuntimeError` at the `safe_commit` level gives exit 0 and
    `Warning: Could not auto-commit lane change:`;
  - a generic `RuntimeError` at the `claim_commit` level gives exit 0 and
    `Warning: Could not update WP status:`.

### Subtask T008 – `--json`, programmatic call, recover

- **`--json`**: the success payload keys and values on a healthy fixture; the error payload
  `{"status":"error","error":…,"wp_id":…}` on a refusal; stdout is exactly one JSON document.
- **Programmatic call** (FR-014): mirror workflow.py exactly. Assert `inspect.signature(implement)`
  names and defaults (including that `json_output` / `recover` defaults are `OptionInfo`), and
  `implement.__wrapped__` exists.
- **`--recover`**: on a mission with nothing to recover → `No crashed implementation sessions found.`
  (console) and the JSON no-action payload.

### Subtask T009 – Proofs and freeze

- Remove WP01's dispatch-map skip and run the gate green.
- Record every planted break (one per case family), the suite runtime and the counter output in the
  activity log. Expect the counter to rise by the `patch_collaborator` calls; that is expected and
  honest.

## Definition of Done

- [ ] All cases green on the base; a planted break per family proven red.
- [ ] No assertion names an implement internal; injection only through the dispatch map.
- [ ] Dispatch-map liveness hook active and green.
- [ ] Suite ≤ 60 s.

## Review Guidance

- Re-run three planted breaks yourself.
- `grep -n "commands.implement" test_implement_characterization.py` must find nothing.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP02 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP02 --mission implement-degod-01M44488`), and work in the path it prints.

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
