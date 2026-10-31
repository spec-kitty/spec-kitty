# Work Packages: Managed lane classification independent of the root checkout's branch

**Inputs**: `kitty-specs/sparse-checkout-managed-lane-branch-independent-01M68JC9/`
**Prerequisites**: spec.md, plan.md, research.md
**Tests**: Required. The regression is pinned red-first through the production preflight before the classifier changes (charter ATDD-First Discipline; DIRECTIVE_034).
**Organization**: One bounded work package; five sequential subtasks; no parallel file writers (one production surface, one test surface).
**Audience**: software-engineer and automation-agent.

## Subtask Format: `[Txxx] [P?] Description`

Plain `Txxx` rows are reference rows. Record completion with `spec-kitty agent tasks mark-status`; do not tick a markdown box or edit a lane field by hand. No `[P]` markers: every subtask touches the same production or test surface.

## Path Conventions

All source/test paths are repository-root-relative; mission artifacts resolve under this Mission directory. Planning base / mission target: `issue-6844-sparse-checkout-managed-lane-branch-independent` (`single_branch`). The PR targets `main`. Never merge, never push `main`.

## Work Package WP01: Branch-independent managed lane policy source (Priority: P1)

**Goal**: Deliver #6844: a managed lane worktree keeps its `MANAGED_LANE` classification — and stops blocking the preflight — whichever branch the repository-root checkout happens to be on, while genuinely legacy sparse state still refuses with the unchanged message.
**Independent Test**: On a real `git worktree` fixture, `scan_repo` / `require_no_sparse_checkout` return the identical `MANAGED_LANE` / non-blocking verdict on both the branch that contains the other Mission's `kitty-specs/` and the branch that does not; every genuine-legacy control on the same fixture family still reports `UNKNOWN` and blocks.
**Prompt**: `kitty-specs/sparse-checkout-managed-lane-branch-independent-01M68JC9/tasks/WP01-branch-independent-lane-policy.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-005, SC-001, SC-002, SC-003, SC-004
**Issue Owner**: Ivan-Melck; issue-matrix row for #6844 starts `in-mission` and reaches `fixed` at hand-off.

### Included Subtasks

T001 Extend the coordination-lane fixture so the repository-root checkout can be switched to a branch without the other Mission's `kitty-specs/`, and add the scan-level branch-independence assertions (red on `main`).
T002 Add the production preflight assertion (`require_no_sparse_checkout`) plus the fail-closed controls (pattern drift, foreign branch, unregistered worktree, lane with no `meta.json` of its own), all red before the fix.
T003 Implement the branch-independent policy source: extract the shared policy constructor, add the lane-local `meta.json` reader, and order the two sources per path in `scan_repo` so the classifier is untouched.
T004 Pin the doctor surface: the branch-switched fixture reports clean (exit 0, lane path absent) while a genuine legacy worktree on the same fixture family is still reported and still gets a remediation plan entry.
T005 Run the targeted suites, the scoped lint/format/strict-typing gates and diff coverage; add the `[Unreleased]` changelog entry and reconcile the docs that describe the preflight; record the self-review evidence.

### Implementation Notes

- The production change is confined to `src/specify_cli/git/sparse_checkout.py`. `_classify_worktree_state`, `SparseCheckoutState`, `SparseCheckoutScanReport`, `require_no_sparse_checkout` and the refusal text must not change.
- `_load_managed_lane_policies` keeps its repository-root source and gains a shared `_policy_from_meta` constructor; `_policy_from_lane_worktree` reads the lane's own `kitty-specs/<mission_dir>/meta.json` and is consulted **only** when no repository-root-derived policy `matches_path` that child. The "more than one candidate → `UNKNOWN`" arm must keep its meaning.
- Fail closed: an unparsable worktree directory name, a missing `meta.json`, or a malformed one yields no policy (pre-#6844 verdict). No exception may escape `scan_repo`.
- Tests are folded into `tests/integration/sparse_checkout/test_detection.py` and `tests/integration/sparse_checkout/test_doctor_finding.py` — the suites that already own this contract. No issue-named test file ships.
- The red-first commit precedes the production fix commit; the fix commit removes nothing from the new tests.

### Parallel Opportunities

None for implementation. The reviewer is a separate role/session after hand-off.

### Dependencies

None. `single_branch` execution uses the resolver-returned write checkout; there is no lane worktree, no lane merge and no consolidation step for this topology.

### Risks & Mitigations

A widened escape (managed granted to a look-alike worktree) → the pattern-shape, expected-branch and registration guards are unchanged and covered by same-fixture controls. A duplicated candidate turning a correct verdict into `UNKNOWN` → the lane-local source is only consulted when the repository-root source produced nothing for that path, and a dedicated test covers the both-sources-agree case. A scan cost regression (660 Missions per lane) → the read is targeted by the directory name, at most one `meta.json` per lane, and covered by a test that the lane-local reader is not consulted when a repository-root policy already matched.

## Dependency & Execution Summary

- **Sequence**: WP01 T001–T002 RED commits → T003 green → T004 pinning → T005 validation/self-review.
- **Parallelization**: None among writing tasks.
- **MVP Scope**: WP01 is the whole change.
- **Hand-off**: `/spec-kitty.analyze` readiness gate, then implement, then independent review; the operator opens/merges the PR.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| C-004 | WP01 |
| C-005 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Branch-switched fixture + scan assertions (RED) | WP01 | P1 | No |
| T002 | Preflight assertion + fail-closed controls (RED) | WP01 | P1 | No |
| T003 | Branch-independent policy source (GREEN) | WP01 | P1 | No |
| T004 | Doctor-surface pinning | WP01 | P1 | No |
| T005 | Validation, changelog, docs, self-review | WP01 | P1 | No |
