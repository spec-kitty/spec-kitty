# Tasks: Close stale WP lifecycle records

**Mission**: `close-stale-lifecycle-records-01M72B89` · **Issue**: #7346 · **Lands on**: `feat/7346-close-stale-lifecycle-records`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/doctor-ops-lifecycle-sweep.md](contracts/doctor-ops-lifecycle-sweep.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing tests: the abandoned phase round-trips and counts as a completion | WP01 | |
| T002 | Add `abandoned` to the lifecycle record contract (`record.py`) | WP01 | |
| T003 | One completion predicate and one unpaired-tail helper (`lifecycle.py`) | WP01 | |
| T004 | `write_abandoned_completion` through the locked lifecycle append | WP01 | |
| T005 | Amend ADR 2026-11-01-2 and the lifecycle module docstring | WP01 | [P] |
| T006 | Failing tests: the lifecycle sweep, its commit, its JSON and exit code | WP02 | |
| T007 | Generalize the #6410 commit-or-skip rules to a record-kind pattern | WP02 | |
| T008 | Extract the shared trail commit helper; the executor delegates to it | WP02 | |
| T009 | `close_stale_lifecycle_records` and `SweepReport.lifecycle_records` | WP02 | |
| T010 | Wire the sweep into `doctor ops --close-stale`: output, exit code, help | WP02 | |
| T011 | Docs: ops-vs-missions, trail model, CLI reference, changelog fragment | WP02 | [P] |

---

## WP01 — The abandoned lifecycle phase (Priority: P1)

**Goal**: a lifecycle record can say it was closed by the doctor sweep (`abandoned`), and every pairing reader counts it as a completion.
**Independent test**: an `abandoned` record written for an orphaned `started` record makes the group non-orphaned, raises the pairing rate, and is excluded from `find_latest_unpaired_started`.
**Prompt**: [tasks/WP01-abandoned-lifecycle-phase.md](tasks/WP01-abandoned-lifecycle-phase.md)
**Requirements**: FR-001, FR-002, FR-005, NFR-001, C-002, C-004

T001 Failing tests: the abandoned phase round-trips and counts as a completion (WP01)
T002 Add `abandoned` to the lifecycle record contract (`record.py`) (WP01)
T003 One completion predicate and one unpaired-tail helper (`lifecycle.py`) (WP01)
T004 `write_abandoned_completion` through the locked lifecycle append (WP01)
T005 Amend ADR 2026-11-01-2 and the lifecycle module docstring (WP01)

**Implementation sketch**: red tests first (T001), then the contract value (T002), the shared predicate and tail helper (T003), the writer (T004), the ADR (T005).
**Dependencies**: none.
**Risks**: a reader that hard-codes `("completed", "failed")` would keep reporting a closed orphan; T003 removes every such copy in `src/`. An older CLI skips `abandoned` records (accepted by the operator).

---

## WP02 — The lifecycle sweep in `doctor ops --close-stale` (Priority: P1)

**Goal**: `doctor ops --close-stale` closes stale orphaned lifecycle records in every checkout, commits the closures like the Op sweep, and reports them.
**Independent test**: seed stale and fresh orphans (one in a linked worktree), run the sweep, and check the closures, the commit, the JSON `lifecycle_records` entries, the exit code, and byte-identical Mission files.
**Prompt**: [tasks/WP02-lifecycle-sweep.md](tasks/WP02-lifecycle-sweep.md)
**Requirements**: FR-003, FR-004, FR-006, FR-007, FR-008, FR-009, FR-010, NFR-002, NFR-003, C-001, C-003, C-005

T006 Failing tests: the lifecycle sweep, its commit, its JSON and exit code (WP02)
T007 Generalize the #6410 commit-or-skip rules to a record-kind pattern (WP02)
T008 Extract the shared trail commit helper; the executor delegates to it (WP02)
T009 `close_stale_lifecycle_records` and `SweepReport.lifecycle_records` (WP02)
T010 Wire the sweep into `doctor ops --close-stale`: output, exit code, help (WP02)
T011 Docs: ops-vs-missions, trail model, CLI reference, changelog fragment (WP02)

**Implementation sketch**: red tests (T006); commit policy then commit helper (T007, T008) so the sweep has its commit seam; the sweep (T009); the CLI (T010); docs (T011).
**Dependencies**: WP01.
**Risks**: `close_stale_ops` (complexity 11) and `doctor.py` are hot: add functions, do not grow existing ones. The sweep JSON is frozen except for the additive key. The executor refactor must keep every Op-commit test green.
