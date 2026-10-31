# Work Packages: Audit and remove special-case workarounds

**Inputs**: Design documents from `/kitty-specs/workaround-audit-and-removal-01M68ZKV/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (§4 ledger, §5 decisions)

**Tests**: Yes — the two removals each carry a test that fails if the workaround returns
(a seam patch-point test and a contract assertion replacing the tolerance test). No test is
deleted.

**Organization**: Three work packages. WP01 and WP02 are independent code changes (different
modules); WP03 is the developer-docs deliverable and depends on both so its "removed here"
rows describe what actually landed.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: One public builder for the runtime discovery context (Priority: P1)

**Goal**: Delete the duplicated `DiscoveryContext` constructor in the mission loader and
publish the runtime's builder as the one seam, so a context field (such as the org tier) can
never again be wired into one copy and missed in the other.
**Independent Test**: patching `runtime.next.runtime_bridge_io.build_discovery_context` is
observed by `mission run` (`run_custom_mission`), and no module defines a second repo-rooted
constructor.
**Prompt**: `/tasks/WP01-discovery-context-seam.md`
**Requirement Refs**: FR-004, FR-005, NFR-002, SC-002

### Included Subtasks

T001 Write the seam patch-point test first: patching `build_discovery_context` on the io seam is observed by `run_custom_mission`, and neither module keeps `_build_discovery_context`
T002 Publish `build_discovery_context` in `src/runtime/next/runtime_bridge_io.py` and point its internal callers at it
T003 Delete `_build_discovery_context` from `src/specify_cli/mission_loader/command.py`, import the seam, and fix the two docstring references
T004 Update `tests/runtime/test_bridge_io.py`: the seam-owned name list and the four constructor tests use the public name
T005 Run the focused suites, `ruff`, and `mypy` on the touched files

### Implementation Notes

- Rename in place (DIRECTIVE_024); do not move the builder into a new module.
- Keep `resolve_pack_chain(..., strict=False, quiet=True)` and let `OrgPackSubdirEscapeError`
  / `OrgPackEnvVarUnsetError` propagate — no `try/except` may wrap the call (DEC-005).
- The seam-owned name list is a non-vacuity pin for an architectural gate; it must name the
  new public symbol in the same commit that renames it.

### Parallel Opportunities

- T002/T003 are ordered (T003 imports what T002 publishes); T004 is mechanical after both.
  WP01 runs in parallel with WP02 (no overlapping files).

### Dependencies

- None.

### Risks & Mitigations

- `tests/runtime/test_bridge_no_compat_delegates.py` pins that the bridge keeps no forwarder
  for seam-owned names: adding the public name to the list keeps that gate honest; a stale
  entry fails loudly rather than silently.
- Updating only one of the two call sites would leave a copy: T001's patch-point test is the
  detector.

---

## Work Package WP02: Composition reads the executor contract, not a test double (Priority: P2)

**Goal**: Remove the `getattr` defaults and the `len()` tolerance in `_compose_action` that
exist so `MagicMock` results flow through, and rewrite the test that pins that tolerance.
**Independent Test**: a fake result carrying `invocation_ids=("inv-001", "inv-002")` makes the
bridge log report 2 invocations, and the module contains no `getattr(result, ...)` default.
**Prompt**: `/tasks/WP02-composition-contract-read.md`
**Requirement Refs**: FR-006, FR-007, NFR-001, SC-003

### Included Subtasks

T006 Rewrite `test_dispatch_handles_non_sized_invocation_ids_and_returns_guard_failures` to assert the contract (real tuple → emitted count) while keeping its guard-failure coverage
T007 Read `result.invocation_ids` and `result.steps` directly in `_compose_action`, drop the `getattr` defaults and the `except TypeError`, and update the two explanatory comments
T008 Run the composition/bridge suites, `ruff`, and `mypy` on the touched files

### Implementation Notes

- `StepContractExecutionResult` (`src/specify_cli/mission_step_contracts/executor.py:145-163`)
  always carries both `invocation_ids` and `steps`; `StepContractStepResult` always carries
  `unresolved_candidates`.
- The rewritten test must not lose the guard-failure assertion that gives it its name.

### Parallel Opportunities

- T006 and T007 touch different files (test vs source) and can be written together; the test
  is the red-first proof and must fail against the pre-change source only if the contract is
  violated, so land them in one commit with the test first.

### Dependencies

- None. Runs in parallel with WP01.

### Risks & Mitigations

- The `except Exception` above (FR-009 structured-failure surface) is deliberately **kept**:
  it is a documented contract for executor failures, not a test-double accommodation. Only the
  post-`try` result read changes.

---

## Work Package WP03: The audit method and its ledger on one page (Priority: P1)

**Goal**: Make the audit repeatable and auditable: heuristics, time-box, the four
classifications, and a disposition row per suspect with evidence and outcome.
**Independent Test**: every suspect in issue #6745 has a row with a classification, an
evidence pointer, and either "removed here" or a child-issue number; the docs freshness check
passes.
**Prompt**: `/tasks/WP03-audit-page-and-changelog.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-008, C-002, C-004, SC-001

### Included Subtasks

T009 Author `docs/development/how-to/auditing-special-case-workarounds.md` (method, classifications, ledger table, "what we deliberately left" section)
T010 Add the page to `docs/development/how-to/index.md` and keep the docs index fresh
T011 Add the `[Unreleased]` changelog entry (impact-first lead with `(#6745)`, before→after, under 1,200 characters)
T012 Verify: docs freshness (`errors=0`), changelog style test, no-legacy-terminology test

### Implementation Notes

- The ledger must be honest: six suspects from the issue plus the four the audit added
  (S7/S8 removed here; S9 and the "secure the sample" note deferred). State plainly that the
  327 `BLE001` sites are sampled, not reviewed.
- Child issues: S1 (activation-token refusal), S5 (`reenter_lane_self_heal` seam), S9
  (dependency-cycle refusal), and the process-guard proposal. Their numbers are recorded in
  the page once filed; if any is still open at implementation time, cite it by number.
- Do not add doctrine to `packs/built-in/` (C-004); the guard proposal is a tracker issue.

### Parallel Opportunities

- T009 → T010 → T011 in order; T012 last.

### Dependencies

- Depends on WP01 and WP02: the "removed here" rows describe their delivered state.

### Risks & Mitigations

- Docs-index regeneration: run only the writes this page needs and verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (`errors=0`); do not rebuild the
  whole CLI reference on this shared host.
- Changelog length: `tests/docs/test_changelog_style.py` enforces the 1,200-character bound.

---

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Seam patch-point test, red first | WP01 | |
| T002 | Publish `build_discovery_context` | WP01 | |
| T003 | Delete the loader's copy, import the seam | WP01 | |
| T004 | Update seam-owned names and constructor tests | WP01 | |
| T005 | Focused suites + lint/type checks | WP01 | |
| T006 | Rewrite the tolerance test as a contract test | WP02 | [P] |
| T007 | Read the executor result contract directly | WP02 | [P] |
| T008 | Focused suites + lint/type checks | WP02 | |
| T009 | Author the audit page | WP03 | |
| T010 | Index row + docs freshness | WP03 | |
| T011 | Changelog entry | WP03 | |
| T012 | Verify docs gates | WP03 | |
