# Work Packages: Decisions lock keyed on the event log (#6765)

**Inputs**: Design documents from `kitty-specs/decisions-lock-log-anchor-01M67JK0/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (D-1..D-6), data-model.md, quickstart.md

**Tests**: Yes — this is a defect mission. FR-001/FR-002 are proven red-first through the
pre-existing entry point (`open_decision`); FR-003/FR-004 are ratchets.

**Organization**: Two work packages. WP01 is the code change and its tests (one surface,
one owner). WP02 is the user-facing record (changelog) and is a `planning_artifact` WP so
it never mixes ownership kinds with the code WP.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/` at the repository root.

---

## Work Package WP01: Anchor-keyed decisions lock on the write path (Priority: P1)

**Goal**: Every Decision Moment write holds a lock keyed on the event log it appends to,
in addition to the existing ledger-dir sidecar, in one global order.
**Independent Test**: two checkouts whose decision writes share one `status.events.jsonl`
and have different `decisions/` ledger dirs never overlap in the open critical section;
two distinct logs still yield two distinct locks; `git status --porcelain` stays empty.
**Prompt**: `/tasks/WP01-anchor-keyed-decisions-lock.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Survey the touched surfaces and record the no-enabler campsite conclusion (service.py, kernel/event_log_append.py, the existing decision suites)
T002 Write the failing-first test module `tests/specify_cli/decisions/test_decisions_lock_log_anchor.py` through `open_decision`; run it and commit RED
T003 Add the log-anchor lock path helper and the two-lock context manager in `src/specify_cli/decisions/service.py`
T004 Wire `open_decision` and `_terminal_command` to the two-lock context manager with the pre-resolved `events_path`
T005 Pin the keying invariants: shared anchor → one lock; distinct anchors → distinct locks; non-git sibling fallback; `dry_run` takes nothing
T006 Run the targeted decision suites and the new module; record commands and results
T007 Self-review the diff against the spec/plan and record the outcome

### Implementation Notes

- Reuse `kernel.event_log_append.event_log_lock_path`; do not derive a second digest or
  lock-placement scheme (C-003).
- Take the anchor lock **first**, then the existing sidecar, both through
  `_decisions_lock`, so the timeout/refusal surface is unchanged (C-001, NFR-003).
- Leave `_decisions_lock_path`, `_LOCK_FILENAME`, `_ensure_runtime_lock_ignore`,
  `_decisions_doctor`, `decision.repair-runtime-lock` and `next_cmd` untouched (C-002).
- Do not change `emit.py`.

### Parallel Opportunities

- None: one surface, one owner.

### Dependencies

- None.

### Risks & Mitigations

- A bounded wait sneaking onto the open path (NFR-001) → the open keeps
  `_OPEN_LOCK_WAIT_S = None` for **both** takes; the terminal verbs pass their existing bound.
- A vacuous test that only compares lock paths for identical ledger dirs → drive the real
  entry point and observe overlap (research D-3).

---

## Work Package WP02: Record the change for users and reviewers (Priority: P2)

**Goal**: A user-facing `[Unreleased]` changelog entry that states the new lock identity,
what it fixes, and that the ledger-dir lock and its machinery are unchanged.
**Independent Test**: the changelog entry exists under `[Unreleased]`, leads with the
impact, cites `(#6765)`, carries before/after, and stays under 1,200 characters; the docs
freshness check the repo runs in CI is unaffected.
**Prompt**: `/tasks/WP02-record-the-change.md`
**Requirement Refs**: NFR-003, C-001, C-002, SC-004

### Included Subtasks

T008 Write the `[Unreleased]` changelog entry for the decisions lock log anchor
T009 Verify the entry length/shape and that no docs reference needs regenerating

### Implementation Notes

- `docs/changelog/CHANGELOG.md` only (root `CHANGELOG.md` is a symlink to it).
- Research the entry from the other entries' shape in that file; do not invent a new
  section or heading.
- Describe keying only. Never describe a timeout/refusal change — that is #6841.

### Parallel Opportunities

- T008/T009 can be drafted while WP01 is in review, but land after WP01's behaviour is fixed.

### Dependencies

- Depends on WP01 (the entry must describe the behaviour that landed).

### Risks & Mitigations

- Overlapping the sibling PR #6841's changelog neighbourhood → describe keying only.
