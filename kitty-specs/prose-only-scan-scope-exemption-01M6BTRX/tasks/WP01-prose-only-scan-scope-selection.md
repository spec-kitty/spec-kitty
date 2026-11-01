---
work_package_id: WP01
title: Prose-only diffs keep the gates that read prose
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Routing fix
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- scripts/ci/battery_scope.py
- scripts/ci/gate_selection.py
- tests/ci/test_battery_scope.py
- tests/ci/test_ci_module_wiring.py
- tests/ci/test_ci_config_battery_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Prose-only diffs keep the gates that read prose

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the
frontmatter (`python-pedro`), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

## Objectives & Success Criteria

- A proven prose-only PR still runs every heavy-battery gate whose declared
  `special_tiers.architectural.scan_scopes` entry matches the diff, through the
  existing #6996 scoped-leg mechanism (FR-001, FR-002, SC-001).
- A prose-only PR that matches no declared scope keeps the battery skipped
  exactly as #4842 ruled (SC-002).
- Non-prose routing is byte-identical to today (FR-003, SC-003).
- A planted removal of the exemption — from the battery `if:` or from the
  selection — turns a pinned test red (FR-004, SC-004).
- Uncertainty still answers the whole leg (NFR-001): no diff base, a git error,
  a selection error.

## Context & Constraints

- Issue: #6999 (P1). Operator ruling 2026-11-01, recorded on the issue: *exempt
  declared scan-scope matches from the subtraction. A prose-only diff still
  skips the battery as a whole, but every gate whose declared `scan_scopes`
  entry matches the diff runs, through the scoped-leg mechanism from #6996.*
- Predecessor: #6994 / PR #6996 added `scan_scopes` declarations and the scoped
  leg. Its `## Deferred` names this exact interaction.
- Mission artifacts: `kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/spec.md`,
  `plan.md` (Design), `contracts/prose-only-scan-scope-exemption.md` (the
  contract you must keep), `research.md`, `quickstart.md`.
- **Do not** touch `scripts/ci/prose_only.py` (content classifier, single
  source), `.github/ci-module-registry.yml` (declarations already exist),
  `.github/ci-shard-timings.json`, or any `tests/architectural/**` gate.
- **Do not** add a CI job, a router group, or a registry row. The battery `if:`
  must name no new `needs.changes.outputs.<group>`.
- No gate may be disabled, skipped, xfailed, deselected or narrowed for a diff
  it declares (C-001). No full heavy suite locally (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Branch Strategy

- **Strategy**: single-branch mission; planning artifacts and code land on the
  mission branch, then one PR to `main`.
- **Planning base branch**: `kitty/mission-prose-only-scan-scope-exemption-01M6BTRX`
- **Merge target branch**: `main` (via the PR; never push `main`)

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first reproduction

- **Purpose**: Prove the defect through the pre-existing entry points before any
  fix (charter ATDD-First; DIRECTIVE_034).
- **Steps**: Run `quickstart.md` §1 in the clone at the mission base. Record the
  command and output in the mission tracer (`spec-kitty agent tracer-append
  --mission prose-only-scan-scope-exemption-01M6BTRX --actor claude --category
  approach --entry "..."`). Expected before the fix:
  `select_battery_gates(["scripts/release/extract_changelog.py"])` returns the
  five declared `scripts/**` scanners, while the real battery `if:` evaluates
  `False` for `changes.arch_scan_scope=true, prose-scan.prose_only=true`.
- **Files**: none changed; evidence only.
- **Notes**: Keep this reproduction as the regression pin in T005/T006 rather
  than a throwaway script.

### Subtask T002 – `select_battery_gates(..., prose_only=...)`

- **Purpose**: The prose verdict is an input to the selection, not something the
  router re-derives.
- **Steps**: In `scripts/ci/gate_selection.py`:
  - Add keyword-only `prose_only: bool = False` to `select_battery_gates`.
  - `mode == "full"` → `None` stays first and unchanged.
  - With `prose_only=True`: return only the heavy-leg gates whose declared scan
    scope matches, computed exactly as today's final comprehension (always-on
    gates excluded). Skip the `selection.unmatched_src` /
    `selection.matched_groups & code_groups` / `battery_code_helpers()` widening
    — prose-only proves no behaviour change. Never return `None`.
  - With `prose_only=False`: today's code path, byte-identical.
  - Extend the docstring: what prose mode means, why it narrows, and that it is
    still fail-safe (full mode / unusable diff → `None`).
- **Files**: `scripts/ci/gate_selection.py`.
- **Notes**: Keep the function pure. No git, no blob reads, no import of
  `prose_only.py`.

### Subtask T003 – CLI flag

- **Purpose**: The workflow can hand the verdict to the step.
- **Steps**: In `scripts/ci/battery_scope.py`:
  - `decide(paths, *, part, mode="pr", prose_only=False, repo=...)` passes
    `prose_only` to `select_battery_gates`.
  - `select` subcommand gains `--prose-only` accepting `true|false`
    (case-insensitive), default `false`; a malformed value must not silently
    mean `true` (fail toward today's behaviour).
  - `main` passes it through; the existing exception → `FULL` fallback stays.
- **Files**: `scripts/ci/battery_scope.py`.
- **Notes**: `--prose-only true` with no base must still answer `mode=full`.

### Subtask T004 – Workflow wiring

- **Purpose**: The battery runs for a prose-only declared-scope match, and the
  selection knows it is prose.
- **Steps**: In `.github/workflows/ci-router.yml`:
  - The `architectural-heavy` `if:` trailing conjunct becomes
    `(needs.prose-scan.outputs.prose_only != 'true' || needs.changes.outputs.arch_scan_scope == 'true')`.
    Keep it the single outer `&&` after the group OR; add no new group.
  - The `Select the battery gates this diff touches (#6994)` step gains
    `PROSE_ONLY: ${{ needs.prose-scan.outputs.prose_only }}` and passes
    `--prose-only "${PROSE_ONLY:-false}"`.
  - Update the explanatory comments at both spots to cite #6999 and the ruling.
- **Files**: `.github/workflows/ci-router.yml`.
- **Notes**: Check `needs:` of the job still includes `prose-scan` (it does).
  Do not reorder unrelated steps.

### Subtask T005 – Prose selection pins

- **Purpose**: Red-first regression pin for the selection half.
- **Steps**: In `tests/ci/test_battery_scope.py` add:
  - a prose-only `scripts/**` diff selects exactly the declared matches, split
    across both legs with empty intersection and a union equal to the selection;
  - a prose-only `src/**` code-group diff selects only declared matches (here:
    none), never `FULL`;
  - a prose-only battery-code-helper touch (`scripts/ci/gate_selection.py`) does
    not widen to `FULL`;
  - `--prose-only true` through `main`/`decide` and the no-base fail-safe;
  - a mutation control: with `prose_only=False` the same `src/**` path answers
    `FULL`, proving the flag is what narrows (same-fixture positive control).
- **Files**: `tests/ci/test_battery_scope.py`.
- **Notes**: Compare against `gate_selection.battery_scan_scopes()` for the
  expected set instead of hardcoding a large list; hardcode only the known
  comment-scanning gates for `scripts/release/**` (both clock bans plus the
  doctrine/retired-subsystem scanners) so the pin names the user-visible value.

### Subtask T006 – Goldens and planted controls

- **Purpose**: Update the #4842 goldens to the ruling and make reversion
  impossible to miss.
- **Steps**:
  - `tests/ci/test_ci_module_wiring.py`
    `test_golden_prose_only_pr_down_routes_matrix_arch_battery_and_code_shards`:
    keep the module-matrix/code-shard/docs assertions; change the battery
    assertion to the two halves — prose-only with `arch_scan_scope=false` stays
    skipped, prose-only with `arch_scan_scope=true` runs — and state the
    2026-11-01 ruling in the docstring.
  - `tests/ci/test_ci_config_battery_routing.py`
    `test_battery_if_keeps_the_prose_only_conjunct_as_the_single_outer_and`:
    assert the trailing conjunct is the exemption
    (`prose_only != 'true' || arch_scan_scope == 'true'`), still a single outer
    `&&`; cite the ruling.
  - Add the planted controls: (a) rewrite a copy of the `if:` back to the old
    single subtraction and assert the prose-only + declared-scope context flips
    to `False`; (b) call `select_battery_gates` with `prose_only=True` on a
    code-group path and assert it is not `None`, and with `prose_only=False`
    and assert it is `None`; (c) drop one declared scanner from the expected set
    and assert the "selected" assertion fails (use a set difference assertion
    shape that fails, e.g. `assert expected <= selected`).
- **Files**: `tests/ci/test_ci_module_wiring.py`,
  `tests/ci/test_ci_config_battery_routing.py`.
- **Notes**: Use `tests.ci._gh_if.eval_gh_if` and `BASE_CONTEXT_ALL_FALSE`, not
  string greps, for the `if:` half.

### Subtask T007 – Targeted verification

- **Purpose**: Prove the change green without a heavy sweep.
- **Steps**: Run and record exact commands/results:
  ```bash
  uv run --frozen python -m pytest tests/ci/test_battery_scope.py tests/ci/test_ci_module_wiring.py tests/ci/test_ci_config_battery_routing.py tests/ci/test_prose_only.py -q
  uv run --frozen python -m pytest tests/architectural/test_battery_scan_scope_routing.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_ci_quality_path_filters.py tests/architectural/test_gate_selection_authority.py -q
  uv run --frozen ruff check scripts/ci/battery_scope.py scripts/ci/gate_selection.py tests/ci/test_battery_scope.py tests/ci/test_ci_module_wiring.py tests/ci/test_ci_config_battery_routing.py
  uv run --frozen ruff format --check --force-exclude scripts/ci/battery_scope.py scripts/ci/gate_selection.py tests/ci/test_battery_scope.py tests/ci/test_ci_module_wiring.py tests/ci/test_ci_config_battery_routing.py
  uv run --frozen mypy --explicit-package-bases scripts/ci/battery_scope.py scripts/ci/gate_selection.py
  ```
  Also run the `quickstart.md` §3 CLI check with `--prose-only true` and with a
  null base.
- **Files**: none changed.
- **Notes**: If a workflow-shape test reds for a reason outside this WP's files,
  report it instead of editing the test.

## Test Strategy

- Red-first: T001's reproduction must be recorded before T002–T004 change
  behaviour, and the same assertions become the T005/T006 pins.
- Unit + golden only; no new architectural gate file, no heavy sweep.
- Mutation controls are part of the test set, never a separate manual step.

## Risks & Mitigations

- **Accidental widening**: pinned by the prose-only-no-scope negative (SC-002)
  and by keeping `mode=full`/`None` first.
- **Golden churn hiding a real red**: evaluate the real `if:` strings with
  `eval_gh_if`; do not weaken the existing code-PR branch of the goldens.
- **Router transcription drift**: no transcription edit here; the #6994 pin
  keeps guarding it.

## Review Guidance

- Confirm `select_battery_gates` with `prose_only=False` is unchanged (diff-read
  the function).
- Confirm the battery `if:` still names exactly the same group set and that
  `HEAVY_BATTERY_NON_SRC_GROUPS` needs no change.
- Confirm no gate/registry/timing file was touched and no gate was skipped.
- Confirm the planted controls actually red when the fix is reverted (run one
  by hand in a scratch copy if in doubt).

## Progress & Status

- Record subtask completion with
  `spec-kitty agent tasks mark-status T001 ... --status done`.
