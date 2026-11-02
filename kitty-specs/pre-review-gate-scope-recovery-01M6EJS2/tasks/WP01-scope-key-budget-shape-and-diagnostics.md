---
work_package_id: WP01
title: Scope key, budget shape and actionable refusals
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pre-review-gate-scope-recovery-01M6EJS2
base_commit: d3d24d41b930aaf0d9779801ed60dbfd323db7dc
created_at: '2026-11-02T17:01:50.314000+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Pre-review gate scope recovery
history:
- at: '2026-11-02T16:58:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/review/test_review_budget_scope_shape.py
- tests/review/test_pre_review_gate_scope_diagnostics.py
- docs/changelog/unreleased/6865-pre-review-gate-scope-recovery.fixed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/wp_metadata.py
- src/specify_cli/review/test_timeout.py
- src/specify_cli/review/pre_review_gate.py
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/specify_cli/status/test_wp_metadata.py
- tests/review/test_review_budget_scope_shape.py
- tests/review/test_pre_review_gate_scope_diagnostics.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py
- docs/development/how-to/review-gates.md
- docs/configuration/review-test-budget.md
- docs/api/configuration.md
- docs/changelog/unreleased/6865-pre-review-gate-scope-recovery.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Scope key, budget shape and actionable refusals

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Deliver, red-first, the three legs of issue #6865:

1. A work package file that carries the documented `pre_review_test_scope`
   frontmatter key parses under `WPMetadata` and its subtask roster resolves, so
   the recovery the gate advertises is usable (FR-001, FR-002, SC-001).
2. The review budget matches the scope the gate actually chose: a whole-declared
   command resolves the whole-command default (1,200 s) when the project declares
   no budget; a bounded target list keeps the 300 s scoped default; a declared
   `review.test_timeout_seconds` always wins; one number per transition (FR-004,
   FR-005, FR-008, C-003, SC-002).
3. Both refusals name the scope shape: `timed_out` names the whole declared
   command (with the command, the budget and the policy metadata that classifies
   scopes) or the bounded target list, and gives the recovery for that shape;
   `scope_oversized` names the bounded shape (FR-006, FR-007, SC-003).

No gate is weakened: `TIMED_OUT`/`CANCELLED` stay terminal, the opt-in
`NEW_FAILURES` block is untouched, `--skip-pre-review-gate` stays an explicit
opt-out (FR-009, SC-004).

## Context & Constraints

- Mission spec: `kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/spec.md`;
  plan: `plan.md`; data model: `data-model.md`; contract:
  `contracts/pre-review-gate-scope-contract.md`; operator notes: `quickstart.md`.
- Discovery evidence (`research.md`, F1/F2/F3): the derived scope is empty for a
  non-narrowing source by design; appending targets after `sh -c` never narrows
  the run; `WPMetadata(extra="forbid")` rejects the key.
- The retired census derivation stays retired: do **not** add a heuristic
  `src/**` → `tests/**` mapping (C-001).
- `review.test_command` stays the single command authority;
  `review.pre_review_test_command` stays a deprecated alias (C-002).
- Measured cost for the default's justification: `make test-fast` = 215.31 s of
  pytest on 2026-11-02 on this host.
- Repository rules: `CLAUDE.md` / `AGENTS.md`. No new dependency, no new config
  key, targeted suites only (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Branch Strategy

- **Strategy**: Current branch at workflow start: main. Planning/base branch for this mission: main. Completed changes must merge into main.
- **Planning base branch**: main
- **Merge target branch**: main

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: WP model and roster read of a pinned scope

- **Purpose**: prove the defect before fixing it (ATDD).
- **Steps**:
  1. In `tests/specify_cli/status/test_wp_metadata.py`, add a class that builds a
     WP file carrying `pre_review_test_scope: "tests/review tests/status"` and
     asserts: `read_wp_frontmatter` yields the value; `authored_subtask_roster`
     returns the authored roster (no `SubtaskRosterResolutionError`).
  2. Pair it with a same-fixture positive control: the identical WP without the
     key still resolves its roster, and a genuine typo key
     (`pre_review_test_scopes`) is still rejected (`extra_forbidden`).
  3. Run it and commit RED.
- **Files**: `tests/specify_cli/status/test_wp_metadata.py`
- **Notes**: the fixture must author `subtasks:` — the roster guard requires it.

### Subtask T002 – Red-first: review-budget shape resolution

- **Purpose**: pin the shape-dependent default and the declared-value precedence
  before implementing them.
- **Steps**: create `tests/review/test_review_budget_scope_shape.py` covering:
  - no declaration + `whole_command=True` → `WHOLE_COMMAND_TEST_TIMEOUT_SECONDS`;
  - no declaration + `whole_command=False` → `DEFAULT_TEST_TIMEOUT_SECONDS`;
  - `review.test_timeout_seconds: 900` → 900 for both shapes;
  - an invalid declaration (`true`) still raises `InvalidReviewTestTimeout` for
    both shapes;
  - the production seam `tasks_move_task_gates._mt_review_test_timeout` resolves
    the whole-command default for a state whose repo declares a review command
    and no budget, and the declared value when one is set.
  Run it and commit RED.
- **Files**: `tests/review/test_review_budget_scope_shape.py`
- **Notes**: build the move-task state with the existing test idiom
  (`SimpleNamespace`) and stub the scope-source resolver; do not construct a
  real mission.

### Subtask T003 – Red-first: refusal diagnostics name the shape

- **Purpose**: pin the wording that makes a refusal actionable, in both shapes.
- **Steps**: create `tests/review/test_pre_review_gate_scope_diagnostics.py` that
  drives `evaluate_pre_review_gate` (injected source, controlled clock/wait so
  the run times out deterministically) and asserts the `TIMED_OUT` reason for a
  non-narrowing source:
  - contains `whole declared command`, the declared command text,
    `review.test_timeout_seconds`, `review/gate_budget.py` / `_RULES`, and both
    recoveries (declare a budget; pin a bounded `pre_review_test_scope`);
  - is a single line and ≤ 800 characters (NFR-002);
  and for a bounded shape (`evaluate_with_scope` with `from_override` targets):
  - contains the targets and `bounded`, and never `whole declared command`.
  Add the `SCOPE_OVERSIZED` assertion (bounded shape named alongside targets).
  Run it and commit RED.
- **Files**: `tests/review/test_pre_review_gate_scope_diagnostics.py`
- **Notes**: reuse the engine tests' controlled-wait idiom rather than sleeping.

### Subtask T004 – Declare `pre_review_test_scope` on `WPMetadata`

- **Purpose**: make the documented field readable (FR-001/FR-002).
- **Steps**: add `pre_review_test_scope: str | None = None` to the
  review-metadata block of `src/specify_cli/status/wp_metadata.py`, with a short
  docstring/description naming its consumer (`_mt_pre_review_scope_override`) and
  the fact that it is a whitespace-separated pytest target list. Keep
  `extra="forbid"` untouched.
- **Files**: `src/specify_cli/status/wp_metadata.py`
- **Notes**: no validator needed; an empty string is treated as absent by the
  consumer.

### Subtask T005 – Whole-command budget default and selector

- **Purpose**: make the budget match the chosen scope (FR-004/FR-005).
- **Steps**: in `src/specify_cli/review/test_timeout.py`:
  - add `WHOLE_COMMAND_TEST_TIMEOUT_SECONDS = 1_200` with a comment citing the
    measured `make test-fast` cost and the repository's 20-minute per-PR CI cap;
  - add a keyword-only `whole_command: bool = False` to
    `resolve_review_test_timeout`, selecting the default only when neither an
    override nor a declaration is present;
  - keep validation, the ceiling and the error messages unchanged; update the
    module/function docstrings.
- **Files**: `src/specify_cli/review/test_timeout.py`
- **Notes**: `baseline.CAPTURE_BASELINE_TIMEOUT_SECONDS` and
  `pre_review_gate._DEFAULT_HEAD_RUN_TIMEOUT` keep their current meaning (the
  scoped default) — do not retune them.

### Subtask T006 – Wire the shape probe at the one budget seam

- **Purpose**: resolve the whole-command shape exactly once per transition
  (FR-008).
- **Steps**: in
  `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`:
  - add `_mt_declared_command_runs_in_full(root) -> bool` returning
    `not exposes_scope_breakdown(_mt_resolve_scope_source(root))`;
  - pass `whole_command=_mt_declared_command_runs_in_full(_mt_config_authority_root(st))`
    from `_mt_review_test_timeout`, keeping its memoisation on `st` so capture,
    the receipt match and every head leg see one number.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`
- **Notes**: import `exposes_scope_breakdown` from
  `specify_cli.review.scope_source`; do not add a second timeout reader.

### Subtask T007 – Shape-aware refusal reasons

- **Purpose**: name the scope the gate chose and why (FR-006/FR-007).
- **Steps**: in `src/specify_cli/review/pre_review_gate.py`:
  - add a small helper that classifies the shape from the resolved scope and the
    injected source (`None` source ⇒ bounded override tier;
    `exposes_scope_breakdown` ⇒ bounded; otherwise whole declared command);
  - extend `_unknown_timeout_reason` / `_finalize_budget_evidence` to carry the
    shape, the declared command (single line, truncated to ≤160 chars) and the
    shape-specific recovery; name `review/gate_budget.py` / `_RULES` as the
    policy metadata;
  - name the shape in the `SCOPE_OVERSIZED` reason.
  Update the console renderer in `tasks_move_task_gates.py` only if it restates
  the reason instead of printing it, and update the observability test's
  assertions to the new wording, keeping a bounded-shape expectation that proves
  the two shapes are distinguishable.
- **Files**: `src/specify_cli/review/pre_review_gate.py`,
  `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py`
- **Notes**: no new `GateOutcome`, no change to `verdict_aggregation`, the block
  policy or `--force`.

### Subtask T008 – Docs, changelog and verification

- **Purpose**: leave the operator path documented (FR-006 operator half,
  SC-003).
- **Steps**:
  - `docs/development/how-to/review-gates.md`: document the pinned
    `pre_review_test_scope` frontmatter recovery (accepted by the WP model), the
    two scope shapes, and the shape-dependent budget;
  - `docs/configuration/review-test-budget.md`: add the whole-command default,
    when it applies, and that a declared value always wins;
  - `docs/api/configuration.md`: add the `pre_review_test_scope` row to the work
    package frontmatter field table;
  - add `docs/changelog/unreleased/6865-pre-review-gate-scope-recovery.fixed.md`
    in the fragment shape (`docs/changelog/unreleased/README.md`), renaming it to
    the PR number once the PR exists;
  - run the targeted suites, `ruff check`/`ruff format --check` on the touched
    files, `python -m scripts.docs.check_docs_freshness --ci` (expect errors=0)
    and `python -m scripts.docs.check_changelog_style`.
- **Files**: the three docs pages and the changelog fragment.
- **Notes**: never edit `docs/changelog/CHANGELOG.md`; the fragment is the entry.

## Test Strategy

Mandatory, red-first, in this order:

```bash
# 1. RED slices (before each fix)
uv run --frozen pytest tests/specify_cli/status/test_wp_metadata.py -q
uv run --frozen pytest tests/review/test_review_budget_scope_shape.py -q
uv run --frozen pytest tests/review/test_pre_review_gate_scope_diagnostics.py -q

# 2. Green, plus the pre-existing gate ratchet
uv run --frozen pytest tests/review/ tests/specify_cli/status/test_wp_metadata.py \
  tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py \
  tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_parent_death.py -q

# 3. Quality
uv run --frozen ruff check src/specify_cli/review src/specify_cli/status/wp_metadata.py \
  src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
uv run --frozen ruff format --check src/specify_cli/review src/specify_cli/status/wp_metadata.py \
  src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
uv run --frozen python -m scripts.docs.check_changelog_style
```

Diff-cover requires ≥90% on changed lines: every new branch (both shapes, the
declared value, the invalid declaration) needs a test.

## Risks & Mitigations

- **Receipt mismatch** → one memoised resolution per transition; assert capture,
  receipt and head read the same number.
- **Consumer behaviour change** (300 s → 1,200 s for an undeclared-budget repo
  with a whole-suite command) → documented, bounded by the unchanged ceiling, and
  a declared value still wins.
- **Wording assertions churn** → update the observability test with paired
  shape assertions rather than loosening it.
- **Shape probe cost** → it reuses the existing `resolve_scope_source`
  selection; do not add a second selection path.

## Review Guidance

- The roster guard must read a pinned-scope WP end to end; a model-only test is
  not enough.
- No gate weakened: check the terminal/block/skip tests still pass unchanged.
- The refusal must name the shape *and* be actionable; check both shapes on the
  same fixture family.
- No census resurrection, no new config key, no second budget reader.

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done`
(the event log is the sole authority; do not tick markdown boxes).
