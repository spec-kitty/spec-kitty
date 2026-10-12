# Mission Specification: Derive the mission-state audit's CI trigger list from what the audit executes

**Mission Branch**: `issue-6090-audit-trigger-derivation`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #6090 (tech-debt / type:chore; follow-up from #6087; motivating incident #6058)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The audit's CI trigger never silently goes stale (Priority: P1)

A maintainer refactors the mission-state audit so it begins executing a `src/`
module that was not in the hand-written trigger list. Today nothing notices until
after merge: the PR that changes the audit's verdict is not matched by the
`mission_state` router group, so the `mission-state-audit` job is not selected, a
skipped job counts as a pass, and the nightly backstop catches the drift only
post-merge (the shape of the #6058 incident). This mission makes a per-PR test
fail the moment the audit executes a module the `mission_state` globs do not
cover — at the cheapest point in the lifecycle.

**Why this priority**: This is the defect class the mission exists to close. Without
it, the trigger list and reality can drift undetected between merges.

**Independent Test**: Plant a module the audit executes but no `mission_state` glob
matches (or drop a covering glob); the new test goes RED. Restore; it goes GREEN on
the real current code.

**Acceptance Scenarios**:

1. **Given** the real current audit and `mission_state` globs, **When** the derived
   test drives the real `doctor mission-state --audit` command (through the typer app, argv read from the CI job) on its fixture and checks every executed `src/`
   module against the group, **Then** the test passes (every executed module is
   matched).
2. **Given** a change that makes the audit execute a `src/` module no `mission_state`
   glob matches, **When** the derived test runs, **Then** it fails and names the
   un-covered module.

---

### User Story 2 - One derived source of truth, not two hand copies (Priority: P2)

A maintainer updating the audit should not have to remember to hand-edit a second
mirror of "the modules the audit touches". Today `AUDIT_INPUT_PATHS` in
`tests/ci/test_mission_state_audit_routing.py` is a hand copy of the router's
`mission_state` module globs; the two can drift from each other. This mission
removes the hand copy and derives the executed-module set at test time.

**Why this priority**: Canonical-source unification (Standing Order 6) — a single
derived authority replaces two hand-maintained mirrors.

**Independent Test**: `AUDIT_INPUT_PATHS` no longer exists as a hand-written mirror
of the executed-module list; the routing tests read a derived set and still pass.

**Acceptance Scenarios**:

1. **Given** the test module, **When** a reader inspects it, **Then** there is no
   hand-written list duplicating the `mission_state` module globs; the executed-module
   assertions come from an in-process audit run.
2. **Given** the dependency-manifest / workflow / renderer trigger inputs (which the
   audit does not execute in-process), **When** the routing tests run, **Then** their
   alignment assertions still hold from a small explicit non-executed-input list.

### Edge Cases

- **Vacuous capture**: if the fixture executed zero `src/` modules, a coverage
  assertion would pass trivially. The test must assert the derived set is non-empty
  and contains known audit anchor modules (a same-fixture positive control).
- **Order-sensitive capture**: a module imported by an earlier test would not
  re-execute its module body, so a body-only capture is flaky. The capture records
  only function-call frames during a warm (post-import) profiled run, which is
  deterministic.
- **Fixture drives an abnormal path**: a legacy `feature_slug` key, or a missing
  `status.json`, changes which modules run. The fixture must drive the normal audit
  path (modern `mission_id` events + a `status.json` so the reducer runs).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Derive the executed-module set in-process | As a maintainer, I want the set of `src/` modules the audit executes derived from a run of the real `doctor mission-state --audit` command on a small fixture (not a hand list) so the check tracks reality. | High | Open | [build] | no — asserts the derived set is non-empty and includes known audit anchor modules (`audit/engine.py`, `status/reducer.py`) as a positive control |
| FR-002 | Fail when an executed module is outside the globs | As a maintainer, I want the test to fail (naming the module) when the audit executes a `src/` module that no `mission_state` glob matches, checked via the canonical `gate_selection.load_router`/`select_gates`. | High | Open | [ratchet] | no — self-mutation-proven RED both by planting an out-of-glob executed module and by dropping a covering glob |
| FR-003 | Remove the hand-copied mirror | As a maintainer, I want `AUDIT_INPUT_PATHS` removed and its consumers re-pointed onto the derived set, so there is one source of truth for the executed-module trigger inputs. | High | Open | [folded] | no — folds into FR-001's derived set; a positive control pins that the derived set still matches the group |
| FR-004 | Keep manifest/workflow alignment without a module mirror | As a maintainer, I want the dependency-manifest, workflow, and renderer trigger inputs (not executed in-process) kept as a small explicit list so their routing + alignment assertions still hold. | Medium | Open | [ratchet] | no — paired with the real router: each listed input must still match the `mission_state` group and (for manifests) the events-alignment workflow |
| FR-005 | Do not over-trigger or weaken routing | As a maintainer, I want the `mission_state` group to keep triggering correctly without regressing into a static import closure (~534 modules) or whole-subpackage triggering. | Medium | Open | [ratchet] | no — the existing `mission_state` routing tests (`test_a_mission_diff_selects_the_audit_job`, `test_the_audit_modules_are_not_spelled_src`) stay green |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast per-PR test | The derived test completes in under 2 seconds (the in-process audit over the fixture runs in ~0.01s; it does not scan the real corpus). | Performance | High | Open |
| NFR-002 | Deterministic capture | The executed-module capture is order-independent across a full test session (warm, function-call-scoped profiling), producing an identical set on repeated runs. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No runtime/product behaviour change | The audit's own imports and behaviour are unchanged; this mission adds a test and removes a test-side hand copy only. | Technical | High | Open |
| C-002 | No ci-router.yml edit required | The audit executes no `src/` module outside the existing `mission_state` globs (33/33 covered over the real corpus), so no workflow-file edit is needed; if a future gap required one and the `.github/workflows/` push were refused, deliver the test plus a documented one-paragraph router diff for the operator. | Technical | High | Open |
| C-003 | Clean, no suppressions | No `# noqa`/`# type: ignore`/suppressions; mypy-clean; complexity ≤ 15; ruff + ruff format clean on changed files. No new ratchet/allowlist gate. | Technical | High | Open |
| C-004 | ATDD, failing-first | The derivation test is the acceptance test and is committed failing-first (demonstrating it catches the drift the hand copies missed) before the change that makes it pass. | Process | High | Open |

### Key Entities

- **Executed-module set**: the `src/`-relative module paths whose functions run
  during a run of the real `doctor mission-state --audit` command over the fixture (warm, function-call-scoped; 37 modules at landing).
- **`mission_state` group**: the router paths-filter group whose globs decide when
  the `mission-state-audit` job runs; the single routing authority is
  `scripts/ci/gate_selection.load_router`.
- **Non-executed trigger inputs**: dependency manifests (`uv.lock`,
  `pyproject.toml`, `.kittify/release/shared-package-compatibility.json`), the
  workflow, and the renderer — legitimate triggers the audit does not execute
  in-process, kept as a small explicit list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The derived test is RED when a module the audit executes is outside the
  `mission_state` globs (planted break) and GREEN on the real current code — demonstrated both directions. — [build] · no-op passable: no (positive control asserts a non-empty, anchor-containing derived set)
- **SC-002**: `AUDIT_INPUT_PATHS` no longer exists as a hand-written duplicate of the `mission_state` module globs; the routing tests read the derived set. — [ratchet] · no-op passable: no (a reader/AST check confirms the mirror is gone while coverage assertions still hold)
- **SC-003**: The touched CI-routing tests and `make test-fast` pass, with the `mission_state` group still selecting the audit job and not over-triggering. — [ratchet] · no-op passable: no (paired against the real router and existing routing tests)
