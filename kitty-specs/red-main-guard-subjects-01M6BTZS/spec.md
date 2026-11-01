# Mission Specification: Clear the two pre-existing contract-guard reds (#6997)

**Mission Branch**: `issue-6997-red-main-guard-subjects`
**Created**: 2026-11-01
**Status**: Draft
**Input**: User description: "Issue #6997 — Pre-existing red on main: two tests/contract guards fail (terminology guard on unclog-ci.md:95; SAFE_COMMIT_DIRECTORY_ARGUMENT not in the orchestrator contract). Batch 7 agent T5. Fix the guards' subjects, not the guards; never weaken or xfail a gate."

## User Scenarios & Testing *(mandatory)*

The subject of both reds is a piece of state the guard is supposed to be able to
trust: in the first, a live doc page's wording; in the second, the orchestrator-api
contract's `allowed_error_codes`. In both cases the guard is right and the subject is
wrong. Not one guard is narrowed, skipped, xfailed or exempted.

### User Story 1 - A live ops runbook stops teaching deprecated main-centric wording (Priority: P1)

A maintainer reading `docs/development/how-to/unclog-ci.md` needs the explanation of
why the Actions queue refills. The page currently says "Every GitHub PR merge to
`main` starts a new wave", which is the exact phrasing the branch-intent terminology
guard exists to keep out of live docs: it reads as a workflow instruction to merge in
`main`, when the page means that a PR landing on the trunk causes a new CI wave. The
page must state that fact without the deprecated phrasing, and the terminology guard
must go green on the untouched guard code.

**Why this priority**: it is one of the two reds the issue is about, and it is the
cheaper half; a live page teaching the deprecated wording is a correctness defect in
its own right, not just a grep trip.

**Independent Test**: run the terminology guard on the reworded page (green) and on
the pre-rewording page (red again). The guard file itself is unchanged.

**Acceptance Scenarios**:

1. **Given** the page with the deprecated sentence, **When** the terminology guard
   runs, **Then** it fails on `docs/development/how-to/unclog-ci.md:95`.
2. **Given** the reworded page, **When** the same guard runs, **Then** it passes and
   the page still says that a PR landing causes a new CI wave.
3. **Given** the guard's forbidden-pattern list, **When** it is read after this
   mission, **Then** it is byte-identical to the list on the mission's base commit.

---

### User Story 2 - The orchestrator contract admits every safe-commit error code core emits (Priority: P1)

An external orchestrator keys on the contract's `allowed_error_codes`, not on prose.
`SafeCommitDirectoryArgument` (`SAFE_COMMIT_DIRECTORY_ARGUMENT`, shipped with the
#6750 fix) is emitted by the safe-commit path but is absent from
`orchestrator_api.allowed_error_codes`, so the contract test fails and — more
importantly — the published contract understates what core can emit. The code must be
registered in the vendored contract and in its pinned mirror, and mirrored in the two
prose surfaces that enumerate the codes (the API reference and the operator skill's
error-code table), exactly as the #5443 registration did for three sibling codes.

**Why this priority**: an understated contract is a caller-visible correctness gap in
the machine-readable surface the whole orchestrator integration is built on.

**Independent Test**: run
`tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed`
(red before, green after), and
`tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact`
(green: the two copies stay byte-identical).

**Acceptance Scenarios**:

1. **Given** the current contract, **When** the safe-commit contract test runs,
   **Then** it fails naming `SAFE_COMMIT_DIRECTORY_ARGUMENT` as the extra item.
2. **Given** the code registered in both contract copies, **When** the same test runs,
   **Then** it passes, and the vendored/planning-artifact equality test still passes.
3. **Given** a re-run of the code walk over every `SafeCommitError` descendant,
   **Then** the emitted set is a subset of `allowed_error_codes` with no code exempted
   by name.

### Edge Cases

- The two contract copies (`src/specify_cli/core/upstream_contract.json` and
  `docs/contracts/upstream-3.0.0-shape.json`) must be edited identically;
  `test_vendored_contract_matches_planning_artifact` compares parsed JSON, so a
  one-sided edit is caught.
- The mission-064 archived copy of the shape
  (`kitty-specs/064-complete-mission-identity-cutover/contracts/`) is byte-frozen by
  `tests/architectural/test_archive_root_byte_identical.py` and must NOT be touched
  (SK-154).
- The reworded sentence must stay accurate: merges landing on the trunk really do
  start a new CI wave; the fix removes the deprecated phrasing, not the fact.
- The reworded docs line must stay within the page's wrapping width so the diff reads
  as a wording change, not a reflow.
- `SAFE_COMMIT_DIRECTORY_ARGUMENT` is a pre-mutation refusal (nothing was committed),
  so it is not a `SAFE_COMMIT_RECOVERY_FAILED` refinement; the docs entry must say so.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | unclog-ci wording clears the branch-intent guard | As a maintainer, I want the ops runbook to describe the trunk-merge CI wave without deprecated main-centric phrasing, so that the live docs stay clean and the guard is honestly green. | High | Open | [build] | no — the guard fails on the current sentence |
| FR-002 | Register `SAFE_COMMIT_DIRECTORY_ARGUMENT` in the vendored contract | As an external orchestrator author, I want every safe-commit code core emits to be in `allowed_error_codes`, so that I can key on the contract without a hole in it. | High | Open | [build] | no — the contract test fails on the current contract |
| FR-003 | Keep the pinned contract mirror identical | As a maintainer, I want `docs/contracts/upstream-3.0.0-shape.json` to carry the same change, so that the vendored/planning-artifact equality gate stays green. | High | Open | [build] | no — a one-sided edit fails the equality gate |
| FR-004 | Mirror the code in the two prose surfaces | As a reader of the API reference or the operator skill, I want the code listed and explained where the other safe-commit codes are, so that the enumerations agree with the machine-readable contract. | Medium | Open | [build] | no — the code is absent from both enumerations today |
| FR-005 | Name the code in the contract test's explicit list | As a maintainer, I want the contract test to name `SAFE_COMMIT_DIRECTORY_ARGUMENT` alongside the three codes the last registration named, so that the regression is legible and pinned by name. | Medium | Open | [ratchet] | yes — the descendant walk already fails; the named assertion is a positive control that pins this specific code |
| FR-006 | Changelog entry as a per-PR fragment | As an operator, I want the user-visible half (contract admits a code it already emitted) recorded in the unreleased changelog, so that the change is discoverable at release. | Medium | Open | [build] | no — the entry does not exist today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Guard files unchanged | `tests/contract/test_terminology_guards.py`'s forbidden-pattern list and scan scope are byte-identical to the base commit; no `skip`, `xfail`, `-k` deselection or scope exemption is added anywhere. | Reliability | High | Open |
| NFR-002 | Both contract copies byte-identical | After the change, `src/specify_cli/core/upstream_contract.json` and `docs/contracts/upstream-3.0.0-shape.json` are byte-identical to each other. | Consistency | High | Open |
| NFR-003 | No frozen surface touched | No file under `services/`, the mission-064 archive root, or the ADR D-9 frozen set changes. | Compliance | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Fix the subject, not the guard | The only permitted response to either red is to correct the doc wording and the contract data; changing a guard's patterns, scope or severity is out of scope. | Technical | High | Open |
| C-002 | No archive or pin-target move | The contract pin target stays `docs/contracts/upstream-3.0.0-shape.json`; do not repoint it at the mission-064 archive copy (SK-154). | Technical | High | Open |
| C-003 | No merge semantics change | The registered code is additive data: no new verb, no renamed field, no removed code. | Technical | High | Open |

### Key Entities *(include if this mission involves data)*

- **Contract shape** (`upstream_contract.json`): the machine-readable, vendored
  contract with `orchestrator_api.allowed_error_codes`; the pinned planning copy is
  `docs/contracts/upstream-3.0.0-shape.json`.
- **Safe-commit error codes**: the `error_code` strings on `SafeCommitError` and its
  descendants in `src/specify_cli/git/commit_helpers.py` — the set the contract test
  walks and compares against `allowed_error_codes`.
- **Live doc page**: `docs/development/how-to/unclog-ci.md`, a first-party live doc in
  the terminology guard's scan scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The two guards named in #6997 pass, run exactly as the issue invoked them, with no guard-side edit — [build] · no-op passable: no
- **SC-002**: `git diff` against the base commit shows zero changes inside `tests/contract/test_terminology_guards.py` and zero added `skip`/`xfail` marks anywhere in the diff — [ratchet] · no-op passable: yes — positive control: the base-commit version of the guard fails on the base-commit doc, so the guard was live before and after
- **SC-003**: Every `SafeCommitError` descendant's `error_code` is a member of `allowed_error_codes`, with no code excluded by name — [ratchet] · no-op passable: no
- **SC-004**: `test_vendored_contract_matches_planning_artifact` and the docs-freshness check report zero errors after the change — [ratchet] · no-op passable: yes — positive control: a one-sided edit to either contract copy makes the equality gate fail

## Amendment 2026-11-01 (implementation)

The repo moved changelog entries to per-PR fragments (`docs/changelog/unreleased/<id>.<section>.md`,
ADR `2026-11-01-1`, #6988) after this spec was written; `AGENTS.md` now says a PR never edits
`docs/changelog/CHANGELOG.md`. FR-006 is satisfied by the fragment
`docs/changelog/unreleased/6997.fixed.md` (renamed to the PR number once the PR exists), which the
release assembles into `[Unreleased]`. The requirement itself is unchanged; only its delivery
surface moved.

## Out of Scope

- Adding the `tests/contract` shard to `make test-fast` (why the red sat unnoticed) —
  a CI-budget decision for the operator, recorded in the PR's `## Deferred`.
- Making the docs/skill error-code enumerations machine-checked against the contract.
  The current prose enumerations already omit 22 contract codes that are documented
  in prose form elsewhere, so a parity gate is its own mission with a docs decision;
  recorded in `## Deferred`.
- Any change to the safe-commit implementation or to `#6750`'s behaviour.
