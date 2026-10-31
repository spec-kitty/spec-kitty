# Work Packages: mark-status owner authority

**Inputs**: `/kitty-specs/mark-status-owner-authority-01M68JA8/` — spec.md, plan.md, research.md, contracts/mark-status-resolution.md
**Mission type**: software-dev (bug fix, issue #6463)
**Organization**: Two work packages. WP01 owns the code and its tests; WP02 owns the
documentation and changelog surfaces. Subtasks are reference rows recorded with
`spec-kitty agent tasks mark-status`; the reduced event-log snapshot is the sole
completion authority.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks work that can proceed in parallel.
- Subtasks are **reference rows**, not checkboxes.

## Path Conventions

Repository root: `src/specify_cli/`, `tests/specify_cli/`, `docs/`.

---

## Work Package WP01: One ownership authority for mark-status (Priority: P0)

**Goal**: `agent tasks mark-status` resolves a subtask id to exactly one owning WP and
refuses loudly when it cannot — no silent wrong-WP write, no write-path re-derivation.
**Independent Test**: the five new tests in
`tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py` are red on
`main@35318ef51c` and green after the change; `tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py`
stays green unchanged.
**Prompt**: `/tasks/WP01-owner-authority.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-001, C-002

### Included Subtasks

T001 Write the red-first tests: mixed-source ambiguity refused; scoped marks stay scoped; a WP index row cannot claim a WP id; a `WP`-shaped authored subtask needs `--wp`; the emit refuses an unattributable id.
T002 Union the ownership sources in the resolution phase (authored roster ∪ structured `tasks.md` claims) and keep the #5953 refusal messages verbatim.
T003 Scope `WP`-shaped ids: apply the ambiguity/`--wp` rules when a WP authors the id as a subtask, and run the lane-transition rejection before the legacy row resolvers otherwise.
T004 Attribute the completion event only from the resolved owner map; refuse before the first event when an updated id has no owner.
T005 Prove red→green and compatibility: run the two mark-status suites, mypy on the changed module, and record the red output of each new test on the base commit.

### Implementation Notes

- Ownership authority stays `core.subtask_rows.authored_roster_owner_map`; `tasks.md`
  contributes only **structured** rows (`history_wp_ids`). No third derivation.
- Keep the shipped `software-dev` shape byte-identical: its `tasks.md` lists subtasks
  as plain lines, so no structured rows exist and the roster stays the sole source.
- Every new refusal must exit 1 before any event is appended.

### Parallel Opportunities

- T001 (tests) proceeds alone; T002–T004 are sequential within the same file.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A mixed-source mission gains a refusal for an unscoped mark — intended; the message
  names every owner and the exact `--wp` to rerun.
- Emit refusal masking a roster problem — the roster read already fails closed earlier.

---

## Work Package WP02: Document the ownership and refusal contract (Priority: P1)

**Goal**: the changelog and the status-model architecture note state who owns a subtask
id, when the command refuses, and what changed for callers.
**Independent Test**: `docs/changelog/CHANGELOG.md` has one `[Unreleased]` entry under
1,200 characters with the `(#6463)` reference, and
`docs/architecture/status-model.md` documents the ownership resolution and refusal
contract; `uv run python -m scripts.docs.check_docs_freshness --ci` still reports
errors=0.
**Prompt**: `/tasks/WP02-ownership-docs.md`
**Requirement Refs**: C-003, NFR-001

### Included Subtasks

T001 Add the `[Unreleased]` changelog entry: bold impact-first lead, `(#6463)`, before/after, under 1,200 characters.
T002 Document the ownership resolution and refusal contract in `docs/architecture/status-model.md`.
T003 Verify docs freshness (`check_docs_freshness --ci`, errors=0) and that no generated CLI-help surface changed.

### Implementation Notes

- The command docstring and `--wp` help are unchanged, so
  `docs/api/agent-subcommands.md` and the `mark-status.help` golden fixture must not be
  regenerated. If they do change, that is a signal the diff grew beyond intent.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`.

### Parallel Opportunities

- T001 and T002 are independent edits; T003 verifies both.

### Dependencies

- Depends on WP01 (the wording must match the shipped refusals).

### Risks & Mitigations

- Docs churn from a global regenerator on a shared machine — regenerate nothing; only
  run the freshness check.
