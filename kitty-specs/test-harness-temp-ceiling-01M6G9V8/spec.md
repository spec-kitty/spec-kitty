# Mission Specification: Test harness temp ceiling

**Mission Branch**: `issue-7076-test-harness-temp-ceiling`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#7076 — "Test harness: TMPDIR under basetemp, from-scratch child envs, stop= for the ancestor walk" (the deferred harness half of #7056).

## Problem

#7022 taught the test harness to list the run's basetemp and the worker's isolated home in
`GIT_CEILING_DIRECTORIES` from `pytest_configure`, and #7056 moved every root walk in `src/`
onto that same ceiling. The ceiling only governs directories **below** a listed entry, so the
harness still has two holes around it:

1. **`tempfile` escapes the ceiling.** `tempfile.gettempdir()` is the *platform* temp root
   (`/tmp`, or `--basetemp`'s parent), which is not below any listed ceiling. Every directory a
   test makes with `tempfile.TemporaryDirectory()` / `mkdtemp()` (59 test modules do) is
   therefore outside the harness's own hermeticity boundary, and on a shared host whose `/tmp`
   gained a stray `.git` (as this host's did, left by parallel missions) those directories sit
   inside a foreign repository. That is the same class of failure #7022/#7056 fixed for
   `tmp_path`: lock paths resolve into the foreign `.git`, mission-state repair re-anchors on it
   and finds no missions, and "not a repository" probes are never reached.
2. **From-scratch child environments do not inherit the harness at all.** Six places build a
   child environment from an allowlist (or copy it and strip `GIT_*`): they drop
   `GIT_CEILING_DIRECTORIES`, so the child's git and the child's own root walks climb into
   whatever encloses the test's temp tree.

A third item from #7056 was left open as a **decision**: the test-only `stop=` keyword on
`locate_project_root` and `find_repo_root`. Both functions already honour the ceiling, so
`stop=` is a second, parallel boundary mechanism with no production caller.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A stray repository above the temp root cannot capture test temporaries (Priority: P1)

A maintainer runs the suite on a shared host where someone else's `/tmp` (or an agent sandbox's
temp dir) is inside a git work tree. Every temporary directory the suite creates — not just
`tmp_path` — must behave as if it were outside any repository.

**Why this priority**: this is the defect. It is what reddened three separate tests on this
host while CI stayed green, and it is invisible until the host is hostile.

**Independent Test**: install the harness against a basetemp that *is* inside a repository, make
a directory with `tempfile`, and assert the root walks answer "no project" — with the same
fixture proving the walk *would* find that repository when the ceiling is removed.

**Acceptance Scenarios**:

1. **Given** a run whose basetemp sits inside a git work tree, **When** `pytest_configure` has
   run, **Then** `tempfile.gettempdir()` and everything `tempfile` creates are below the run's
   basetemp, and `locate_project_root` on such a directory returns `None`.
2. **Given** the same fixture with the ceiling removed, **When** the walk runs, **Then** it
   resolves the enclosing repository — so the first scenario is not passing vacuously.

---

### User Story 2 - A child built from a scratch environment still knows the ceiling (Priority: P1)

A test that spawns a child with a deliberately minimal environment (upgrade preview processes,
git helpers, the isolated-env shell helper, the offline sdist build, the bake-commit fixture)
must give that child the same discovery boundary the harness holds.

**Why this priority**: an allowlisted environment is the most hermetic thing in the suite and
the only place where the ceiling silently disappears; it is also where a leaked foreign
repository does the most damage (real git commands, real mission state).

**Independent Test**: build each site's environment through its real helper and assert
`GIT_CEILING_DIRECTORIES` (and the harness temp root where the site does not pin its own) is
present and equals the harness value.

**Acceptance Scenarios**:

1. **Given** the harness has a ceiling, **When** each from-scratch child environment is built,
   **Then** the child environment carries it.
2. **Given** a test narrows the ceiling for itself, **When** it builds a child, **Then** the
   child inherits the narrowed value rather than the run-wide one.

---

### User Story 3 - One boundary mechanism, not two (Priority: P2)

A contributor reading `locate_project_root` sees one documented boundary — git's own ceiling —
rather than a keyword argument that only tests pass and that must be kept in sync with it.

**Why this priority**: it removes the drift risk; it is not needed for the P1 fix to work.

**Independent Test**: `inspect.signature` on both walks has no `stop` parameter, and the three
test modules that passed it are green using the per-test ceiling instead.

**Acceptance Scenarios**:

1. **Given** the tests that needed a last-directory boundary, **When** they run after the change,
   **Then** they bound the walk with `GIT_CEILING_DIRECTORIES` and keep their verdicts.
2. **Given** the walks are called with `stop=`, **When** the change is in, **Then** it is a
   `TypeError` — the parameter is gone, not ignored.

### Edge Cases

- The run has no basetemp at all (`config.option.basetemp` is `None`): the temp-root install is a
  no-op and must not crash.
- pytest resolves the given basetemp lazily and **removes and recreates it** at first use: a temp
  root created eagerly in `pytest_configure` is destroyed. The install must therefore also
  re-create it once the basetemp is resolved, before any test body runs.
- A test narrows `TMPDIR` itself or sets `tempfile.tempdir`: `tempfile.tempdir` is a process
  global; the harness sets it once and per-test narrowing remains the test's business.
- `--basetemp` passed explicitly: the run still owns that tree, so the temp root still goes under
  it; the install must not depend on `install_run_basetemp` having claimed the option.
- Windows: `tempfile` reads `TMPDIR` first on every platform, but git and other child tools read
  `TEMP`/`TMP` there, so all three point at the same root.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Temp root under the basetemp | As a maintainer on a shared host, I want `TMPDIR`/`TEMP`/`TMP` pointed at a directory below the run's basetemp and `tempfile`'s cached root reset, so that every temporary the suite makes is below the harness ceiling. | High | Open | [build] | no |
| FR-002 | Temp root survives pytest's basetemp reset | As a maintainer, I want the temp root re-created after pytest removes and recreates the given basetemp, so that `tempfile` never points at a missing directory during a run. | High | Open | [build] | no |
| FR-003 | Ceiling covers the temp root | As a maintainer, I want a `tempfile` directory made under a hostile temp root to resolve to no project, so that a stray repository above the platform temp root cannot capture test temporaries. | High | Open | [ratchet] | no |
| FR-004 | From-scratch children carry the ceiling | As a maintainer, I want each from-scratch (or `GIT_*`-stripped) child environment to carry the harness `GIT_CEILING_DIRECTORIES`, so that a child's git and root walks hold the same boundary as the parent. | High | Open | [ratchet] | no |
| FR-005 | `stop=` leaves the two walks | As a contributor, I want `locate_project_root` and `find_repo_root` to take no test-only boundary argument, so that git's ceiling is the single boundary mechanism. | Medium | Open | [build] | no |
| FR-006 | The three `stop=` callers keep their verdicts | As a maintainer, I want the tests that passed `stop=` to bound the walk with the per-test ceiling instead, so that removing the parameter does not weaken what they prove. | Medium | Open | [ratchet] | yes — paired with FR-005 on the same three modules |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Hermeticity is host-independent | On a host whose platform temp root is inside a git work tree, zero harness-made temp directories resolve into that work tree (proved by a same-fixture positive control). | Reliability | High | Open |
| NFR-002 | No per-test cost | The change adds at most one session-scoped hook and one `mkdir` per process; `pytest_configure` startup grows by under 5 ms and no per-test fixture is added. | Performance | Medium | Open |
| NFR-003 | Portable to Windows | The same mechanism applies on Windows: `TMPDIR` is what `tempfile` reads first there too, and `TEMP`/`TMP` follow it so child tools agree. | Portability | High | Open |
| NFR-004 | No dependency on unmerged work | The change lands on `main` without depending on #7056's walker (PR #7082), which is still open. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Per-test narrowings stay | The per-test `GIT_CEILING_DIRECTORIES` controls (monkeypatch-narrowed) are narrower local controls, not duplicates of the harness entry, and stay (issue item 3). | Technical | High | Open |
| C-002 | `session_start._find_project_root` is out of scope | Its `stop=` stays in this mission: that walk does not read the ceiling, so removing its only bound would make its callers non-hermetic. Named in the PR's Deferred section. | Technical | Medium | Open |
| C-003 | No gate weakened | No test is skipped, xfailed or relaxed to accommodate the change. | Process | High | Open |
| C-004 | Suite cleanup is inherited, not re-invented | Temp artifacts live under the basetemp precisely so the existing per-run wipe/outcome-gated reap (`run_basetemp`) governs them; no second reaper is added. | Technical | Medium | Open |

### Key Entities

- **Harness temp root**: `<basetemp>/tmp`, created per process after pytest has resolved the
  basetemp; the process's `TMPDIR`/`TEMP`/`TMP`.
- **Harness ceiling**: the `GIT_CEILING_DIRECTORIES` value `pytest_configure` installs (run
  basetemp + worker isolated home), and what a child environment must inherit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A test that creates a directory with `tempfile` inside a run whose basetemp sits inside a repository resolves no project root, and the same fixture without the ceiling resolves that repository. — [build] · no-op passable: no
- **SC-002**: `tempfile.gettempdir()` is a path below the run's basetemp for every process the harness configure step touches (controller and xdist worker). — [build] · no-op passable: no
- **SC-003**: All six from-scratch/`GIT_*`-stripping child-environment sites carry the harness ceiling when the harness has one. — [ratchet] · no-op passable: no
- **SC-004**: `inspect.signature(locate_project_root)` and `inspect.signature(find_repo_root)` contain no `stop` parameter, and the three affected test modules are green. — [ratchet] · no-op passable: no
