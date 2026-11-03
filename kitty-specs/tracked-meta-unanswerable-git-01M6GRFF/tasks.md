# Work Packages: A refusal notice that names a repair the operator can actually perform

**Inputs**: Design documents from `/kitty-specs/tracked-meta-unanswerable-git-01M6GRFF/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Organization**: Two work packages. WP01 is the foundational single-authority move (a shared
"git refused on ownership" predicate); WP02 is the user-facing change (carry the cause, render the
repair class). The mission is deliberately small: the refusal itself is already correct and pinned.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add `refuses_ownership(stderr)` to `src/kernel/git/runner.py` | WP01 | |
| T002 | Re-export the predicate from `src/kernel/git/__init__.py` | WP01 | |
| T003 | Replace `_is_dubious_ownership` in `core/git_preflight.py` with the shared predicate | WP01 | |
| T004 | Cover the predicate directly in `tests/git_ops/test_git_preflight.py` | WP01 | [P] |
| T005 | Red-first: unreadable-repository, ownership and committed-blob notice tests | WP02 | |
| T006 | Carry `TrackedMeta.unreadable_reason` from `read_tracked_meta` | WP02 | |
| T007 | Render one repair-class tail per unreadable cause in the shared notice | WP02 | |
| T008 | Verification sweep, changelog fragment, tracer update | WP02 | |

---

## Work Package WP01: One owner for the ownership-refusal predicate (Priority: P1)

**Goal**: The "git refused this checkout's ownership" predicate has one home — `kernel.git.runner`,
beside `GitCommandError` — and both call sites import it. `git_preflight` behaves exactly as before.
**Independent Test**: `uv run pytest -q -p no:randomly tests/git_ops/test_git_preflight.py` is green
with the new direct predicate cases, proving the relocation changed no behaviour.
**Prompt**: `/tasks/WP01-shared-ownership-refusal-predicate.md`
**Requirement Refs**: C-005, FR-005

### Included Subtasks

T001 Add `refuses_ownership(stderr: str) -> bool` to `src/kernel/git/runner.py`
T002 Re-export it from `src/kernel/git/__init__.py` (and its `__all__`)
T003 Delete `_is_dubious_ownership` from `src/specify_cli/core/git_preflight.py`; import the shared one
T004 Cover the predicate directly in `tests/git_ops/test_git_preflight.py`

### Implementation Notes

- The two matching conditions are `"dubious ownership"` and `"safe.directory"`, case-insensitive — the
  same two the private helper used, moved without semantic change.
- `git_preflight`'s issue codes (`UNTRUSTED_REPOSITORY`, `NOT_A_GIT_REPOSITORY`), messages and
  remediation commands are **not** touched; its existing tests are the guard.
- No new `safe.directory` write and no wildcard trust is introduced anywhere (C-003).

### Parallel Opportunities

T004 can be written while T003 is applied; both touch different files.

### Dependencies

- None (starting package).

### Risks & Mitigations

- `kernel/git/__init__.py` `__all__` ordering/`__all__` convention: follow the surrounding alphabetical list.
- Import direction: `specify_cli.core.git_preflight` → `kernel.git` is the existing direction elsewhere
  in the tree, so no cycle is introduced.

---

## Work Package WP02: Carry the cause, render the repair class (Priority: P1)

**Goal**: When git cannot answer for a checkout, the operator-facing refusal says so, names the
repair class for that cause, and stops prescribing `git checkout --`. The refusal, its stable code
and the no-write guarantee are untouched.
**Independent Test**: `uv run pytest -q -p no:randomly tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`
is green with the new cause coverage, and the cutover placement suite still passes unchanged.
**Prompt**: `/tasks/WP02-carry-cause-render-repair-class.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T005 Red-first tests for the three unreadable causes
T006 `TrackedMeta.unreadable_reason` and its two call sites
T007 One repair-class tail per cause in `tracked_meta_notice`
T008 Verification sweep, changelog fragment, tracer

### Implementation Notes

- The cause is data on the classifier's answer (`"repository" | "ownership" | "objects"`), never a
  re-parse of git's stderr in the notice module.
- The subject of the sentence changes only for the unverified causes: "tracked meta.json …" becomes
  "meta.json …", because git never established that the path is tracked.
- The healthy branches (`staged_differs`, `index_only`, `corrupt`, and the usable tracked copy) keep
  their text and their `git checkout --`/`git show HEAD:` remedies exactly.
- No new write path, no `safe.directory` mutation, no stderr echo (NFR-001).

### Parallel Opportunities

None — T005→T007 are one red-first chain in one module pair.

### Dependencies

- Dependencies: WP01 (WP02 imports the shared `refuses_ownership` predicate).

### Risks & Mitigations

- `tests/specify_cli/upgrade` is out-of-matrix (nightly), so the PR must record the targeted local run.
- The committed-blob cause needs a genuinely unreadable object; corrupting one loose object keeps the
  fixture real (no monkeypatched git) — if that proves brittle across git versions, patch the git seam
  the way `tests/git_ops/test_git_preflight.py` already does and say so in the test docstring.
- The ownership cause cannot be produced by an unprivileged test (git only refuses ownership for a
  checkout owned by another uid), so that one test patches the git invocation seam with git's real
  refusal text — the same technique the preflight tests already use.
