# Mission Specification: Refuse a `--target` override onto a protected branch

**Mission Branch**: `issue-6464-protected-target-override-refusal`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "issue #6464 — `merge --target main` commits directly to protected branches with no guard. Reproduce, then make it refuse (or route through the honest path) when the target is protected, with an actionable message, and pin it."
**Issue**: spec-kitty/spec-kitty#6464

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The landing commit never writes onto a protected branch (Priority: P1)

An operator consolidates a Mission whose recorded target is an ordinary topic branch (`develop`) and
adds `--target main` — the default branch of their repository, protected by policy. Today the
branch-integration step squash-commits the Mission straight onto local `main`, outside the protection
gate that every status commit goes through; only a later bookkeeping step notices, and only because
the checkout happens to disagree with the recorded target. The operator must instead be refused
before anything moves, with a message that says which branch is protected, what the Mission is
actually recorded for, and the three ways forward.

**Why this priority**: it is the issue's exact shape — a commit written onto a protected branch with
no guard — and it is the only path by which `consolidate` can reach a protected ref that the project's
protection policy never sees.

**Independent Test**: run the real `spec-kitty consolidate --mission <slug> --target main --yes` in a
repository whose recorded target is `develop`; assert exit 1, `PROTECTED_BRANCH_REFUSED`, `main` at
its pre-run SHA, no squash commit on `main`, and the remedy naming the recorded target.

**Acceptance Scenarios**:

1. **Given** a Mission recorded for `develop` in a repository whose protected set includes `main`,
   **When** the operator runs `consolidate --target main`, **Then** the command exits 1 with
   `PROTECTED_BRANCH_REFUSED` before any branch moves and `main` keeps its pre-run SHA.
2. **Given** the same Mission and repository, **When** the operator runs `consolidate --target develop`
   (the recorded target restated), **Then** the consolidation proceeds exactly as it does today.
3. **Given** the same Mission and repository, **When** the operator runs `consolidate --target main`
   with `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`, **Then** the guard stands down, exactly as the
   operator hatch does for every other protection decision.

---

### User Story 2 - The preview and the API tell the same story (Priority: P2)

An operator previews with `--dry-run`, or an external orchestrator calls
`orchestrator-api consolidate-mission --target main`. Neither may be more permissive than the real
command: each must report the same refusal code and the same remedy, and neither may move a branch.

**Why this priority**: `--dry-run` is sold as a readiness signal, and the orchestrator-api is a
machine contract; a preview that promises success where the real run refuses is worse than no preview.

**Independent Test**: run both entries against the same refusing fixture and assert the code and the
remedy appear in the JSON payload, with every branch unmoved.

**Acceptance Scenarios**:

1. **Given** the refusing fixture, **When** `consolidate --dry-run --json --target main` runs, **Then**
   the payload carries `PROTECTED_BRANCH_REFUSED` and the remedy, and exits 1.
2. **Given** the refusing fixture, **When** `orchestrator-api consolidate-mission --target main` runs,
   **Then** its failure envelope carries the same code and no branch moves.

---

### User Story 3 - The refusals that already work stay exactly as they are (Priority: P3)

The recorded-target refusal (#5385) must not change, and the landings the project deliberately allows
— a coordination-topology Mission on `main`, an all-done Mission, a `single_branch` Mission created
with `--commit-to-target` — must keep consolidating.

**Why this priority**: the guard must key on the branch-protection decision, not on "`--target` was
passed", or it silently widens a documented contract.

**Independent Test**: the existing `tests/terminus/test_protected_target_preflight.py` controls stay
green unmodified, and a new control proves an in-bounds `--target` is not refused.

**Acceptance Scenarios**:

1. **Given** any #5385 control (coord Mission on `main`, all-done Mission, `commit_to_target`), **When**
   it runs, **Then** its existing outcome is unchanged.
2. **Given** a Mission recorded for `develop`, **When** it runs with `--target develop`, **Then** it
   consolidates as before.

### Edge Cases

- `--target` names the recorded target explicitly (a restatement): not a retarget, never refused.
- `--target` names an unprotected branch other than the recorded target: **out of scope** — the guard
  keys on protection only, so that run keeps today's behaviour (it still fails later on the
  bookkeeping HEAD mismatch; recorded as a residual, not widened here).
- The operator hatch `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` is set: the guard stands down.
- `--skip-lanes` synthesises a manifest: the recorded target is still read from `meta.json`, so the
  comparison is unaffected.
- A Mission whose `meta.json` cannot be read: the pre-existing preflights own that failure.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Refuse a protected `--target` override | As an operator, I want `consolidate --target <protected>` refused before any branch moves so that a Mission never lands directly on a branch my project protects. | High | Open | [build] | no |
| FR-002 | Name the branches and the way forward | As an operator, I want the refusal to name the protected branch, the Mission's recorded target, and the ways forward (drop `--target`; record the target; the operator hatch) so that I can act without reading the source. | High | Open | [build] | no |
| FR-003 | Same refusal in preview and API | As an operator, I want `--dry-run` and `orchestrator-api consolidate-mission` to report the same code and remedy so that the preview can be trusted. | Medium | Open | [build] | no |
| FR-004 | Leave every existing protection decision untouched | As a maintainer, I want the #5385 recorded-target refusal and the deliberately-allowed landings unchanged so that the fix cannot widen a documented contract. | High | Open | [ratchet] | yes — positive control: the in-bounds `--target` run still consolidates in the same test module |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Refusal is pre-mutation | A refused run moves no branch (target, mission/coordination, lanes), writes no merge record, adds no reflog entry, and prints no traceback: 0 refs changed, exit 1. | Reliability | High | Open |
| NFR-002 | One protection authority | The decision is `ProtectionPolicy`'s (the sole sanctioned source); 0 second protected-branch lists or bespoke name comparisons added. | Maintainability | High | Open |
| NFR-003 | Bounded latency | The guard adds at most one policy resolution (config read plus ≤ 3 git probes) to a pre-lock preflight; no measurable change to a refused run's wall clock. | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new error code | Reuse `PROTECTED_BRANCH_REFUSED`; the status-write protocol's code allowlist is a public contract and is not extended. | Technical | High | Open |
| C-002 | Scope is the override | The recorded-target case keeps #5385's decision; the unprotected-mismatch case is a named residual, not this Mission's change. | Business | High | Open |
| C-003 | Doctrine surface untouched | No change under `packs/`; the guard is product behaviour in core. | Technical | Medium | Open |

### Key Entities

- **Protection decision**: the resolved protected set plus the operator hatch, produced only by
  `ProtectionPolicy` (`is_protected_target` folds "primary plus configured").
- **Recorded target**: the target branch the Mission declares in `meta.json` (via
  `resolve_merge_target_branch` with no override); the branch its bookkeeping lands on.
- **Effective target**: the branch the branch-integration step actually commits to, after `--target`.
- **Refusal**: the policy's `Refused` carrier — `error_code`, `message`, `next_step`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's command (`consolidate --mission <slug> --target main`, Mission recorded for
  `develop`) exits 1 with `PROTECTED_BRANCH_REFUSED`, `main` at its pre-run SHA and no squash commit on
  `main`, and a control on the same fixture shows the same run landing on `develop` without
  `--target` — [build] · no-op passable: no
- **SC-002**: The three entries (real run, `--dry-run --json`, `orchestrator-api consolidate-mission`)
  report the same code and remedy for the same fixture — [build] · no-op passable: no
- **SC-003**: Every existing control in `tests/terminus/test_protected_target_preflight.py` and
  `tests/orchestrator_api/test_consolidate_mission_protected_target.py` passes unmodified —
  [ratchet] · no-op passable: yes (the existing fixtures are the positive control)
