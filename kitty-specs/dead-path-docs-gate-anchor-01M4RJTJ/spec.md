# Mission Specification: Anchor Gate D's dead-path docs regex

**Mission Branch**: `issue-6096-dead-path-gate-anchor`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #6096 — "Dead-path docs gate (Gate D) over-matches: unanchored regex treats any `…/src/charter/offering/…` path as a top-level `src/` reference"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A nested path tail no longer trips the dead-path docs gate (Priority: P1)

A maintainer writes live documentation under `docs/` that legitimately names a
longer path whose tail happens to be `…/src/charter/offering/<kind>/built-in`
(for example a `packs/internal/x/src/charter/offering/foo/built-in` path, an
absolute CI path, or a GitHub blob URL). The architectural gate that forbids
live docs from pointing at the **retired top-level** `src/charter/offering/…`
home must not flag that line, because the doc never named the top-level home.

**Why this priority**: This is the defect #6096 reports — a false-positive /
precision defect in an architectural gate. Without the fix the gate can red CI
on a correct doc, and its guard is imprecise.

**Independent Test**: Run Gate D's matcher against a synthetic `docs/` tree
containing a line where the retired shape is the tail of a longer path; assert
the line is NOT reported, while a genuine top-level reference on the same
fixture still is.

**Acceptance Scenarios**:

1. **Given** a live doc line `packs/internal/x/src/charter/offering/foo/built-in`, **When** Gate D runs, **Then** the line is not reported as a dead top-level reference.
2. **Given** a live doc line `src/charter/offering/foo/built-in` (a genuine top-level reference), **When** Gate D runs, **Then** the line is still reported.

---

### User Story 2 - The gate still catches a genuinely retired top-level reference (Priority: P1)

A maintainer accidentally leaves a live doc pointing at the retired top-level
`src/charter/offering/<kind>/built-in` home (or a `src/charter/offering/*.graph.yaml`
fragment home). Gate D must still red, exactly as before, so the guard keeps its
reach. Tightening the left boundary must not weaken what the gate forbids.

**Why this priority**: A gate change that silences the over-match must not
silence the real defect it exists to catch — the non-vacuity invariant
(Standing Order 5).

**Independent Test**: Plant a genuine top-level reference in a synthetic `docs/`
tree and assert Gate D reports it; separately, revert the left-boundary anchor
and confirm the new regression test goes RED (self-mutation proof).

**Acceptance Scenarios**:

1. **Given** a planted genuine top-level `src/charter/offering/<kind>/built-in` reference, **When** Gate D runs, **Then** it is reported (exit "matches found").
2. **Given** the left-boundary anchor is removed, **When** the regression test runs, **Then** it fails (the over-match returns).

---

### Edge Cases

- A genuine top-level reference at **start of line**, or preceded by a space,
  quote, backtick, or a markdown-link `(`, must still be caught (the left
  boundary admits a real path start).
- A reference preceded by `/`, a word character, `.`, or `-` (i.e. the tail of a
  longer path) must be rejected — per #6096 the general `src/` literal gate
  (`test_no_dead_src_path_literals.py`) owns blob-URL / nested-literal coverage,
  not Gate D.
- The clean real `docs/` tree must continue to return zero hits; the existing
  `_GUARD_DOC_EXCLUSIONS` (docs/adr, docs/plans, the retrieval index, the
  relocation migration note) stay intact.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Reject a retired-shape tail of a longer path | As a maintainer, I want Gate D to ignore a `…/src/charter/offering/<kind>/built-in` (or `…/*.graph.yaml`) occurrence that is the tail of a longer path so that a correct doc is never falsely flagged. | High | Open | [build] | no — paired with FR-002 on the same fixture (positive control) |
| FR-002 | Still catch a genuine top-level reference | As a maintainer, I want Gate D to still report a genuine top-level `src/charter/offering/<kind>/built-in` or `src/charter/offering/*.graph.yaml` reference in a live doc so that the guard keeps its reach. | High | Open | [ratchet] | no — a gate that reported nothing would fail this positive control |
| FR-003 | Preserve the forbidden set and exclusions | As a maintainer, I want the set of forbidden shapes and the `_GUARD_DOC_EXCLUSIONS` left unchanged so that the fix tightens the left boundary only, never loosening what the gate forbids. | High | Open | [ratchet] | no — paired with a planted genuine dead ref that must still red |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Self-mutation-proven non-vacuity | The regression test MUST fail in both directions: RED when the left-boundary anchor is removed (over-match returns) AND RED when the match stops catching a genuine top-level dead ref. Zero vacuous assertions. | Correctness | High | Open |
| NFR-002 | Quality gates clean | Changed files pass `ruff check` and `ruff format --check --force-exclude` with zero issues, `mypy` clean, and every changed function stays at cyclomatic complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Tighten the left boundary only | The fix changes only the left-boundary admissibility of the match; it MUST NOT loosen the guard's reach, change the two forbidden path shapes, or weaken `_GUARD_DOC_EXCLUSIONS`. | Technical | High | Open |
| C-002 | No suppressions, no new ratchet | No `# noqa` / `# type: ignore` / Sonar suppressions, and no new ratchet gate or allowlist (Standing Order 5 empty-allowlist invariant). | Technical | High | Open |
| C-003 | Red-first through the pre-existing entry point | The ATDD regression test is committed before the fix, is RED on the planning base in the over-match direction, and GREEN on the final commit (Standing Order 4 / ATDD-First C-011). Never retry-to-green. | Process | High | Open |

### Key Entities

- **Gate D**: `tests/architectural/test_dead_builtin_doc_paths.py::test_no_live_doc_names_a_pre_move_builtin_path` — the `docs/`-scoped dead-path architectural gate.
- **`_MOVED_BUILTIN_DOC_RE`**: the ERE pattern Gate D feeds to `git grep -nE`; the subject of the left-boundary fix.
- **`_GUARD_DOC_EXCLUSIONS`**: the four documentation subtrees/paths excluded from the guard; unchanged by this mission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the fix, Gate D's matcher reports 0 of the three false-positive tail fixtures (nested `packs/.../src/...`, absolute `/home/.../src/...`, blob-URL `.../src/...*.graph.yaml`) and 1 of the genuine top-level fixture, on the same synthetic `docs/` tree — [build] · no-op passable: no.
- **SC-002**: Temporarily reverting the left-boundary anchor turns the new regression test RED, witnessed and recorded in the PR (self-mutation proof) — [ratchet] · no-op passable: no.
- **SC-003**: `tests/architectural/test_dead_builtin_doc_paths.py` returns zero hits on the real clean `docs/` tree and still reds on a planted genuine top-level dead ref — [ratchet] · no-op passable: no (paired with the planted dead ref).
