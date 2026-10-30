# Work Packages: Caller-supplied migration actors are not seeds (#6754)

**Inputs**: Design documents from `kitty-specs/migration-actor-cli-spoofing-01M66YYX/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Required. The charter's ATDD-first rule applies: the first commit of WP01 inverts the existing spoof pin test into a refusal test, is watched fail on the base, and lands before the guard.

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). WP01 is the refusal authority plus the surface that motivated it; WP02 closes the other two refusing surfaces; WP03 records the change for users.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: invert the emit spoof pin into a refusal test; pin the builder and the allowed arms | WP01 | |
| T002 | One refusal predicate and one canonical message in `status/models.py`; facade export | WP01 | |
| T003 | `agent status emit --actor` refuses before any write; `--actor` help states the rule | WP01 | |
| T004 | `actor_from_option` fails closed; the two recorded-identity call sites opt in with `recorded=True` | WP01 | |
| T005 | Pin the allowed and unchanged arms: `--agent` values, recorded seeds, the three migration writers | WP01 | |
| T006 | Red-first: refuse a seed-shaped `--actor` on the four orchestrator-api lifecycle verbs | WP02 | |
| T007 | Refuse a seed-shaped `--actor` in all four `orchestrator_api/wp_lifecycle.py` verbs (`USAGE_ERROR`) | WP02 | |
| T008 | Red-first: refuse a seed-shaped hidden `implement --actor` before any allocation | WP02 | [P] |
| T009 | Guard `spec-kitty implement --actor` beside the existing `--mission` no-selector guard | WP02 | |
| T010 | Sweep the blast radius: emit / move-task / mark-status / add-history / orchestrator-api / implement suites | WP02 | |
| T011 | `docs/architecture/status-model.md`: who may write a seed, and the refusal | WP03 | |
| T012 | Refresh the `--actor` help text copies in `docs/api/agent-subcommands.md` | WP03 | [P] |
| T013 | `[Unreleased]` changelog entry with the compatibility consequence | WP03 | |

---

## Work Package WP01: The refusal authority and the emit surface (Priority: P1)

**Goal**: one predicate and one message decide that a caller-supplied identity is seed-shaped, `agent status emit` refuses it before any write, and the shared lenient builder defaults to refusing so a future call site fails closed.
**Independent Test**: `pytest tests/status/test_caller_seed_refusal_6754.py tests/status/test_status_emit_structured_actor_6400.py` — the refusal arms fail on the base and pass after T002–T004; the allowed arms pass throughout.
**Prompt**: `tasks/WP01-refusal-authority-and-emit-surface.md`
**Requirement Refs**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, FR-010, NFR-002, NFR-003, NFR-005, SC-002, SC-003, SC-004

### Included Subtasks

T001 Red-first tests: emit refusal, builder fail-closed, allowed arms (WP01)
T002 Refusal predicate + canonical message + facade export (WP01)
T003 `agent status emit --actor` refusal and help text (WP01)
T004 `actor_from_option` fail-closed and the two `recorded=True` call sites (WP01)
T005 Migration-writer and recorded-seed ratchets (WP01)

### Implementation Notes

- The predicate mirrors `is_migration_actor` exactly (same `MIGRATION_ACTOR_PREFIX`, same `actor_identity_str` projection) and lives beside it in `status/models.py`; do not add a second prefix constant anywhere.
- Refuse, never rewrite: the value is not stripped, escaped or re-parsed into a live-looking actor.
- The guard in `emit` goes before `locate_project_root`, so a refused invocation reads and writes nothing.
- `actor_from_option(..., recorded=True)` is the only way to re-record a seed-shaped identity; the two recorded-identity call sites (`_mt_structured_actor`, `_add_history_actor`) opt in, everything else refuses by default.

### Dependencies

- None.

### Risks & Mitigations

- A refused arm that is not actually refused looks green if the test asserts only the exit code: assert the canonical message **and** that the event log is byte-identical.
- The migration-writer arm must not mock the writer; drive `backfill_wp_status` on a fixture, or assert the row it builds through its own builder function.

---

## Work Package WP02: The other two refusing surfaces (Priority: P1)

**Goal**: the four `orchestrator-api` lifecycle verbs and the hidden `implement --actor` refuse a seed-shaped identity with the same message, before any state change.
**Independent Test**: `pytest tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py tests/specify_cli/cli/commands/test_implement_caller_seed_refusal_6754.py` — red on the base, green after T007/T009.
**Prompt**: `tasks/WP02-orchestrator-api-and-implement-surfaces.md`
**Requirement Refs**: FR-003, FR-004, FR-009, NFR-001, SC-001

### Included Subtasks

T006 Red-first orchestrator-api refusal tests (WP02)
T007 Refuse on the four lifecycle verbs with `USAGE_ERROR` (WP02)
T008 Red-first `implement --actor` refusal test (WP02)
T009 Guard the hidden `implement --actor` before allocation (WP02)
T010 Blast-radius sweep (WP02)

### Implementation Notes

- Reuse the allowlisted `USAGE_ERROR` error code — the outbound contract gate must stay green without an allowlist edit (`src/specify_cli/core/upstream_contract.json`). Precedent: the existing invalid-`--evidence-json` refusal in the same module.
- The refusal must precede the write lock, the worktree allocation and the claim: assert 0 appended events and, for `implement`, that no lane worktree was created.
- `append-history` writes an annotation, not a transition; its refusal is the same message.

### Dependencies

- **Depends on WP01** — it imports the refusal predicate and the canonical message.

### Risks & Mitigations

- The `implement` command allocates a lane worktree early; place the guard beside the existing `--mission` no-selector guard at the top of the body, before `detect_context`.
- Keep the JSON envelope parseable in each command's `--json` mode.

---

## Work Package WP03: Docs and changelog (Priority: P2)

**Goal**: the shipped docs and the changelog say who may write a `migration:` actor, what a caller sees now, and what changed for them.
**Independent Test**: read the three changed documents against a run of the refusal from `quickstart.md`; `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0.
**Prompt**: `tasks/WP03-docs-and-changelog.md`
**Requirement Refs**: FR-011, C-005

### Included Subtasks

T011 `docs/architecture/status-model.md` "The actor" section (WP03)
T012 `docs/api/agent-subcommands.md` help-text copies (WP03)
T013 `[Unreleased]` changelog entry (WP03)

### Implementation Notes

- The changelog entry: bold impact-first lead with `(#6754)`, before/after, under 1,200 characters, and it must name the compatibility consequence and the remedy in one line.
- ADRs are historical records: do not rewrite them. The `2026-10-07-3` review-lane-exit ADR keeps its exemption statement; the new rule is that only migrations can produce such an actor.
- Keep the reference doc's audience: an operator or integrator reading `--help` output and the actor table.

### Dependencies

- **Depends on WP01 and WP02** — the docs describe the final behaviour of all three surfaces.

### Risks & Mitigations

- `docs/api/agent-subcommands.md` is hand-maintained from `--help` output; copy the final help text verbatim so it does not drift.
- Do not restate the Doctrine in the docs; link the architecture page instead.
