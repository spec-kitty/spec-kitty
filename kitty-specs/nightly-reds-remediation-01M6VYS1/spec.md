# Mission Specification: Cheap nightly reds remediation

**Mission Branch**: `issue-7183-nightly-reds-remediation`
**Created**: 2026-11-07
**Status**: Draft
**Input**: User description: "Fix the cheap nightly reds #7177, #7178, #7111, #7181, #7182, #7183 using the research debrief (every node reproduced RED on origin/main 13f873afb7)."

## Intent Summary

The maintainer reads the nightly run on `main`. Nineteen test nodes across six issues are red. Every one traces to a deliberate, already-landed contract change whose own pull request stayed green because the failing tests live in out-of-matrix trees that only the nightly executes. Eighteen of the nodes are stale pins that must be re-pinned to the new contract at least as strongly as before (never weakened); one (issue 7178) is a real production violation of the destructive-git-advice gate and is fixed in production code. Done means each named node passes locally, each re-pin cites the commit that moved its contract, the gate allowlist stays empty and no guard is relaxed.

Primary scenario: the maintainer opens the next nightly and finds these nodes green for the right reason. Main exception: a node cannot be re-pinned without weakening it; the work stops and reports an operator decision instead of greening it. Invariant: a test is never made weaker to turn it green.

## Domain Language

- **Mission** is the canonical term (never "feature").
- **Stale pin**: a test assertion or fixture that encodes a contract a landed change deliberately moved.
- **Out-of-matrix tree**: a test directory that per-pull-request CI does not run (nightly only).
- **Residue** here means the read-side sense: a `kitty-specs/` child that is not a selectable Mission (#5875). Do not use bare "residue".
- **Node**: one pytest node id.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Test re-pins that need no production change (Priority: P1)

As the maintainer, I want the stale pins for #7177 (consolidate flag-surface golden) and #7111 (orchestrator-api migration actor) re-pinned so those nodes stop failing on contracts that were changed on purpose.

**Why this priority**: smallest, safest edits that clear two reds and establish the re-pin discipline.

**Independent Test**: run the two exact node ids; both pass, and the guards they sit next to (the seed-actor refusal matrices) stay green.

**Acceptance Scenarios**:

1. **Given** the `consolidate` parser now carries the visible `--dependency-ref` flag (#6771), **When** the flag-surface golden runs, **Then** it passes and still fails for any other new or removed flag.
2. **Given** a caller-supplied `migration:` actor is refused (#6754), **When** the orchestrator-api migration-actor test runs, **Then** it seeds the reconstruction seed in-process through the system-actor builder and still asserts the stored-whole actor, the migration-actor predicate and the reducer's reconstruction-seed behaviour.

---

### User Story 2 - Destructive git advice routed through its one home (Priority: P1)

As the maintainer, I want the upgrade tracked-meta notice to render its file-restore remedy through the canonical git-remedies module so the destructive-advice gate passes with its allowlist still empty and the operator-visible text is unchanged.

**Why this priority**: the only production defect of the six; the gate is correct and must not be weakened.

**Independent Test**: the gate node passes; the notice tests that pin the exact remedy text still pass byte for byte.

**Acceptance Scenarios**:

1. **Given** the notice module prints `git checkout -- <path>` inline, **When** the gate scans `src/`, **Then** no inline destructive command remains and the allowlist is still empty.
2. **Given** the staged-differs and index-only refusal branches, **When** the notice renders, **Then** the remedy is the checkout form (index to working tree), so a staged edit is never discarded and an index-only file is never given a remedy that fails.

---

### User Story 3 - Charter status and activation tests match the current contracts (Priority: P2)

As the maintainer, I want the `charter status` tests (#7181) and the charter activation and interview tests (#7182) re-pinned to the typed refusal envelope, the absent-key rule and the file-name collision refusal.

**Why this priority**: eight-plus nodes, all test-side, but each needs a careful strength-preserving re-pin.

**Independent Test**: the two status nodes and the eight activation and interview nodes pass; the sibling files that pin the same contracts stay green.

**Acceptance Scenarios**:

1. **Given** `charter status --json` now refuses with `{ok:false, error:{code,message}}`, **When** its error test runs, **Then** it asserts the typed payload including the code, and the unparseable-`charter.yaml` test asserts exit 1 with `ACTIVE_CHARTER_CONFIG_INVALID`.
2. **Given** a first `charter activate` on a keyless project writes no allow list (#6685), **When** the write-path tests run, **Then** they seed present empty lists first so the write path is genuinely exercised.
3. **Given** two layers use one file name for different directive ids, **When** the interview runs, **Then** the tests assert the refusal in the interview's own JSON error shape (not the status envelope) for both the selection-driven and org-required cases.

---

### User Story 4 - The five remaining nightly nodes of #7183 (Priority: P2)

As the maintainer, I want each of the five independent stale pins of #7183 re-pinned to its own contract: the structured merge system actor, the selectable-Mission fixture identity, the per-Mission git-call budget, the synthesis lock file in the project-tree snapshot, and the one-file-per-record lifecycle bookkeeping.

**Why this priority**: closes the umbrella issue; five unrelated changes, each its own point cut.

**Independent Test**: the five exact node ids pass and each owning file is green.

**Acceptance Scenarios**:

1. **Given** the done transition writes the structured four-key system actor (#6722), **When** the merge test runs, **Then** it asserts the full four-key actor.
2. **Given** a sole-active-Mission default needs a Mission with identity (#5875), **When** the tasks-status default tests run, **Then** the fixture Missions carry distinct `mission_id` values and the error-path tests in the file still error for the right reason.
3. **Given** the tracked-meta guard adds four git calls per real Mission (#6673), **When** the cutover probe test runs, **Then** its budget is `2 + 4 x real Missions` and still proves identity-less folders cost the single batch probe, never a probe each.
4. **Given** activate and deactivate hold the synthesis lock (#6719), **When** the pack-skill lifecycle test compares project snapshots, **Then** only the runtime-locks subtree is ignored, and the test also asserts the lock file exists so the ignore is not vacuous.
5. **Given** lifecycle records are one new file per record (#7003), **When** the single-branch residue test runs, **Then** it asserts the tracked-and-modified Mission events file and the new per-record untracked form, and still queries tracked changes only.

---

### Edge Cases

- A re-pin that would only pass by loosening an assertion (subset, negation, deleting the pin) is an operator decision, not a fix.
- A path containing a space renders quoted in the new git-remedies renderer; the notice paths never contain spaces, so output stays byte-identical.
- A first-in-session venv rebuild once made the pack-skill lifecycle test fail one time; a single one-off red there is environment residue, never retried to green silently (report it).
- The charter-activate cascade tests take about two minutes; that is expected.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Pin the `--dependency-ref` flag in the consolidate flag-surface golden | As the maintainer, I want the golden's expected long-flag set to include `--dependency-ref` so the node passes while any other flag drift still fails (#7177, #6771 `9c2881c6`). | High | Open | [ratchet] | no |
| FR-002 | Seed the migration actor in-process in the orchestrator-api test | As the maintainer, I want the stored-whole migration-actor test to write its seed through the system-actor builder with role `system`, keeping its three seed predicates, so it no longer passes a refused caller-supplied actor (#7111, #6754 `f22a7b6275`). | High | Open | [ratchet] | no |
| FR-003 | Render the file-restore remedy through the git-remedies home | As the maintainer, I want a checkout-form recipe renderer in the canonical git-remedies module used by the tracked-meta notice, with unit tests, so the destructive-advice gate passes with an empty allowlist and notice text is byte-identical (#7178). | High | Open | [build] | no |
| FR-004 | Re-pin the two `charter status` tests to the typed refusal | As the maintainer, I want the error-JSON test pinned to `{ok:false,error:{code,message}}` and the unparseable-`charter.yaml` test pinned to exit 1 `ACTIVE_CHARTER_CONFIG_INVALID` (#7181, #6557 `9bee2389`). | High | Open | [ratchet] | no |
| FR-005 | Seed present activation lists in the six activate tests | As the maintainer, I want the six write-path activation tests to seed present empty lists so they still exercise the write path under the absent-key rule (#7182, #6685 `09bca55275`). | High | Open | [ratchet] | no — each keeps its original assertion on the same fixture |
| FR-006 | Re-pin the two ambiguous-directive interview nodes to the collision refusal | As the maintainer, I want both parameters pinned to the file-name-collision refusal in the interview's own error JSON shape (#7182, `a8dd1812`). | High | Open | [ratchet] | no |
| FR-007 | Re-pin the merge done-transition actor | As the maintainer, I want the done-emit test to assert the structured four-key system actor (#7183 node 1, #6722 `3c0a8f3453`). | Medium | Open | [ratchet] | no |
| FR-008 | Give the tasks-status default fixture Missions an identity | As the maintainer, I want the fixture helper to write a distinct `mission_id` per Mission so the two defaulting nodes pass and the three error-path tests keep their meaning (#7183 node 2, #5875 `7634075bd5`). | Medium | Open | [ratchet] | no |
| FR-009 | Re-derive the cutover git-call budget | As the maintainer, I want the budget set to `2 + 4 x real Missions` so residue-independence stays pinned (#7183 node 3, #6673 `d8829074b7`). | Medium | Open | [ratchet] | no |
| FR-010 | Ignore the runtime-locks subtree in the pack-skill lifecycle snapshots | As the maintainer, I want both snapshots to ignore the runtime-locks subtree and the test to assert the lock file exists (#7183 node 4, #6719 `d4be7a1940`). | Medium | Open | [ratchet] | no |
| FR-011 | Re-pin the single-branch residue bookkeeping check | As the maintainer, I want the tracked-and-modified assertion to name the Mission events file and add the per-record untracked form (#7183 node 5, #7003 `8f3149ae5b`). | Medium | Open | [ratchet] | no |
| FR-012 | Record the change for operators | As the maintainer, I want an internal changelog fragment describing the fix, and a drafted follow-up (in the Mission tracer files; filing it is the operator's call) for the per-Mission four-git-call guard cost (FR-009). | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Strength preserved | Every re-pinned test keeps at least its original behavioural assertions plus the new contract; zero assertions are deleted without a stronger home, zero allowlist entries are added. | Quality | High | Open |
| NFR-002 | Node-level proof | Each of the nineteen named node ids is run before (RED) and after (GREEN) the change with pass/fail counts recorded; zero are left red or skipped. | Reliability | High | Open |
| NFR-003 | Blast radius | Each owning test file and each named gate runs green; no full or heavy suite is run (NO_FULL_HEAVY_SUITES_IN_MISSION). | Reliability | High | Open |
| NFR-004 | Lint and format | `ruff check` and `ruff format --check --force-exclude` report 0 issues on every touched file; new code adds no `noqa` or `type: ignore`. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Brownfield point cuts | Touch only the files named in the debrief, the changelog fragment, the follow-up note and the Mission dossier; no refactors. | Technical | High | Open |
| C-002 | Do not substitute the restore recipe | The checkout-form renderer is new; `restore_recipe` must not be used for the notice because it drops the staged edit kept by the staged-differs branch and fails for index-only files. | Technical | High | Open |
| C-003 | Gate and guards stay | The git-remedies gate keeps an empty allowlist; the #6754 seed-actor guard and its refusal matrices are not changed. | Technical | High | Open |
| C-004 | Two error envelopes | The charter interview keeps its own error JSON shape; only `charter status` uses the typed envelope. | Technical | Medium | Open |
| C-005 | Stop before review | The Mission stops with every work package in `for_review`; no self-review, approve, accept, consolidate, push or pull request. | Process | High | Open |

### Key Entities

- **Nightly node**: a pytest node id that only the nightly runs; the unit of before/after evidence.
- **Contract-change commit**: the landed commit that moved a node's contract; cited in each re-pin.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 19 named node ids pass locally after the change, each shown RED on the base first — [ratchet] · no-op passable: no (a do-nothing change leaves them red).
- **SC-002**: The destructive-advice gate scan reports 0 inline destructive git commands with 0 allowlist entries — [build] · no-op passable: no.
- **SC-003**: The notice tests that pin the exact remedy strings pass unchanged (0 text diffs) — [ratchet] · no-op passable: yes — paired with SC-002 on the same fixture, which a do-nothing change fails.
- **SC-004**: 0 new `noqa`, `type: ignore` or allowlist additions across the diff — [ratchet] · no-op passable: yes — paired with SC-001, which a do-nothing change fails.
- **SC-005**: A re-pinned test still fails when its guarded behaviour regresses (spot-check the golden, the actor, the typed refusal and the budget) — [ratchet] · no-op passable: no.

## Assumptions

- The debrief's research (reproduced on `13f873afb7`) is accurate; if a node is already green or a fix does not hold on the live tree, the work reports it instead of improvising.
- Verification is local; the nightly owns final confirmation of the out-of-matrix trees.
