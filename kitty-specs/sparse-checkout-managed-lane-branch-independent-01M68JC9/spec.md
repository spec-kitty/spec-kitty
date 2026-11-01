# Mission Specification: Managed lane classification must not depend on the repository-root checkout's branch

**Mission Branch**: `issue-6844-sparse-checkout-managed-lane-branch-independent`
**Created**: 2026-10-31
**Status**: Draft
**Input**: GitHub issue [#6844](https://github.com/spec-kitty/spec-kitty/issues/6844) — "implement refuses with 'legacy sparse-checkout state' when another mission's managed lanes aren't on the primary checkout's branch (#1413's fix does not hold)"

## Intent Summary (confirmed)

- **Primary actor**: a maintainer or consumer operator who runs `spec-kitty agent action implement` (or `merge`/`consolidate`, which share the same preflight) in a repository where an earlier, already-merged Mission left its lane worktrees behind.
- **Trigger**: the repository-root checkout is on a branch that does not contain the other Mission's `kitty-specs/<mission-dir>/` (a branch switch, a fresh topic branch, a release branch). The lane worktrees under `.worktrees/` are still registered, clean, on their own lane branches, and carry exactly the managed sparse-checkout patterns spec-kitty wrote.
- **Desired outcome**: those lanes are recognised as *managed lanes* — the same verdict they get when the repository-root checkout happens to sit on a branch that contains that Mission — and no command refuses with `legacy sparse-checkout state detected`.
- **Root cause** (reproduced on `main` @ `35318ef5`, see `research.md`): `_load_managed_lane_policies()` builds the managed-lane policy set **only** from `<repo_root>/kitty-specs/*/meta.json`, which is whatever the repository-root checkout's current branch has committed. With no policy candidate, `_classify_worktree_state` leaves the default kind (`LEGACY_USER`), so `is_blocking` is true and the preflight refuses.
- **Second-order harm**: the refusal advertises `spec-kitty doctor sparse-checkout --fix`, which is exactly the remediation #1413 rules out for managed lanes — it would disable the lane sparse-checkout and put `status.events.jsonl` / `status.json` back into the lanes. A false refusal therefore steers the operator into damaging state.
- **Invariant**: the managed-lane *shape* is unchanged. No pattern, no branch name, no lane topology, and no `--allow-sparse-checkout` escape changes. Only the *source* of the policy evidence becomes branch-independent, and every existing guard (active config, exact managed pattern shape, expected lane branch, registered worktree) keeps deciding.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A preset left-over lane does not block a new Mission (Priority: P1)

As an operator, I switch the repository-root checkout to a fresh branch, create and plan Mission B, and run `implement`: Mission A's left-over lane worktrees (A is fully merged) are recognised as managed and no longer block B.

**Why this priority**: this is the reported defect; without it the repository is permanently blocked by an unrelated, already-finished Mission.

**Independent Test**: build a fixture repo where Mission A owns registered lane worktrees with the managed patterns, switch the repository-root checkout to a branch that has no `kitty-specs/<A>/`, and run the production preflight — it must not refuse.

**Acceptance Scenarios**:

1. **Given** a registered lane worktree with the managed pattern shape, the expected lane branch, and sparse-checkout active, **When** the repository-root checkout's branch contains no `kitty-specs/<A>/`, **Then** `scan_repo` classifies that lane `MANAGED_LANE` and reports no blocking path.
2. **Given** the same fixture with the repository-root checkout on a branch that *does* contain `kitty-specs/<A>/`, **When** `scan_repo` runs, **Then** the verdict is identical (`MANAGED_LANE`, not blocking) — the branch is not an input.
3. **Given** the branch-switched fixture, **When** the production preflight for `spec-kitty agent action implement` runs without `--allow-sparse-checkout`, **Then** it does not raise.

### User Story 2 - Genuine legacy state still refuses (Priority: P1)

As an operator, a worktree whose sparse pattern file does not match the managed shape (or that is on the wrong branch, or is not a registered worktree) still refuses, so the hardening #588 paid for is intact.

**Why this priority**: the fix must narrow the false positive, never widen the escape. A classification that says "managed" too eagerly would silently disable the data-loss defence.

**Independent Test**: the existing drift / wrong-branch / non-registered fixtures keep reporting `UNKNOWN` and blocking, on the same fixture family that proves the managed case is non-blocking.

**Acceptance Scenarios**:

1. **Given** a lane worktree whose pattern file is `/*` only, **When** the repository-root checkout's branch contains no `kitty-specs/<A>/` **and** when it does, **Then** the state is `UNKNOWN` and blocking in both cases.
2. **Given** a worktree on a branch that is not the expected lane branch, **Then** it stays `UNKNOWN`/blocking.
3. **Given** a directory under `.worktrees/` that git does not register as a worktree, **Then** it stays `UNKNOWN`/blocking.

### User Story 3 - The advertised remedy never damages a managed lane (Priority: P2)

As an operator, `spec-kitty doctor sparse-checkout` in the branch-switched scenario reports no legacy state and offers no remediation plan for the managed lanes.

**Why this priority**: it is the harm the issue names explicitly ("`doctor sparse-checkout --fix` should never recommend disabling a lane whose patterns match the managed shape"); it follows from the classification fix, so it needs pinning rather than new mechanism.

**Independent Test**: run the doctor detection surface against the branch-switched fixture; it exits clean and no lane path appears in the finding or the remediation plan.

**Acceptance Scenarios**:

1. **Given** the branch-switched fixture, **When** `doctor sparse-checkout` (detection mode) runs, **Then** it reports no legacy state (exit 0) and the lane path is absent from the output.
2. **Given** a genuinely legacy worktree on the same fixture family, **When** the same surface runs, **Then** it does report it (positive control on the same fixture).

### Edge Cases

- **Lane whose own tree has no `meta.json`** (Mission dir deleted in the lane, or a lane branch that never carried it): no branch-independent policy evidence exists, so the state stays `UNKNOWN`/blocking (fail closed, the pre-#6844 verdict) and the `--allow-sparse-checkout` escape stays the documented way through. Pinned by a test so the boundary is explicit rather than incidental.
- **Both sources agree** (repository-root branch *does* contain the Mission and the lane carries the same `meta.json`): the two candidates must not double up into the "more than one candidate policy → UNKNOWN" arm of `_classify_worktree_state`. The lane-local lookup is consulted only when no repository-root-derived policy matches that path.
- **Non-coordination Mission** (`meta.json` `coordination_branch` null, no lane policy): unchanged — no policy is built, so nothing becomes managed.
- **Planning lane** (`.worktrees/<slug>-lane-planning`, #5100): still `UNKNOWN`, never a crash.
- **Mission A's lane is dirty or stale**: classification reads the lane's own `meta.json` and sparse pattern file as they are on disk today; no new write, no `git checkout`, no repair.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Branch-independent policy source | As an operator, I want a lane worktree's managed policy resolved from that lane's own `kitty-specs/<mission-dir>/meta.json` so that classification cannot be flipped by the repository-root checkout's branch. | High | Open | [build] | no — the branch-switched fixture is red without it and green with it |
| FR-002 | Guards preserved | As an operator, I want every existing managed-lane guard to keep deciding (active `core.sparseCheckout`, pattern file a superset of the managed shape, expected lane branch, registered worktree), so that a genuine legacy worktree still refuses. | High | Open | [ratchet] | yes — paired on the same fixture with FR-001's branch-switched managed case, plus the drift/wrong-branch/unregistered controls |
| FR-003 | Preflight entry point | As an operator, I want the production preflight used by `agent action implement` (and shared by `merge`/`consolidate`) to stop refusing in the branch-switched scenario, while the genuine legacy message, exit code and `--allow-sparse-checkout` escape stay byte-identical. | High | Open | [build] | no |
| FR-004 | Doctor surface follows classification | As an operator, I want `doctor sparse-checkout` to report clean (and build no remediation plan) in the branch-switched scenario, so that the refusal never advertises a remedy that would put `status.events.jsonl` back into a managed lane. Satisfied by FR-001 through the existing `is_blocking` filter. | Medium | Open | [folded] | no — satisfied by FR-001; the test pairs it with a real legacy worktree that is still reported |
| FR-005 | Regression tests folded into the owning suites | As a maintainer, I want the regression pinned where the contract already lives (`tests/integration/sparse_checkout/test_detection.py`, `test_doctor_finding.py`) with no issue-named test file left behind, so that no development-assist file ships. | Medium | Open | [ratchet] | no — self-mutation control: reverting FR-001's lane-local lookup turns the new assertions red |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No scan blow-up | The lane-local policy lookup runs at most one `meta.json` read per worktree under `.worktrees/`, and only when no repository-root-derived policy already matches that path; `scan_repo` on this repository's 660-Mission corpus does not read more `meta.json` files than it does today for a checkout with no lanes. | Performance | Medium | Open |
| NFR-002 | Quality gates | Changed files pass `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` with zero findings; the new helper stays within complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Coverage | Every line added by this mission is covered by the tests added in the same mission (CI diff-cover ≥ 90% on changed lines). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|---------|
| C-001 | Policy shape unchanged | `lane_sparse_checkout_patterns`, the lane branch grammar, `register_lane_sparse_checkout`, the lane allocator and the coordination topology are untouched. Only the *source* of `meta.json` evidence is added. | Technical | High | Open |
| C-002 | Same gating on the evidence | The lane-local source is gated exactly like the repository-root source (a non-empty `coordination_branch`, a `mission_slug`, and a `mission_id` of at least 8 characters). No new mission becomes "managed" because of this change. | Technical | High | Open |
| C-003 | Fail closed | Any read failure (missing `meta.json`, unreadable file, unparsable lane directory name) leaves the state at the pre-#6844 verdict (`UNKNOWN`/blocking). No new exception path escapes `scan_repo`; `warn_if_sparse_once` keeps swallowing probe failures. | Technical | High | Open |
| C-004 | No new user-facing flag | The `--allow-sparse-checkout` escape is unchanged and no new flag, env var or config key is introduced. | Technical | Medium | Open |
| C-005 | Diagnostic honesty | The refusal text is unchanged for genuine legacy state: `legacy sparse-checkout state detected`, the affected paths, `spec-kitty doctor sparse-checkout --fix` and the `--allow-sparse-checkout` hint keep their wording (tests assert on it). | Process | High | Open |

### Key Entities

- **Managed lane policy** (`_ManagedLanePolicy`): a Mission's expected lane directory shape + expected branch, derived from that Mission's `meta.json`. Today derived only from the repository-root checkout's `kitty-specs/`; this mission adds the lane-local derivation.
- **Sparse-checkout state** (`SparseCheckoutState`): the per-path probe result; `sparse_checkout_kind` is the classification verdict that `is_blocking` reads.
- **Scan report** (`SparseCheckoutScanReport`): the aggregate the preflight (`require_no_sparse_checkout`) and the doctor surface both key on, through `any_blocking` / `affected_paths`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the branch-switched fixture, `scan_repo` reports `any_blocking == False` and the lane as `MANAGED_LANE`, matching the on-branch verdict exactly — [build] · no-op passable: no
- **SC-002**: The number of worktrees classified `MANAGED_LANE` for the same fixture is identical whichever branch the repository-root checkout is on (branch is not an input to classification) — [build] · no-op passable: no
- **SC-003**: Zero genuine-legacy fixtures change verdict: the drift, wrong-branch, non-registered and manual-worktree controls all still report `UNKNOWN`/blocking — [ratchet] · no-op passable: yes — positive control is SC-001 on the same fixture family
- **SC-004**: The production `implement` preflight raises zero times on the branch-switched fixture and exactly once on the genuine-legacy fixture, with the unchanged message — [build] · no-op passable: no
