# Mission Specification: One ceiling-aware ancestor walker

**Mission Branch**: `issue-7056-ceiling-aware-ancestor-walk`
**Created**: 2026-11-02
**Status**: Draft
**Input**: User description: "Issue #7056 — One ceiling-aware ancestor walker: the remaining root walks ignore GIT_CEILING_DIRECTORIES (follow-up to #7022)"

## Context and grounding

#7022 landed as PR #7058 (merged). It made the test harness list its basetemp and
isolated home in `GIT_CEILING_DIRECTORIES`, and taught three product walks to honour
that ceiling: `specify_cli.core.paths.locate_project_root`,
`specify_cli.core.paths.resolve_canonical_root` and the plain-`.git` fallback of
`specify_cli.task_utils.support.find_repo_root`. Its adversarial review found that
every *other* ancestor walk in the tree still climbs straight past the ceiling, and
deferred them to this issue.

Reproduced on current `main` before this mission was opened: with
`GIT_CEILING_DIRECTORIES=<tmp root>` and an ambient `.git` in `<tmp root>/outer`,
`_resolve_invocation(<tmp root>/outer/work)` returns `<tmp root>/outer`,
`mission_metadata._has_no_git_anchor(<tmp root>/outer/work)` returns `False` and
`bootstrap.env_file._find_repo_root(<tmp root>/outer/work)` returns
`<tmp root>/outer` — none of them may cross the ceiling.

Terms, as used in this mission:

- **root walk** — iterating a starting directory and its ancestors looking for a
  repository/project marker (`.git`, `.kittify`, `pyproject.toml`, `kitty-specs`) and
  returning the first directory that satisfies it. The walk starts at some `cwd` or
  caller-supplied directory and, without a ceiling, ends at the filesystem root.
- **ceiling** — an entry in `GIT_CEILING_DIRECTORIES`: a directory the walk may still
  examine, above which it must never continue. This is the mechanism #7022 uses to
  keep a hermetic temp tree from resolving into whatever repository happens to
  enclose it on the host.
- **hand-rolled root walk** — an inline `[p, *p.parents]` / `(p, *p.parents)` /
  `[p] + list(p.parents)` loop written at the call site instead of going through the
  shared primitive.

Issue item 2 (exact git ceiling semantics) is decided here as a **contract**, not a
behaviour change: the primitive keeps the shipped, looser reading (a ceiling
directory is itself examined and the walk stops after it) and pins it with tests,
because matching git exactly would change `resolve_canonical_root`'s shipped
behaviour for every consumer. Issue items 3 and 4 are test-harness hygiene with a
much wider blast radius than this defect; what is safe is done here, the rest is
named in the PR's `## Deferred` section with a follow-up issue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every root walk stops at the ceiling (Priority: P1)

As an operator running the CLI or its test suite inside a directory that some other
repository encloses, I want every repo/project root discovery to stop at
`GIT_CEILING_DIRECTORIES`, so that a hermetic tree is never resolved into a foreign
checkout just because that checkout happens to sit above it.

**Why this priority**: this is the defect. Every walk that ignores the ceiling is a
place where a hermetic run silently reads or writes another repository's state. The
eleven walks named in #7056 each make a different decision (checkout identity,
mission metadata, legacy bookkeeping, gitignore control paths, env-file tiers,
ledger posture, charter lint, next-run planning, catalog diagnosis), so each is a
separate leak.

**Independent Test**: build a temp tree with an ambient `.git`/`.kittify` above it,
list the temp root in `GIT_CEILING_DIRECTORIES`, and call each walk's entry point
from a directory below the ceiling. Every call must behave as if the ambient
markers do not exist — the same verdict it reaches with no ambient repo at all.

**Acceptance Scenarios**:

1. **Given** ambient `.git` above the ceiling, **When** `locate_project_root`,
   `resolve_canonical_root`, `find_repo_root`, `get_status_read_root`,
   `is_worktree_context`, `checkout_identity.resolve_checkout_identity`,
   `mission_metadata._has_no_git_anchor`, `legacy_charter_gate.find_checkout_root`,
   `coordination.legacy_resolution._legacy_worktree_and_branch`,
   `gitignore_manager._has_git_control_path` or `bootstrap.env_file._find_repo_root`
   runs below the ceiling, **Then** the ambient repo above the ceiling is never
   returned.
2. **Given** ambient `.kittify` above the ceiling, **When**
   `ledger_posture._walk_up_to_kittify_marker`, `context.middleware._find_repo_root`,
   `charter_runtime.lint.checks.org_layer._find_repo_root_from_drg`,
   `runtime.next._internal_runtime.planner._infer_project_root` or
   `charter.activation.context_renderers.catalog_diagnosis`'s project-layer walk
   runs below the ceiling, **Then** the ambient project above the ceiling is never
   returned.
3. **Given** a marker *below* the ceiling (a repository the test itself created in
   its own tree), **When** any of those walks runs, **Then** it is still found: the
   ceiling bounds discovery, it does not blind it.

---

### User Story 2 - One primitive, one reading of the environment (Priority: P1)

As a maintainer, I want a single ceiling-aware ancestor-walk primitive at the
`kernel` floor, so that `specify_cli`, `charter` and `runtime` share one
implementation and one reading of `GIT_CEILING_DIRECTORIES` instead of eleven
copies that drift.

**Why this priority**: the eleven defects in Story 1 all exist because each walk
re-implemented the same loop. Fixing them one by one without a shared primitive
leaves the twelfth to be written next month.

**Independent Test**: the primitive is importable from `kernel`; every migrated walk
calls it; `specify_cli.core.paths.git_ceiling_dirs` still exists as the public name
and delegates to the primitive's single reading. A test pins that the ceiling is
read per call (a monkeypatched environment takes effect on the next call).

**Acceptance Scenarios**:

1. **Given** a fresh import of `kernel.ancestor_walk`, **When** a caller sets
   `GIT_CEILING_DIRECTORIES` between two calls, **Then** the second call honours the
   new value (no import-time or module-level caching).
2. **Given** `specify_cli.core.paths.git_ceiling_dirs`, **When** it is called, **Then**
   it returns exactly what the kernel primitive reads (the same frozenset of resolved
   absolute entries, relative entries ignored).
3. **Given** a walk started at a ceiling directory itself, **When** it runs, **Then**
   that directory is examined and the walk stops after it (the documented contract
   from item 2), and a test pins this.

---

### User Story 3 - A gate keeps the next walk honest (Priority: P2)

As a reviewer, I want an architectural gate that rejects a new hand-rolled
`[p, *p.parents]` ancestor walk outside the primitive, so that the next contributor
cannot reintroduce the defect that #7022 and #7056 are about.

**Why this priority**: Story 1 is a one-off repair; Story 3 is what keeps it
repaired. It ranks below the repair only because a wrong gate is worse than no gate,
so it must land with a census that is honest about the walks it exempts.

**Independent Test**: run the gate over `src/`: it reports zero violations for the
migrated corpus, flags a synthetic hand-rolled walk the test injects, and every
allowed exception names the file and function with a stated reason.

**Acceptance Scenarios**:

1. **Given** the migrated tree, **When** the gate scans `src/`, **Then** it reports
   no unlisted hand-rolled ancestor walk.
2. **Given** a source file containing `for parent in [start, *start.parents]:`, **When**
   the gate scans it, **Then** it reports a violation naming file and line.
3. **Given** an exempted file/function that has since been migrated or deleted,
   **When** the gate runs, **Then** it fails and asks for the exemption to be removed
   (shrink-only allowlist).

---

### User Story 4 - The test harness no longer needs its local patches (Priority: P3)

As a test author, I want the harness's redundant hermeticity fixtures to give way to
the ceiling, so that there is one mechanism to learn instead of three overlapping
ones.

**Why this priority**: it is cleanup, not correctness, and it changes tests rather
than product code. Only the provably redundant piece is in scope; removing the
`stop=` parameter or moving `TMPDIR` under basetemp changes dozens of test files and
belongs in its own mission.

**Independent Test**: remove the redundant fixture; the tests it protected still pass
because the harness ceiling covers the same tree, and a control test shows the
protection is real (a walk below the ceiling does not see an ambient repo).

**Acceptance Scenarios**:

1. **Given** `tests/unit/workspace/test_root_resolver.py`'s
   `no_git_ancestry_inside_tmp_path` fixture, **When** it is removed, **Then** the
   file's tests still pass and the ambient-repo protection still comes from the
   harness ceiling.

### Edge Cases

- `GIT_CEILING_DIRECTORIES` unset or empty → walks behave exactly as today (all the
  way to the filesystem root).
- Relative ceiling entries → ignored, as git ignores them.
- A ceiling entry that is not an ancestor of the start path → no effect on that walk.
- Start path is the ceiling itself → examined, then the walk stops after it.
- Several ceiling entries, one an ancestor of another → the nearest ancestor bounds.
- A symlinked temp root (`/tmp` on macOS) → ceilings are resolved, so resolved
  candidates still compare equal.
- Worktree pointer files (`.git` *file*): the ceiling bounds the walk that looks for
  the pointer, not the pointer's own resolution to the primary checkout.
- Walks that start from an already-resolved canonical root (below every ceiling) are
  unaffected.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Kernel ancestor-walk primitive | As a maintainer, I want one primitive in `kernel` that yields a start directory and its ancestors and never continues above a `GIT_CEILING_DIRECTORIES` entry, so every layer shares one walk. | High | Open | [build] | no — a no-op leaves the eleven walks climbing past the ceiling |
| FR-002 | Single ceiling reading | As a maintainer, I want one function that reads and resolves the ceiling entries, with `specify_cli.core.paths.git_ceiling_dirs` delegating to it, so relative/absolute handling is decided once. | High | Open | [build] | no |
| FR-003 | `.git` walks honour the ceiling | As an operator below a ceiling, I want the `.git`/`.kittify` root walks of `locate_project_root`, `resolve_canonical_root`, `get_status_read_root`, `is_worktree_context`, `task_utils.support.find_repo_root`, `checkout_identity`, `mission_metadata`, `legacy_charter_gate`, `coordination.legacy_resolution`, `gitignore_manager` and `bootstrap.env_file` to stop at the ceiling, so an enclosing repository is never adopted. | High | Open | [build] | no |
| FR-004 | `.kittify`-only walks honour the ceiling | As an operator below a ceiling, I want the marker-only walks of `ledger_posture`, `context.middleware`, `charter_runtime.lint.org_layer`, `runtime.next.planner` and `charter.activation.catalog_diagnosis` to stop at the ceiling. | High | Open | [build] | no |
| FR-005 | Other repo-root walks honour the ceiling | As a maintainer, I want the remaining repo-root walks (`charter.activation.neutrality.lint`, `cli.commands.regen`) to use the primitive, so the "one walker" claim is true of the census, not just of the issue's list. | Medium | Open | [build] | yes — these are secondary walks; the primaries are FR-003/FR-004 |
| FR-006 | Ceiling contract pinned by tests | As a reviewer, I want the primitive's ceiling contract (ceiling examined, stop after it, relative entries ignored, resolved comparison, per-call env read) pinned by tests, so item 2 of the issue is a decision with evidence rather than an accident. | High | Open | [ratchet] | no |
| FR-007 | Architectural gate | As a reviewer, I want an architectural test that rejects hand-rolled `[p, *p.parents]`-shape ancestor walks under `src/` outside the primitive, with a shrink-only exemption list, so the defect cannot be reintroduced. | High | Open | [ratchet] | no |
| FR-008 | Exemption census is honest | As a maintainer, I want every exempted walk to name its file, function and why it is not a root walk, and the gate to fail when an exemption goes stale. | Medium | Open | [ratchet] | no |
| FR-009 | Redundant hermeticity fixture removed | As a test author, I want `no_git_ancestry_inside_tmp_path` removed when the harness ceiling already gives the same protection, so there is one mechanism, not two. | Low | Open | [build] | yes — the protection exists either way |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Floor-only dependencies | `kernel.ancestor_walk` imports only the standard library and `kernel` modules: no `charter`, `runtime`, `mission_runtime` or `specify_cli` import, enforced by the existing layer-rule gate. | Maintainability | High | Open |
| NFR-002 | No caching of the environment | The ceiling is read on every call; a run that sets the variable between calls sees the new value (no `lru_cache`, no module-level constant). | Correctness | High | Open |
| NFR-003 | Walk cost | The primitive adds at most one `Path.resolve()` per call and one environment read; no filesystem probe beyond what the caller's predicate already does. | Performance | Medium | Open |
| NFR-004 | Zero behaviour change without a ceiling | With `GIT_CEILING_DIRECTORIES` unset, every migrated walk returns exactly what it returned before this mission; the existing unit suites for each walker stay green. | Compatibility | High | Open |
| NFR-005 | Changed-line coverage | CI's diff-cover gate requires at least 90 % coverage on changed lines; every new branch of the primitive and the gate is covered. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No upward import | The primitive lives at the `kernel` floor because `charter` and `runtime` need it and must not import `specify_cli` (`docs/architecture/00_landscape/README.md`, `tests/architectural/test_layer_rules.py`). | Technical | High | Open |
| C-002 | Shipped ceiling semantics unchanged | Item 2 of the issue is decided as "keep the shipped reading and pin it", not "match git exactly": changing `resolve_canonical_root`'s semantics needs its own decision and mission. | Technical | High | Open |
| C-003 | Public name preserved | `specify_cli.core.paths.git_ceiling_dirs` stays importable (it is the name #7022 shipped and tests reference it); it delegates rather than disappears. | Technical | Medium | Open |
| C-004 | No xfail, no skip, no weakened gate | A gate that fails for a reason outside this change is reported, not disabled. | Process | High | Open |
| C-005 | Test-harness items 3/4 scoped out | Removing the `stop=` parameter or moving `TMPDIR` under basetemp touches dozens of test files and is deferred to a follow-up issue named in the PR. | Process | Medium | Open |

### Key Entities

- **Ceiling set**: the resolved absolute directories read from
  `GIT_CEILING_DIRECTORIES`; the boundary of every root walk.
- **Ancestor sequence**: the start directory followed by each parent up to and
  including the ceiling directory that bounds the walk (or the filesystem root when
  unbounded).
- **Walk predicate**: each caller's own marker test (`.git` directory with `HEAD`,
  worktree pointer, `.kittify` directory, `pyproject.toml`); unchanged by this
  mission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All eleven root walks named in #7056, plus `get_status_read_root`,
  `is_worktree_context`, `charter.activation.neutrality.lint` and `cli.commands.regen`,
  return the same verdict with an ambient repo above the ceiling as they do with no
  ambient repo at all — proven by one test per walk. — [build] · no-op passable: no
- **SC-002**: The architectural gate reports zero unlisted hand-rolled ancestor walks
  under `src/`, and flags a synthetic positive control. — [ratchet] · no-op passable: no
- **SC-003**: Every migrated walker's existing unit suite is green with the ceiling
  unset, i.e. zero behaviour change on a machine whose temp root is not inside a
  repository. — [build] · no-op passable: no
- **SC-004**: One primitive is the only place a root walk is written: the census in
  the gate's allowlist shrinks to non-root walks only, each with a stated reason. — [ratchet] · no-op passable: no
