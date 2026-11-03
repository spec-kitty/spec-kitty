# Work Packages: Subtask completion recipes name their work package

**Inputs**: Design documents from `kitty-specs/subtask-recipe-wp-scoping-01M6G9TW/`
**Prerequisites**: plan.md, spec.md

**Tests**: red-first. WP01 begins by writing the failing shape test for the recipe
renderer; WP02 begins by writing the failing assertion on the emitted refusal and
on the rendered prompt, then makes both pass.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).
Each work package is independently reviewable; WP02 depends on WP01 because it
consumes the renderer, WP03 depends on both because it records what shipped.

> This mission's own WP files deliberately reuse `T001..T00n` per work package —
> the id shape issue #7108 is about. Running `mark-status` without `--wp` on this
> mission must refuse, and the scoped recipes this mission ships are what make it
> pass. That is the dogfood check: if the recipes were still unscoped, driving
> this mission to `for_review` would need `--force`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different file, no shared state).
- Subtasks are reference rows, not checkboxes: completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --wp <WPxx> --status done --mission <slug>`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: The recipe's single home (Priority: P1)

**Goal**: One pure function renders the subtask-completion command, in a module both
`runtime` and `specify_cli.cli` may import, with every option arm pinned.
**Independent Test**: `uv run pytest tests/specify_cli/core/test_subtask_recipe.py -q`
passes, and each rendered arm matches the exact expected command line.
**Prompt**: `/tasks/WP01-recipe-home.md`
**Requirement Refs**: FR-001, FR-003, FR-004, FR-005, NFR-002, C-002, C-003

### Included Subtasks

- T001 Red-first: write `tests/specify_cli/core/test_subtask_recipe.py` asserting the five render arms (plain, with `--mission`, with `--owned-checkout`, multi-id, unknown slug). It must fail with `ModuleNotFoundError` before T002.
- T002 Add `src/specify_cli/core/subtask_recipe.py` with `mark_status_recipe(...)`; pure, `collections.abc`-only imports.
- T003 Pin the option order: `--wp` before `--status`, then `--mission`, then `--owned-checkout`, so the owned-arm assertions in the existing integration test stay a suffix match.

### Implementation Notes

- The module lives under `specify_cli.core` because `tests/architectural/test_layer_rules.py::TestRuntimeBoundary` forbids `runtime` → `specify_cli.cli`; `core` is already in the `runtime` ledger.
- `mission_slug=None` omits `--mission` entirely — no `--mission None` is ever rendered.
- The function takes the WP id as a **required keyword** so a caller cannot forget it.
- No empty-input `ValueError` with a synthetic test: every call site already guards `if subtask_ids` (DIRECTIVE_041).

### Parallel Opportunities

- None: T001→T002→T003 are one file pair.

### Dependencies

- None (root).

### Risks & Mitigations

- A new module can trip a census/allowlist gate: the function is used by three modules immediately, so it is live, not dead; validate with `tests/architectural/dead_symbol` gates before review.
- Importing a new leaf into `tasks_transition_core` must not add I/O: the module imports only `collections.abc`.

---

## Work Package WP02: Every emitter prints the scoped recipe (Priority: P1)

**Goal**: The `move-task` refusal, the implement "WHEN DONE" block and the three
`workflow_executor` runbook recipes all print the scoped command, and the emitted
command provably clears the gate on a mission whose WPs share subtask ids.
**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py tests/next/test_prompt_builder_review_base.py tests/integration/test_prompt_builder_owned_arms.py -q` passes.
**Prompt**: `/tasks/WP02-emitters.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

- T001 Red-first: write `tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py`; it asserts the refusal recipe names `--wp` and fails on unmodified `src`.
- T002 Wire `tasks_transition_core._guard_subtasks` to the renderer using `req.task_id` as the WP and `req.mission_slug` as the mission; change the message only, never the pass/refuse verdict.
- T003 Add the behavioural proof in the same test file: on a two-WP shared-id fixture, execute the emitted command string through the real `mark-status` entry point and assert it exits 0 and records against the named WP (SC-001).
- T004 Wire `runtime/next/prompt_builder._completion_lines` to the renderer, preserving the "no subtasks declared" wording verbatim (FR-006).
- T005 Wire all three `cli/commands/agent/workflow_executor.py` sites to the renderer.
- T006 Update `tests/next/test_prompt_builder_review_base.py` and `tests/integration/test_prompt_builder_owned_arms.py` to assert the scoped string, including both flags on the owned arm.
- T007 Assert the three runbook recipes in the same test file as T001 (SC-002), and that an empty roster emits zero `mark-status` lines (SC-003).

### Implementation Notes

- `_guard_subtasks` is a pure decision function: the renderer import must be module-scope-safe and side-effect free (NFR-001). Do not re-resolve the WP id — `req.task_id` already is it.
- `req.mission_slug` may be `None` for directly-constructed requests; the rendered recipe must still be a valid command.
- Do not touch `tasks.py` / `tasks_mark_status.py` docstrings: the `agent tasks --help` fixtures are byte-frozen (`tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py`). The help already documents `--wp`.
- Do not change `_resolve_task_owners`, `_owners_for_task` or any refusal verdict (C-002, C-003).

### Parallel Opportunities

- T002/T003 (refusal + behavioural proof) and T004/T005/T006 (prompt and runbook) touch disjoint files; T007 lands last because it asserts all four sites.

### Dependencies

- WP01.

### Risks & Mitigations

- Editing one of the three `workflow_executor` sites and missing the others: T007 asserts all three by rendering each entry point.
- Prompt byte-stability tests elsewhere may pin the old string: grep for the old recipe text across `tests/` and update every pin in this WP.
- Suppressing the refusal to make the test pass: forbidden — the test asserts the refusal still fires and only its advice changed.

---

## Work Package WP03: Changelog fragment, docs and mission trail (Priority: P2)

**Goal**: The user-visible change is recorded where maintainers look, and the mission's
issue matrix and tracers are closed truthfully.
**Independent Test**: `uv run --frozen python -m scripts.docs.check_changelog_style` reports
no error on the fragment, and `check_docs_freshness --ci` reports errors=0.
**Prompt**: `/tasks/WP03-changelog-and-trail.md`
**Requirement Refs**: NFR-003, FR-002

### Included Subtasks

- T001 Write `docs/changelog/unreleased/<pr>.fixed.md` in the impact-first fragment shape from `docs/changelog/unreleased/README.md`, with the before/after and the `(#7108)` reference.
- T002 Run `check_changelog_style` and `check_spelling --pass unreleased` against the fragment.
- T003 Append the mission tracers (approach, design-decisions, tooling-friction) with `spec-kitty agent tracer-append`, including the dead-end reproduction and the byte-frozen-help decision.
- T004 Set the `#7108` issue-matrix verdict with `spec-kitty agent issue-verdict` once the work is on the branch.
- T005 Confirm `check_docs_freshness --ci` errors=0 without regenerating the shared CLI reference.

### Implementation Notes

- Use the PR number once the PR exists; before that, the `<issue>-<slug>` form from the README.
- Do not edit `docs/changelog/CHANGELOG.md` — fragments only (since #6988).
- Do not rebuild the whole `docs/api/cli-commands.md`: the installed CLI's global asset cache is shared with other agents on this host. This mission changes no `--help` surface, so nothing there should move.

### Parallel Opportunities

- T001/T002 are independent of T003/T004; T005 runs last.

### Dependencies

- WP01, WP02.

### Risks & Mitigations

- Changelog style rejection: the README's shape is authoritative and the checker runs locally before the PR is opened.
- Claiming a docs change that did not happen: the fragment names only the recipe change, not a help-text change.
