# Work Packages: Evidence survives a pruned lane branch

**Inputs**: Design documents from `kitty-specs/pruned-lane-evidence-window-01M67HX3/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required. This is a defect fix: the reproduction must fail through the real
`accept --mode pr --merge-commit` entry point before the production edit (charter,
ATDD-First Discipline).

**Organization**: Two work packages. WP01 carries the red-first reproduction, the
production window stand-in, the honest refusal and the attestation plumbing. WP02
carries the operator-facing record (changelog + pr-landing gotcha).

**Prompt Files**: `kitty-specs/pruned-lane-evidence-window-01M67HX3/tasks/`

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/specify_cli/`, `tests/`.

---

## Work Package WP01: Evidence is judged against the verified landing when the lane branch is gone (Priority: P1) 🎯 MVP

**Goal**: A PR-landed lanes Mission whose lane branches were pruned accepts through
`accept --mode pr --merge-commit`; a hollow work package still refuses
`IMPLEMENTATION_MISSING`; a readable lane branch keeps using the lane window; and with
no verified landing commit the refusal names the missing branch and both remedies.
**Independent Test**: The extended `test_accept_merge_commit.py` fixture merges the lane
branch into the mission branch, lands it on the target with a PR-shaped merge commit,
deletes the lane branch, and drives the production `accept(...)` entry point — the
reproduction passes, the hollow arm refuses, the intact-lane control uses the lane window.
**Prompt**: `tasks/WP01-landed-evidence-window.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002,
NFR-003, NFR-004, C-001, C-002, C-003

### Included Subtasks

T001 Survey the evidence window, the dependency widening and both accept call sites; record the exact call chain in the WP history
T002 [P] Write the failing reproduction in `tests/specify_cli/cli/commands/test_accept_merge_commit.py` (lane merged into the mission branch, PR landing, lane branch pruned) and run it RED on the pre-fix code
T003 [P] Add the same-fixture arms: a hollow approved WP still refuses `IMPLEMENTATION_MISSING`, and a present lane branch still uses the lane window
T004 Implement the landed-window stand-in in `src/specify_cli/consolidation/wp_evidence.py` (window choice, ancestor guard, dependency-widening tip) and the honest `IMPLEMENTATION_UNREADABLE` refusal text
T005 Thread the verified landing commit from `src/specify_cli/cli/commands/accept.py` into the evidence gate and `src/specify_cli/consolidation/no_implementation_attestation.py`
T006 Run the touched modules plus the #6715/#5939 evidence modules and the code-literal module; record counts
T007 Run the project's lint/type checks on the touched Python files

### Implementation Notes

- The lane branch stays the first choice: the stand-in is consulted only when the
  window's tip does not resolve to a commit (research.md D-2).
- The stand-in is opt-in from the caller that verified the landing
  (`verify_pr_merge_evidence`); every other call site passes `None` and is unchanged
  (D-3).
- The base, the owned-glob match, the bookkeeping exclusion and the independence check
  are untouched; only the tip changes (D-4).
- A planning commit that is not an ancestor of the landing commit is refused, never
  diffed (D-5).
- The dependency widening must use the same effective tip (D-6).

### Parallel Opportunities

- T002 and T003 share one test file — write them in one pass.

### Dependencies

- None.

### Risks & Mitigations

- A fixture that leaves the lane branch in place never reproduces the bug → the new
  fixture deletes `refs/heads/<lane branch>` explicitly and asserts the reproduction red
  first.
- The hollow arm could pass vacuously if its owned files were untouched anywhere →
  assert the exact code (`IMPLEMENTATION_MISSING`) and that nothing was written.

---

## Work Package WP02: The operator-facing record explains the pruned-branch path (Priority: P2)

**Goal**: The changelog and the PR-landing runbook tell an operator that a PR-landed
Mission's evidence is judged against the verified landing commit when its lane branches
are pruned, and how to make the accept succeed (or what a refused one is telling them).
**Independent Test**: `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry with
the `(#6780)` reference and before/after; `docs/development/how-to/pr-landing.md` carries
a gotcha naming `--merge-commit` and the pruned-lane case.
**Prompt**: `tasks/WP02-docs-and-changelog.md`
**Requirement Refs**: FR-001, FR-004, NFR-003

### Included Subtasks

T008 Add the `[Unreleased]` changelog entry under `docs/changelog/CHANGELOG.md`
T009 Add the pruned-lane-branch gotcha to `docs/development/how-to/pr-landing.md`
T010 Run the docs freshness check and the terminology gate over the touched docs

### Implementation Notes

- Changelog shape: bold impact-first lead ending with `(#6780)`, then before/after, under
  1,200 characters.
- Quote the refusal/recovery wording from WP01 verbatim so a grep of code and docs agrees.
- No new CLI option, so no generated CLI reference regeneration is expected; confirm with
  the freshness check.

### Parallel Opportunities

- T008 and T009 touch different files.

### Dependencies

- Depends on WP01 (the wording it documents).

### Risks & Mitigations

- Documentation drift → quote the shipped strings verbatim from the code.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none worth splitting; the mission is deliberately two packages.
- **MVP Scope**: WP01 alone delivers the fix; WP02 completes the operator-facing record.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|---------------------------|
| FR-001 | WP01, WP02 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01, WP02 |
| FR-005 | WP01 |
| FR-006 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01, WP02 |
| NFR-004 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01, WP02 |
| SC-005 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Survey the evidence window, widening and accept call sites | WP01 | P1 | No |
| T002 | Failing reproduction through `accept --mode pr --merge-commit` | WP01 | P1 | Yes |
| T003 | Hollow-WP refusal arm and intact-lane control arm | WP01 | P1 | Yes |
| T004 | Landed-window stand-in + honest refusal text | WP01 | P1 | No |
| T005 | Thread the verified landing commit through accept and the attestation planner | WP01 | P1 | No |
| T006 | Targeted evidence module test run | WP01 | P1 | No |
| T007 | Lint/type check the touched files | WP01 | P1 | Yes |
| T008 | Changelog `[Unreleased]` entry | WP02 | P2 | Yes |
| T009 | `pr-landing.md` pruned-lane gotcha | WP02 | P2 | Yes |
| T010 | Docs freshness + terminology checks | WP02 | P2 | No |
