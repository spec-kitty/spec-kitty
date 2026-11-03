# Work Packages: Repair the #4891 accept pin's positive control fixture

**Inputs**: Design documents from `kitty-specs/issue-6859-accept-pin-fixture-01M6GS08/`
**Prerequisites**: plan.md (required), spec.md (user stories)
**Issue**: [#6859](https://github.com/spec-kitty/spec-kitty/issues/6859)

**Tests**: required, and already red. The failing CLI-level pin exists on `main`
(`test_accept_cli_positive_control_with_lanes_json_and_passing_matrix`, reproduced before any
change: `1 failed, 1 passed`, `IMPLEMENTATION_UNREADABLE`). This Mission repairs the fixture
that test depends on; it adds no product code and no new test.

**Organization**: one work package. The change is a single file's fixture builder plus a
changelog fragment; splitting the fixture repair from its verification would put the red-first
proof and the fix in different review units.

**Prompt Files**: `/tasks/WP01-4891-accept-pin-fixture.md`.

## Path Conventions

- Tests: `tests/…`; changelog fragments: `docs/changelog/unreleased/<pr>.internal.md`
  (see `docs/changelog/unreleased/README.md`). No `src/` path changes.

---

## Work Package WP01: Make the pin's two controls a Mission apart only by `lanes.json` (Priority: P1)

**Goal**: the #4891 pin's positive control is green on `main` because its fixture is an
implemented, owned, independently reviewed Mission — not because any gate was relaxed — and both
controls are built by one helper so they cannot drift apart.
**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -q` reports `2 passed`; removing each fixture part in turn (lane implementation commit, `owned_files`, independent approval) turns the positive control red with the matching evidence code.
**Prompt**: `/tasks/WP01-4891-accept-pin-fixture.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Read the three landing gates and record which ones refuse today's fixture (`wp_evidence.py`, `preflight.py`)
T002 Add the shared `_build_accept_ready_mission` builder: owned files, implemented/reviewed lifecycle, committed clean
T003 Positive control: keep `lanes.json` + passing matrix, add `commit_lane_implementation` for WP01's lane branch
T004 Prove non-vacuity half by half (each of the three fixture parts removed -> the matching evidence code)
T005 Changelog fragment `docs/changelog/unreleased/<pr>.internal.md`; targeted test run and self-review

### Implementation Notes

- **Fix the subject, not the assertion.** `accept`'s refusal of an unreadable evidence window is
  correct, documented, fail-closed behaviour (`src/specify_cli/consolidation/wp_evidence.py`); the
  fixture is the side that is wrong. No assertion, marker or docstring claim of the pin is
  softened, and the test keeps driving the real `accept` CLI.
- Do **not** edit `tests/specify_cli/test_acceptance_regressions.py::_create_test_feature`: ~35
  call sites share it. Call it with `omit_status_events=True` and seed the lifecycle locally.
- The evidence axis reads authored frontmatter only (`_owned_patterns_by_wp`), so `owned_files`
  must be in `tasks/WP01-test.md`, not inferred from `lanes.json`.
- `commit_lane_implementation` requires `lanes.json` to exist first (it reads
  `planning_commit_sha`), which is why the positive control is the only caller.
- Seed the status chain with the status-store helpers (`seed_status_event`, `materialize`); ids
  must stay in the ULID alphabet or the store drops the line.
- Changelog is a **fragment**, not a `CHANGELOG.md` edit: tests-only, so `<pr>.internal.md`.

### Parallel Opportunities

None: one file, one coherent slice.
