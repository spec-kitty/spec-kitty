# Mission Specification: Status lock directory name single-source

**Mission Branch**: `issue-6516-status-lock-dir-name-ssot`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6516 — "Red main: status/locking.py hand-rolls a `.spec-kitty` home literal and trips `test_no_handrolled_spec_kitty_home_in_global_state_modules`", plus the run guidance: route the literal through the canonical resolver, delete the literal, and pin with the existing gate rather than adding an exemption.

## Problem

`src/specify_cli/status/locking.py` carries `_NON_GIT_LOCK_HOME = ".spec-kitty"` (added by #6367). The value names the **repository-local** runtime directory a bare non-git tree's status lock falls back to — *not* the user-global runtime home. It is the same directory `specify_cli.review.lock` uses for its worktree lock, and #6367 chose it precisely because no project/repository-root walk treats it as a marker.

Two things are wrong with it as it stands:

1. The name is hand-rolled a second time. The directory name is already spelled in the canonical runtime-state path authority (`specify_cli.paths`), which is the one place the runtime state directory is named; a second copy can drift from it silently.
2. `tests/audit/test_no_legacy_path_literals.py` was made to step around it. #6582 appended `src/specify_cli/status/locking.py` to `_HOME_LITERAL_ALLOWLIST` so the nightly escalation went green, which is exactly the blind allowlist issue #6516 says not to add: the runtime-home guard (`spec-kitty-home-isolation-01KW1JXX#FR-010`, enforced by `tests/audit/test_no_legacy_path_literals.py`) no longer looks at that module at all, so a real re-scatter of the *home* literal into it would pass unseen.

The variable's name is the root of the confusion: `..._HOME` reads as "the user-global runtime home", which is what the runtime-home guard forbids recomputing. The value is a repository-local directory.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The runtime-home guard covers the status lock module again (Priority: P1)

A maintainer changes `src/specify_cli/status/locking.py` and, by mistake, re-types the runtime state directory name (or a `Path.home() / ".spec-kitty"` recompute). The runtime-home audit gate fails the build and names the file and line, instead of stepping over the module because it is allowlisted.

**Why this priority**: the guard is the only structural defence against the #2171 class of bug (global state scattered across hand-rolled homes). An allowlisted module is an unprotected module, and this one is a live place state is composed.

**Independent Test**: run `pytest tests/audit/test_no_legacy_path_literals.py`. It fails on current `main` once the exemption is removed (the red step) and passes once the literal is gone from the module.

**Acceptance Scenarios**:

1. **Given** `src/specify_cli/status/locking.py` with a hand-rolled `.spec-kitty` literal and no allowlist entry, **When** the runtime-home guard runs, **Then** it reports `src/specify_cli/status/locking.py:<line>` as a violation.
2. **Given** the module rewritten to source the name from the runtime-state path authority, **When** the guard runs, **Then** it reports no violation for that module and the rest of the suite is unchanged.

### User Story 2 - One owner for the runtime state directory name (Priority: P2)

A maintainer renames or re-homes the runtime state directory (or adds a Windows/POSIX branch), and the status-lock fallback follows from the canonical authority instead of keeping a stale second copy.

**Why this priority**: it is the durable half of the fix; the guard only tells you when you broke it.

**Independent Test**: `grep` for the bare literal outside the canonical authority returns nothing in `src/specify_cli/status/`; importing the module yields the same directory name the authority exports.

**Acceptance Scenarios**:

1. **Given** the runtime-state path authority exports the canonical directory name, **When** `status/locking.py` builds its non-git fallback, **Then** the directory segment is that exported name, not a literal typed in `status/locking.py`.

### User Story 3 - An operator's existing locks do not move (Priority: P2)

An operator with a bare non-git tree takes a status lock. The lock still lands at `<repo_root>/.spec-kitty/spec-kitty-locks/<key>.status.lock`, `#6367`'s no-marker guarantee still holds, and no in-flight lock file becomes orphaned.

**Why this priority**: this is a refactor of where a name comes from. Moving the lock to the user-global home instead would be a behaviour change (and would collide unrelated bare trees that share a mission-dir key), so the location is a hard constraint.

**Independent Test**: `pytest tests/status/test_lock_fallback_never_mints_marker.py` passes with no edits to its assertions.

**Acceptance Scenarios**:

1. **Given** a bare non-git directory, **When** a status lock is taken, **Then** the lock path is `<root>/.spec-kitty/spec-kitty-locks/<key>.status.lock` and neither `.git` nor `.kittify` is created.
2. **Given** the same directory one level below, **When** a project-root walk runs after the lock, **Then** it still finds no project.

### Edge Cases

- A tree that already has `.git` or `.kittify` keeps its existing lock location (both branches untouched by this mission).
- `SPEC_KITTY_HOME` set to a custom path: the *repository-local* fallback directory is unaffected by design (it is not global state); the global home tests that assert `get_runtime_root().base` equality must keep passing.
- A module importing the authority at call time versus at import time must not create an import cycle; `specify_cli.paths.windows_paths` is a leaf that must gain no imports.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Status-lock module is scanned by the runtime-home guard again | As a maintainer, I want `tests/audit/test_no_legacy_path_literals.py` to fail when `src/specify_cli/status/locking.py` hand-rolls a bare `.spec-kitty` literal, so the literal cannot reappear unseen behind an exemption. | High | Open | [ratchet] | no — a no-op leaves the #6582 allowlist entry in place, which the row's own assertion (`status/locking.py` not in `_HOME_LITERAL_ALLOWLIST`) rejects. |
| FR-002 | Directory name sourced from the runtime-state authority | As a maintainer, I want the non-git lock fallback's directory name to come from `specify_cli.paths` — the one place the runtime state directory is named — so a rename or a home-policy change cannot leave a second hand-rolled copy behind. | High | Open | [build] | no |
| FR-003 | The module's constant no longer presents itself as a home | As a maintainer, I want the constant named for what it is (a repository-local lock directory), so the next reader and the next guard author are not misled by a `..._HOME` name. | Medium | Open | [build] | no |
| FR-004 | Fallback lock location is unchanged | As an operator with a bare non-git tree, I want the status lock to keep living under `<repo_root>/.spec-kitty/spec-kitty-locks/`, so in-flight locks and #6367's no-marker guarantee are unchanged. | High | Open | [ratchet] | yes — [ratchet] row; the pin is `tests/status/test_lock_fallback_never_mints_marker.py`, whose own fixture also asserts the post-lock walk finds no project (same-fixture positive control). |
| FR-005 | The exemption cannot be re-added silently | As a maintainer, I want an allowlist-bypassed scan of the global-state surface to prove `status/locking.py` is literal-free, so re-adding both the literal and an allowlist entry goes red. | High | Open | [ratchet] | no |
| FR-006 | The sibling worktree lock uses the same owner | As a maintainer, I want `src/specify_cli/review/lock.py`'s `LOCK_DIR` to take the same directory name from the runtime-state authority, so the mission leaves one owner for the name instead of two hand-rolled copies and the runtime-home guard covers both modules. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Import boundaries hold | `src/specify_cli/paths/windows_paths.py` gains zero imports (it is a documented leaf); `status/locking.py` imports only from `specify_cli`/`kernel` modules it may already depend on. Verified by `ruff check`, `mypy` (no new errors) and the import-cycle tests. | Maintainability | High | Open |
| NFR-002 | No behaviour change in the lock paths | The status lock test files pass with zero edits to their assertions, and CI's diff-cover stays >= 90 % on changed lines. | Reliability | High | Open |

### Constraints


| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Fallback stays repository-local | The non-git fallback must not be re-pointed at `get_runtime_root().base`: that would move lock state out of the tree and serialise unrelated bare trees sharing a mission-dir key (#6367). | Technical | High | Open |
| C-002 | The guard shrinks, never widens | `_HOME_LITERAL_ALLOWLIST` must lose the `status/locking.py` entry and gain none; no gate is narrowed, skipped or xfailed. | Technical | High | Open |
| C-003 | Per-PR routing of `tests/audit/**` is out of scope | The issue's second half (a `src/specify_cli/status/**` diff does not route `tests/audit/**` per PR) is a router/module-registry change with its own cost decision; it is deferred to a filed follow-up and named in the PR's `## Deferred` section. | Business | Medium | Open |

### Key Entities

- **Runtime-state directory name**: the single directory name (`".spec-kitty"`) the runtime state root uses, owned by the canonical path authority; the repository-local runtime directory deliberately shares it.
- **Non-git lock fallback directory**: `<repo_root>/<runtime-state directory name>` — the repository-local home of the bare-tree status lock. Not a project or repository marker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/audit/test_no_legacy_path_literals.py` passes with `src/specify_cli/status/locking.py` absent from `_HOME_LITERAL_ALLOWLIST`, and fails (naming that file) if the entry is removed before the code fix — the red-first proof. — [ratchet] · no-op passable: no
- **SC-002**: `_scan_global_state_for_home_literal(repo_root, frozenset())` reports no violation starting `src/specify_cli/status/locking.py:`, so the exemption cannot be restored silently. — [ratchet] · no-op passable: no
- **SC-003**: `pytest tests/status/test_lock_fallback_never_mints_marker.py` passes with no edits: the three fallback branches and the no-marker walk are unchanged. — [ratchet] · no-op passable: yes — same-fixture control: the file's bare-tree test also asserts `.kittify`/`.git` were not created after a real lock.
- **SC-004**: The bare `.spec-kitty` literal appears in exactly the allowlisted canonical-owner modules (`paths/windows_paths.py`, `kernel/paths.py`, `paths/windows_migrate.py`) — two fewer modules than on `main`, and the only one of them in the `specify_cli` package is the path authority itself. — [build] · no-op passable: no
- **SC-005**: `LOCK_DIR` in `src/specify_cli/review/lock.py` still resolves to `".spec-kitty"` (pinned by the review-lock tests, which import it), sourced from the authority rather than typed there. — [ratchet] · no-op passable: yes — same-fixture control: `tests/specify_cli/test_audit_tail_readers.py` builds a real lock under `tmp_path / LOCK_DIR` and asserts the unreadable-lock refusal, so a wrong value fails the behavioural path, not just a constant comparison.
