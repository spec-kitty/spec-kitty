# Work Packages: Scoped heavy legs intersect the universe pre-step

**Inputs**: Design documents from `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/selected-gates-file.md, quickstart.md

**Organization**: three work packages. WP01 owns the file format (one writer, one parser)
and the plug-in that reads it; WP02 owns the decision, its fail-closed rules and the
workflow wiring; WP03 owns the reference page and the changelog (planning artifact).

**Prompt Files**: `tasks/WP01-*.md`, `tasks/WP02-*.md`, `tasks/WP03-*.md`.

## Subtask Index

| Subtask | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | Move the selected-gates write/parse pair into `battery_scope` | WP01 | no |
| T002 | Point the plug-in's `read_gates_file` at that parser, contract unchanged | WP01 | no |
| T003 | Round-trip tests: writer, both readers, blanks and duplicates | WP01 | yes |
| T004 | Red-first decision tests through the real CLI entry point | WP02 | no |
| T005 | Implement `--gates-file` and the intersection, fail closed | WP02 | no |
| T006 | Wire the leg's gates file into the `select` step of `ci-router.yml` | WP02 | no |
| T007 | Extend the workflow-shape test and its mutation cases | WP02 | yes |
| T008 | Rewrite the reference page's stored-universe section | WP03 | no |
| T009 | `[Unreleased]` changelog entry citing (#7001) | WP03 | no |

---

## Work Package WP01: One parser for the selected-gates file (Priority: P1)

**Goal**: The selected-gates file has exactly one writer and one parser, and the battery
plug-in keeps its documented `SK_BATTERY_GATES_FILE` contract while reading through it.
**Independent Test**: A round-trip test writes a file through the CI writer and asserts the
plug-in's `read_gates_file` and `battery_scope.read_selected_gates` resolve the same set,
blank lines and duplicates included; an unset variable still means the whole part.
**Prompt**: `/tasks/WP01-one-parser.md`
**Requirement Refs**: FR-005, C-001

### Included Subtasks

T001 Move the selected-gates write/parse pair into `battery_scope` (WP01)
T002 Point the plug-in's `read_gates_file` at that parser (WP01)
T003 Round-trip tests for the writer and both readers (WP01)

### Implementation Notes

- `scripts/ci/battery_scope.py` already writes the file inside `output_lines`; factor that
  into `write_selected_gates(gates, out)` and add `read_selected_gates(named)` that raises
  `FileNotFoundError` for a missing path. Both stay pure (no globals, no env reads).
- `scripts/ci/battery_partition_plugin.read_gates_file(env)` keeps its signature and its
  two documented outcomes (unset/empty → `None`, missing named file → `pytest.UsageError`);
  only its parsing body moves.
- `__all__` in both modules stays accurate (repo convention, C-007).

### Parallel Opportunities

- T003's tests can be written before T001/T002 land (they fail first) and cover both readers.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A second parser appearing later: the round-trip test names both readers on one fixture,
  so a divergence reds `tests/ci/test_battery_scope.py`.

---

## Work Package WP02: The decision answers for the leg's selected gates (Priority: P1)

**Goal**: `collect_universe_prestep consumers` intersects its answer with the leg's selected
gates file, fails closed on an unreadable file, and `ci-router.yml` passes the file.
**Independent Test**: On `main`'s own fixture — a gates file naming only non-consumer gates —
the CLI answers `false`; adding a consumer gate flips it to `true`; removing the file
restores today's whole-part answer; a missing file exits 1 with nothing on stdout.
**Prompt**: `/tasks/WP02-decision-intersection.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-006, NFR-001, NFR-002, NFR-003, C-002, C-003

### Included Subtasks

T004 Red-first decision tests through the real CLI entry point (WP02)
T005 Implement `--gates-file` and the intersection, fail closed (WP02)
T006 Wire the leg's gates file into the `select` step of `ci-router.yml` (WP02)
T007 Extend the workflow-shape test and its mutation cases (WP02)

### Implementation Notes

- The new option defaults to `$SK_BATTERY_GATES_FILE` (the variable the plug-in reads), so a
  local reproduction needs one variable; CI passes `--gates-file` explicitly.
- Effective scope = `battery_part_files(part) ∩ read_selected_gates(file)`; the answer is
  `bool(effective & universe_consumers())`. No gates file → the existing whole-part answer.
- stderr gets one explanatory line (how many of the part's files the leg selected); stdout
  stays exactly `true`/`false`, because the workflow parses it with a `case`.
- The workflow's `select` step keeps `shell: bash`, keeps no `||`, keeps always running, and
  keeps writing `universe=` to `$GITHUB_OUTPUT` (C-003, and the shape test pins each).

### Parallel Opportunities

- T007 (the shape test and its mutation table) can be prepared alongside T005/T006.

### Dependencies

- WP01 (the parser this decision calls).

### Risks & Mitigations

- A silently narrowed leg whose selected gate does need the universe: FR-002's test adds a
  real consumer gate to the same fixture and asserts `true`; `check` still catches a stray
  self-collection if the wiring is ever wrong.
- A gates file path that is empty in a *whole* run: `gates_file=` empty means "no file", which
  must keep the whole-part answer (FR-003) — tested explicitly.

---

## Work Package WP03: Document the saving and the remaining wins (Priority: P2)

**Goal**: The reference page and the changelog state what a scoped leg now skips, with the
measured cost and the further cheap wins the issue asks to note.
**Independent Test**: `docs/development/reference/ci-gate-mechanics.md` documents the
`--gates-file` input and its fail-closed rule, and the changelog's `[Unreleased]` section
carries an entry leading with the impact and citing (#7001).
**Prompt**: `/tasks/WP03-docs-and-changelog.md`
**Requirement Refs**: FR-007

### Included Subtasks

T008 Rewrite the reference page's stored-universe section (WP03)
T009 `[Unreleased]` changelog entry citing (#7001) (WP03)

### Implementation Notes

- Correct the stale sentence that says leg 2/2 holds no collecting test; both legs hold one
  today (the partition moved with the timings).
- State the measurement with its caveat (development host, 20 concurrent agents; the
  published CI range is 89–233 s for a first collection) and keep the entry under 1,200
  characters.
- Note the further cheap wins as *notes*, not changes: the store cache is keyed by
  `universe-<key>-<commit>`, so the second leg of the same commit restores instead of
  collecting; checkout and `uv sync --frozen --all-extras` still run for a scoped leg.

### Dependencies

- WP02 (the behaviour and the numbers it produces).

### Risks & Mitigations

- Documentation drift: run `uv run python -m scripts.docs.check_docs_freshness --ci` and the
  legacy-terminology gate after the edit.
