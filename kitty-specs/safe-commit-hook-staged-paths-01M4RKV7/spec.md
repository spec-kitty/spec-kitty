# Mission Specification: Guard `safe_commit` against hook-staged paths

**Mission Branch**: `issue-5903-safe-commit-hook-staged-paths`
**Created**: 2026-10-12
**Status**: Draft
**Input**: User description: "Deliver #5903 — stop `safe_commit` from silently committing the operator's unstaged edits (and leaving their index staging a revert) when a pre-commit hook stages files."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator's unstaged edits are never silently swept into a `--only` commit (Priority: P1)

An operator has a formatter / lint-staged-style pre-commit hook that runs `git add -u`. They
have an in-progress edit to `operator.txt` that they have **not** staged. A Spec Kitty flow
(upgrade, claim, bake, spec-commit, a status commit, the `safe-commit` CLI, …) calls
`safe_commit(paths=(tool.txt,))` to commit exactly the file the operation wrote. Because
`git commit --only` runs the hook against git's own temporary index, the hook's `git add -u`
stages `operator.txt` into the commit being built.

Today the commit silently carries `operator.txt`, `safe_commit` returns success (exit 0), and
the operator's real index is left staging a revert of their own edit (`git status` shows `MM`).
After this mission, `safe_commit` detects the mismatch after the commit landed, re-syncs the
operator's real index so no stale `MM` remains, and reports the landing the "landed, but" way
through a `SafeCommitRecoveryFailed`-style result that **names** the extra paths — so the caller
knows the commit landed and knows it carried content the operation never requested.

**Why this priority**: This is the P0 defect itself — a success report that hides a data-integrity
problem (unrequested content committed; the operator's work staged for reversal) is the most
dangerous possible failure mode for a commit helper.

**Independent Test**: In a fixture repo with a `git add -u` pre-commit hook and an unstaged edit,
call `safe_commit(paths=(tool.txt,))` and assert it raises a `SafeCommitRecoveryFailed` subclass
whose `commit_sha` is set and whose message/paths name `operator.txt`, that the landed commit's
tree is left as git produced it, and that the operator's real index no longer stages a revert
(`git diff --cached` for `operator.txt` is empty).

**Acceptance Scenarios**:

1. **Given** a repo with a `git add -u` pre-commit hook and an unstaged edit to a tracked file,
   **When** `safe_commit(paths=(tool.txt,))` is called, **Then** it raises a
   `SafeCommitRecoveryFailed` subclass carrying the landed `commit_sha` and naming the swept path,
   and the operator's real index no longer stages a revert of that path.
2. **Given** the same repo with **no** pre-commit hook, **When** `safe_commit(paths=(tool.txt,))`
   is called, **Then** it returns a `CommitResult` with the same SHA and tree it produced before
   this mission (byte-identical clean-path behaviour; no new raise).

---

### User Story 2 - The FR-022 temp-index route gets the same guard (Priority: P1)

The FR-022 path (`safe_commit(paths=..., index_deletions=...)` → `_commit_with_index_deletions`)
commits from a temporary index seeded from HEAD, under its own `GIT_INDEX_FILE`. A `git add -u`
pre-commit hook stages the operator's other modified tracked files into that temp index exactly as
on the `--only` route, so the same silent-sweep defect applies.

**Why this priority**: The issue names both routes as affected; a guard that covers only `--only`
leaves the FR-022 migration path (used by `upgrade`) exposed to the identical P0.

**Independent Test**: In a fixture repo with a `git add -u` pre-commit hook, an unstaged edit, and a
tracked file to index-delete, call `safe_commit(paths=(tool.txt,), index_deletions=(untrack.txt,))`
and assert the same "landed, but" raise naming only the genuinely-extra path (`operator.txt`) —
the requested path and the deletion are **not** reported as extra — and the operator's real index
is left consistent.

**Acceptance Scenarios**:

1. **Given** a repo with a `git add -u` pre-commit hook, an unstaged edit, and a tracked file
   requested for index deletion, **When**
   `safe_commit(paths=(tool.txt,), index_deletions=(untrack.txt,))` is called, **Then** it raises
   the same `SafeCommitRecoveryFailed` subclass naming `operator.txt` only (never `tool.txt` or
   `untrack.txt`), carrying the landed `commit_sha`.
2. **Given** the same repo with **no** pre-commit hook, **When** the same call is made, **Then** it
   returns a `CommitResult` with the requested add and the index deletion, and raises nothing.

---

### User Story 3 - The expected-parent route and every caller stay correct (Priority: P2)

The expected-parent route (`commit-tree` + CAS `update-ref`) already rebuilds the commit tree from
the requested paths only, so a hook's extra staging is dropped — it is the negative control and
must stay unaffected. Every `safe_commit` caller (upgrade, claim, bake, spec-commit, the
`safe-commit` CLI, status commits) must surface the new outcome as "DID land", the same way they
already surface `SAFE_COMMIT_INDEX_RESIDUE`, so none of them misreports the landed commit as a
failure-to-land.

**Why this priority**: Protecting the control and the caller surfaces guarantees the fix closes the
defect without regressing the route that was already correct or the callers that already handle the
"landed, but" family.

**Independent Test**: Call `safe_commit(paths=(tool.txt,), expected_parent_sha=HEAD)` in the hooked
fixture and assert the commit carries only `tool.txt` and raises nothing; and assert the new error
class satisfies the shared caller predicate `isinstance(exc, SafeCommitRecoveryFailed) and
exc.commit_sha is not None`.

**Acceptance Scenarios**:

1. **Given** the hooked fixture, **When** `safe_commit(..., expected_parent_sha=HEAD)` is called,
   **Then** the commit contains exactly `tool.txt` and nothing is raised (control stays GREEN).
2. **Given** the new error class, **When** a caller applies the shared "DID land" predicate,
   **Then** the predicate is satisfied (the new code is contract-registered and surfaced as a
   landed commit, not a failure-to-land).

### Edge Cases

- A **partial / subset** commit: a requested path is a genuine no-op while another requested path
  changed — the committed set is a subset of the requested set, so no path is reported extra.
- An **empty changeset** for the requested paths (benign no-op) still raises
  `SafeCommitStagedTreeUnchanged`, never the new error (the commit never lands).
- A hook that stages an **untracked** new file: that path is extra and is reported; the real index
  re-sync must leave it in a consistent state (unstaged, not staging content the operation never
  wrote).
- Out of scope: a hook that runs `git stash` against the temporary index (PR #5896 lists it
  separately; untested; left as a follow-up note).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Post-landing path check on the `--only` route | As an operator, I want `safe_commit(paths=...)` to detect when the landed commit carries paths the operation did not request so that hook-swept edits are never silently committed. | High | Open | [build] | no — paired with the no-hook control (FR-004) proving a clean commit does not raise |
| FR-002 | Same post-landing path check on the FR-022 temp-index route | As an operator, I want `safe_commit(paths=..., index_deletions=...)` to apply the identical post-landing check so that the migration/upgrade path is guarded too. | High | Open | [build] | no — paired with the no-hook FR-022 control (FR-004) |
| FR-003 | Re-sync the operator's real index for the extra paths | As an operator, I want my real index left consistent (no stale `MM` staging a revert) after a swept commit so that a later plain `git commit` does not revert my work. | High | Open | [build] | no — asserted by `git diff --cached` being empty for the swept path after the call |
| FR-004 | Clean (no-hook) `safe_commit` is byte-identical; expected-parent route unaffected | As a caller, I want a hook-free `safe_commit` and the expected-parent route to behave exactly as before so that the guard adds no behavioural change on the healthy paths. | High | Open | [ratchet] | no — the hooked positive controls (FR-001/FR-002) prove the guard is non-vacuous, same fixture |
| FR-005 | Register the new contract-visible error code in `upstream_contract.json` + every mirror | As an external consumer, I want the new `safe_commit` failure code in the published contract and its docs mirror so that scripted detection stays complete. | High | Open | [build] | no — the contract/mirror-parity gate fails if the code is absent from either file |
| FR-006 | Caller surfaces report the new outcome as "DID land" | As a caller (upgrade/claim/bake/spec-commit/safe-commit CLI/status commits), I want the new outcome treated as a landed commit, the way `SAFE_COMMIT_INDEX_RESIDUE` already is, so that no caller misreports it as failure-to-land. | Medium | Open | [folded] | no — folded into FR-001/FR-002 by subclassing `SafeCommitRecoveryFailed` with `commit_sha` set; proven by the shared-predicate test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra cost on the clean path | The post-landing check adds at most one `git diff-tree` read and a set comparison on a successful commit; no index mutation occurs unless an extra path is detected. | Performance | Medium | Open |
| NFR-002 | Hooks still run | The fix must not pass `--no-verify` or otherwise disable/skip pre-commit hooks on any route. | Reliability | High | Open |
| NFR-003 | Type/lint/complexity clean | New code passes `mypy --strict`, `ruff check`, `ruff format`, and keeps cyclomatic complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority for the new error code | The new error code is defined once in `upstream_contract.json` with its mirrors updated in the same change; no second authority is introduced. | Technical | High | Open |
| C-002 | Do not change the expected-parent route | The `commit-tree` + CAS route already rebuilds the tree from requested paths only; it must stay the untouched negative control. | Technical | High | Open |
| C-003 | Final regression tests are unmarked and green | The red reproduction may carry `@pytest.mark.p0_repro(issue=5903)` while red, but because this PR also lands the fix the final committed tests are UNMARKED permanent regression tests. | Process | High | Open |

### Key Entities

- **`safe_commit` post-landing check**: compares `git diff-tree --name-only` of the new commit
  against the requested path set (plus FR-022 `index_deletions`); on mismatch re-syncs the real
  index for the extra paths and raises the new `SafeCommitRecoveryFailed` subclass naming them.
- **New error class** (a `SafeCommitRecoveryFailed` subclass with its own `error_code`, carrying
  `commit_sha` + the extra paths): mirrors `SafeCommitIndexResidue` so every caller's existing
  "DID land" predicate handles it unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `--only` and FR-022 reproduction tests are RED on `origin/main` and GREEN on the
  final mission commit; the expected-parent control is GREEN on both. — [build] · no-op passable: no
- **SC-002**: After a hook-swept `safe_commit` call, the operator's real index stages no revert of
  the swept path (`git diff --cached <path>` is empty). — [build] · no-op passable: no
- **SC-003**: The contract/mirror-parity gate(s) pass with the new error code present in
  `upstream_contract.json` and `docs/contracts/upstream-3.0.0-shape.json`. — [build] · no-op passable: no
- **SC-004**: No `safe_commit` caller misreports the new outcome as failure-to-land (the shared
  `SafeCommitRecoveryFailed` + `commit_sha` predicate is satisfied). — [folded] · no-op passable: no
